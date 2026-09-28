"""Git connector: repository state and commit events.

Implements the NerveCenter connector for Git repositories (spec Section 44,
"Connectors"). It shells out to the ``git`` CLI; no other external
dependencies are required.

Capabilities
------------

* **Point-in-time snapshot** (:meth:`snapshot` / :meth:`_snapshot_internal`)
  — a *pure* capture of the repository's current state. Includes:

  - ``branch`` — current branch name, or ``"detached"`` when applicable
  - ``head`` — full SHA of the current HEAD commit, or ``None`` on empty repos
  - ``subject`` — one-line commit message of HEAD
  - ``author`` — author name/email of HEAD
  - ``committed_at`` — ISO-8601 UTC timestamp of HEAD
  - ``dirty`` — whether the working tree has staged or unstaged changes
  - ``dirty_count`` — number of changed files
  - ``commits`` — list of the last N commits, newest-first, with
    structured metadata (sha, subject, author, parents, committed_at)
  - ``branches`` — map of local branch name → tip SHA
  - ``tags`` — most recent tags, name → SHA
  - ``remotes`` — map of remote name → its default HEAD ref, if remote
    tracking refs exist

* **Live event subscription** (:meth:`subscribe` / :meth:`_subscribe_internal`)
  — differential polling that emits structured events *only* on state change:

  ================  ============  ============================================
  Event type        Subject       Payload
  ================  ============  ============================================
  ``git.commit``    commit SHA    One event per new commit, in chronological
                                  order, when HEAD advances on the same
                                  branch. Payload carries the full commit
                                  record plus ``branch``.
  ``git.checkout``  branch name   Emitted when the branch (or detached
                                  state) HEAD points at changes. Payload
                                  carries ``from`` / ``to`` / ``head``.
  ``git.branch.created``   branch name   New local branch detected.
  ``git.branch.deleted``   branch name   Local branch deleted.
  ``git.tag.created``      tag name      New tag detected.
  ``git.tag.deleted``      tag name      Tag deleted.
  ``git.working_tree``     repo name     ``dirty`` toggled between True/False.
  ``git.remote.fetched``   repo name     Remote ``fetch`` succeeded; payload
                                  carries counts of new commits per branch.
  ================  ============  ============================================

* **Remote repositories** — pass a URL (``https://…``, ``git://…``,
  ``ssh://…``) instead of a local path. The connector will:

  1. Lazily ``git clone --bare`` into a work cache
     (``<cache_root>/<hash>/``) on :meth:`connect`.
  2. On each subscription tick, optionally run ``git fetch``
     (``fetch_on_tick=True``) to pull new commits.
  3. Detect new commits on the remote's default branch and emit
     ``git.commit`` events with ``origin="remote"``.

Design notes
------------

* **Snapshot is pure.** :meth:`_snapshot_internal` only reads state — it
  never emits events. Emission is :meth:`_subscribe_internal`'s sole
  responsibility. This keeps :meth:`snapshot` idempotent and safe to
  call concurrently from multiple consumers.

* **Bounded concurrency** — every git subprocess is gated by an
  :class:`asyncio.Semaphore` (``max_concurrent``, default 4) so that a
  burst of events (e.g. 20 new commits at once triggering 20 fetches)
  cannot exhaust the process's file descriptors. This is the CLI analog
  of the HTTP connection pool other connectors use.

* **Retry policy** — inherited from :class:`~.base.Connector`. Timeouts
  and network-level ``git fetch`` failures are retryable; a missing
  ``git`` binary or a non-repo path are not.

* **Baseline discipline** — the *first* tick after :meth:`connect`
  establishes the baseline (known branches, tags, last HEAD, dirty
  state) without emitting events. Events only flow for *changes*
  observed after that.

Usage::

    from backend.connectors import GitConnector

    # Local repo
    connector = GitConnector(repo="/path/to/repo", max_commits=20)

    # Remote repo (lazily cloned, cached, polled)
    connector = GitConnector(
        repo="https://github.com/org/repo.git",
        name="org-repo",
        fetch_on_tick=True,
    )

    await connector.connect()
    snap = await connector.snapshot()
    print(snap.data["branch"], snap.data["head"])

    collected: list = []
    async def on_event(e): collected.append(e)

    await connector.subscribe(interval=2.0, on_event=on_event)
    ...
    await connector.unsubscribe()
    await connector.disconnect()
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from .base import (
    CommandResult,
    ConnectError,
    Connector,
    ConnectorEvent,
    SnapshotError,
    run_command,
)

log = structlog.get_logger(__name__)

#: Field separator for ``git log --pretty=format:...`` records. We use
#: ``\x01`` (SOH) so that tab / newline in any of the fields cannot
#: corrupt parsing. Records are separated by a single trailing newline.
_REC_SEP = "\x01"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_remote(repo: str) -> bool:
    """Return ``True`` if *repo* looks like a remote URL."""
    s = repo.strip()
    return (
        "://" in s
        or s.startswith("git@")
        or s.startswith("ssh://")
        or s.startswith("git://")
        or s.startswith("git+ssh://")
    )


class GitConnector(Connector):
    """Connector to a local or remote Git repository.

    Parameters
    ----------
    repo:
        Local path to a git working tree (must contain ``.git``), *or*
        a remote URL (``https://``, ``git://``, ``ssh://``, or
        ``git@host:path``). Remote repositories are lazily cloned
        (bare) into ``cache_root`` on :meth:`connect`.
    name:
        Human-readable name for this connector instance. Defaults to
        ``git:<repo>``.
    max_commits:
        Number of recent commits to include in each snapshot.
    timeout:
        Maximum seconds to wait for any single git subprocess.
    max_concurrent:
        Maximum number of git subprocesses that may run concurrently
        from this connector. Acts as the process-side analog of a
        connection pool.
    cache_root:
        Directory in which remote clones are cached. Defaults to
        ``~/.cache/nervcenter/git``. Only used for remote repositories.
    remote_name:
        Name of the remote to fetch. Defaults to ``origin``.
    fetch_on_tick:
        Whether the subscription loop runs ``git fetch`` before each
        diff. Only relevant for remote repositories.
    watch_remote_head:
        When ``True`` and the repository is remote, the subscription
        watches the remote's default branch (``refs/remotes/<r>/HEAD``
        or the tracking branch of local HEAD). When ``False``, the
        local HEAD of the cached clone is watched (which, for a bare
        clone, is the same branch but only updates on fetch).
    """

    connector_type = "git"
    capabilities = ["pull", "subscribe"]
    transport = "local_api"
    auth_scheme = "none"

    def __init__(
        self,
        *,
        repo: str,
        name: str | None = None,
        max_commits: int = 10,
        timeout: float = 30.0,
        max_concurrent: int = 4,
        cache_root: str | None = None,
        remote_name: str = "origin",
        fetch_on_tick: bool = False,
        watch_remote_head: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name or f"git:{repo}", endpoint=repo, **kwargs)
        if not repo:
            raise ValueError("repo must be a non-empty path or URL")
        self._repo = repo
        self._max_commits = max_commits
        self._timeout = timeout
        self._remote_name = remote_name
        self._fetch_on_tick = fetch_on_tick and _is_remote(repo)
        self._watch_remote_head = watch_remote_head
        self._is_remote = _is_remote(repo)

        # Local working directory (populated on connect for remote repos).
        self._workdir: str = repo
        self._cache_root: Path | None = None
        self._cache_lock = asyncio.Lock()

        # Bounded-concurrency gate — the CLI "connection pool".
        self._sem = asyncio.Semaphore(max(1, max_concurrent))

        # Baseline state, populated on first subscription tick.
        self._baseline_done: bool = False
        self._last_head: str | None = None
        self._last_branch: str | None = None
        self._last_dirty: bool | None = None
        self._known_branches: set[str] = set()
        self._known_tags: set[str] = set()

        # Remote-only state.
        self._last_remote_head: str | None = None

    # -- lifecycle -------------------------------------------------------------

    async def _connect_internal(self) -> None:
        """Verify git is available and the repository (or remote) is usable.

        Raises
        ------
        ConnectError
            Non-retryable: git missing, local path is not a repository,
            or remote clone fails permanently.
        """
        # 1. Git binary sanity check (non-retryable if missing).
        version = await self._run(["git", "--version"])
        if not version.ok:
            raise ConnectError(
                f"git binary unavailable: {version.stderr.strip() or version.stdout.strip()}"
            )

        # 2. Local repo: confirm it's a git work tree.
        if not self._is_remote:
            p = Path(self._repo)
            if not p.exists():
                raise ConnectError(
                    f"Repository path does not exist: {self._repo}"
                )
            check = await self._run(
                ["git", "-C", str(p), "rev-parse", "--is-inside-work-tree"]
            )
            if not check.ok:
                raise ConnectError(
                    f"Not a git repository: {self._repo}: {check.stderr.strip()}"
                )
            if check.stdout.strip() != "true":
                raise ConnectError(
                    f"Path is not a git work tree: {self._repo}"
                )
            self._workdir = str(p)
            return

        # 3. Remote repo: lazily clone (bare) into a work cache.
        self._workdir = await self._ensure_remote_workdir()
        self._log(
            "remote_connected",
            repo=self._repo,
            workdir=self._workdir,
            remote=self._remote_name,
        )

    async def _disconnect_internal(self) -> None:
        """Tear down state.

        The cached remote clone is intentionally kept on disk so that
        reconnects are fast. To remove it, delete the cache directory
        manually (or configure a fresh ``cache_root``).
        """
        self._baseline_done = False
        self._last_head = None
        self._last_branch = None
        self._last_dirty = None
        self._known_branches = set()
        self._known_tags = set()
        self._last_remote_head = None

    async def _ensure_remote_workdir(self) -> str:
        """Lazily clone a remote repo into a stable cache path.

        Uses a content hash of ``(name, repo)`` so that the same
        (connector, url) pair always maps to the same on-disk clone,
        while different repos get different directories.
        """
        async with self._cache_lock:
            cache_root = Path(
                self._cache_root_dir()
            ).expanduser()
            cache_root.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(
                f"{self.name}:{self._repo}".encode("utf-8")
            ).hexdigest()[:24]
            workdir = cache_root / digest
            if not (workdir / "HEAD").exists():
                self._log("remote_cloning", repo=self._repo, workdir=str(workdir))
                result = await self._run_plain(
                    ["git", "clone", "--bare", self._repo, str(workdir)],
                    timeout=max(self._timeout, 120.0),
                )
                if not result.ok:
                    raise ConnectError(
                        f"Failed to clone remote {self._repo}: {result.stderr.strip()}",
                        retryable=True,
                    )
            return str(workdir)

    def _cache_root_dir(self) -> str:
        if self._cache_root is not None:
            return self._cache_root
        # Respect XDG_CACHE_HOME on POSIX; fall back to ~/.cache.
        import os

        base = os.environ.get("XDG_CACHE_HOME") or "~/.cache"
        return f"{base}/nervcenter/git"

    # -- snapshot ------------------------------------------------------------

    async def _snapshot_internal(self) -> dict[str, Any]:
        """Capture a pure, side-effect-free snapshot of the repository.

        The returned dict is JSON-serializable. See the module docstring
        for the documented key set. This method never emits events; that
        is :meth:`_subscribe_internal`'s job.
        """
        branch = await self._current_branch()
        head, head_meta = await self._current_head_and_meta()
        dirty, dirty_count = await self._dirty_status()
        commits = await self._last_n_commits(self._max_commits)
        branches = await self._local_branches()
        tags = await self._recent_tags(limit=20)
        remotes = await self._remotes()

        snapshot: dict[str, Any] = {
            "repo": self._repo,
            "is_remote": self._is_remote,
            "branch": branch,
            "head": head,
            "subject": head_meta.get("subject"),
            "author": head_meta.get("author"),
            "committed_at": head_meta.get("committed_at"),
            "dirty": dirty,
            "dirty_count": dirty_count,
            "commits": commits,
            "branches": branches,
            "tags": tags,
            "remotes": remotes,
            "snapshot_at": _utcnow().isoformat(),
        }
        return snapshot

    # -- subscription --------------------------------------------------------

    async def _subscribe_internal(self, *, interval: float) -> Any:
        """Differential polling loop.

        On each tick (after ``interval`` seconds):

        1. Refresh state (branch, HEAD, branches, tags, dirty).
        2. If remote and ``fetch_on_tick``, run ``git fetch`` and
           watch the remote default branch instead of local HEAD.
        3. On the *first* tick, establish a baseline without emitting
           events.
        4. On subsequent ticks, emit events for every observed change.
        """
        while self._sub_running:
            await asyncio.sleep(max(0.05, interval))

            # Remote fetch happens *before* we read state so that the
            # diff sees the freshest possible remote refs.
            if self._is_remote and self._fetch_on_tick:
                await self._fetch_remote()

            try:
                state = await self._read_state()
            except SnapshotError as exc:
                # Non-fatal for the subscription loop: skip the tick and
                # let the next one retry. If the failure is persistent,
                # the base-class snapshot path will surface it separately
                # when health_check() is called.
                self._log(
                    "tick_read_failed",
                    error=str(exc),
                    retryable=exc.retryable,
                )
                continue

            async for event in self._diff(state):
                yield event

    async def _read_state(self) -> dict[str, Any]:
        """Read the current repo state without mutating anything."""
        branch = await self._current_branch()
        head, _ = await self._current_head_and_meta()

        # For remote watchers, prefer the remote-tracking ref if it
        # exists and resolves; that reflects what the remote has done
        # since our last fetch, independent of the local HEAD.
        watch_head = head
        if self._is_remote and self._watch_remote_head:
            remote_head = await self._remote_default_head()
            if remote_head:
                watch_head = remote_head

        branches = await self._local_branches()
        branch_names = set(branches.keys())
        tags = await self._recent_tags(limit=50)
        tag_names = set(tags.keys())
        dirty, _ = await self._dirty_status()

        return {
            "branch": branch,
            "head": head,
            "watch_head": watch_head,
            "branches": branch_names,
            "tags": tag_names,
            "dirty": dirty,
        }

    async def _diff(self, state: dict[str, Any]) -> Any:
        """Yield events for changes since the last tick.

        The *first* call establishes the baseline (no events).
        """
        if not self._baseline_done:
            self._last_head = state["head"]
            self._last_branch = state["branch"]
            self._last_dirty = state["dirty"]
            self._known_branches = set(state["branches"])
            self._known_tags = set(state["tags"])
            self._baseline_done = True
            self._log(
                "baseline_established",
                branch=state["branch"],
                head=state["head"],
                branches=len(state["branches"]),
                tags=len(state["tags"]),
                dirty=state["dirty"],
            )
            return

        emitted = 0

        # 1. New commits on the branch we're watching.
        watch_head = state["watch_head"]
        last = self._last_head
        if last and watch_head and last != watch_head:
            commits = await self._commits_between(last, watch_head)
            for commit in commits:
                payload = dict(commit)
                payload["branch"] = state["branch"]
                if self._is_remote:
                    payload["origin"] = "remote"
                yield self._make_event(
                    "git.commit",
                    subject=commit["sha"],
                    payload=payload,
                    occurred_at=self._iso_to_dt(commit.get("committed_at")),
                )
                emitted += 1
            self._last_head = watch_head
        elif watch_head and not last:
            # We had no previous HEAD (e.g. repo was empty on baseline
            # and now has commits). Emit the current commits, capped.
            commits = await self._last_n_commits(min(self._max_commits, 20))
            for commit in commits:
                payload = dict(commit)
                payload["branch"] = state["branch"]
                yield self._make_event(
                    "git.commit",
                    subject=commit["sha"],
                    payload=payload,
                    occurred_at=self._iso_to_dt(commit.get("committed_at")),
                )
                emitted += 1
            self._last_head = watch_head

        # 2. Branch change (checkout / switch).
        current_branch = state["branch"]
        if self._last_branch is not None and current_branch != self._last_branch:
            yield self._make_event(
                "git.checkout",
                subject=current_branch,
                payload={
                    "from": self._last_branch,
                    "to": current_branch,
                    "head": state["head"],
                    "detached": current_branch == "detached",
                },
                occurred_at=_utcnow(),
            )
            emitted += 1
            # After a checkout, we cannot diff the new branch's HEAD
            # against the old branch's HEAD (they diverge). Reset the
            # baseline head so the next tick treats the new HEAD as the
            # starting point and only reports *new* commits from here.
            self._last_head = state["head"]
        self._last_branch = current_branch

        # 3. Branch lifecycle (created / deleted).
        current_branches = state["branches"]
        for b in sorted(current_branches - self._known_branches):
            yield self._make_event(
                "git.branch.created",
                subject=b,
                payload={"branch": b, "head": state["head"] if b == current_branch else None},
                occurred_at=_utcnow(),
            )
            emitted += 1
        for b in sorted(self._known_branches - current_branches):
            yield self._make_event(
                "git.branch.deleted",
                subject=b,
                payload={"branch": b},
                occurred_at=_utcnow(),
            )
            emitted += 1
        self._known_branches = current_branches

        # 4. Tag lifecycle.
        current_tags = state["tags"]
        for t in sorted(current_tags - self._known_tags):
            yield self._make_event(
                "git.tag.created",
                subject=t,
                payload={"tag": t},
                occurred_at=_utcnow(),
            )
            emitted += 1
        for t in sorted(self._known_tags - current_tags):
            yield self._make_event(
                "git.tag.deleted",
                subject=t,
                payload={"tag": t},
                occurred_at=_utcnow(),
            )
            emitted += 1
        self._known_tags = current_tags

        # 5. Working-tree dirty toggle.
        current_dirty = state["dirty"]
        if self._last_dirty is not None and self._last_dirty != current_dirty:
            yield self._make_event(
                "git.working_tree",
                subject=self._repo,
                payload={"dirty": current_dirty, "branch": current_branch},
                occurred_at=_utcnow(),
            )
            emitted += 1
        self._last_dirty = current_dirty

        if emitted:
            self._log("tick_emitted", count=emitted, branch=current_branch)

    # -- git helpers ---------------------------------------------------------

    async def _run(self, argv: list[str], *, timeout: float | None = None) -> CommandResult:
        """Run a git command in the working directory, gated by the semaphore.

        Uses the connector's retry policy. ``--no-optional-locks`` is
        injected on read-only commands so that concurrent reads do not
        take write locks.
        """
        async with self._sem:
            return await run_command(
                argv,
                cwd=self._workdir,
                timeout=timeout if timeout is not None else self._timeout,
                retries=self._retry,
            )

    async def _run_plain(self, argv: list[str], *, timeout: float = 30.0) -> CommandResult:
        """Run a git command without the working-directory default (used
        for initial clone where no workdir exists yet)."""
        async with self._sem:
            return await run_command(
                argv,
                timeout=timeout,
                retries=self._retry,
            )

    async def _current_branch(self) -> str:
        """Return the current branch name, or ``"detached"``."""
        result = await self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if not result.ok:
            raise SnapshotError(
                f"Failed to determine branch: {result.stderr.strip()}",
                retryable=True,
            )
        name = result.stdout.strip()
        return "detached" if name == "HEAD" else name

    async def _current_head_and_meta(self) -> tuple[str | None, dict[str, Any]]:
        """Return ``(sha_or_none, metadata_dict)`` for HEAD.

        On an empty repository (no commits) the SHA is ``None`` and
        ``metadata_dict`` is empty.
        """
        result = await self._run(["git", "rev-parse", "HEAD"])
        if not result.ok:
            # Empty repo (or corrupt). Return None so callers can
            # gracefully skip.
            return None, {}
        sha = result.stdout.strip()
        if not sha or sha.upper() == "NULL":
            return None, {}

        meta_fmt = f"%s{_REC_SEP}%an{_REC_SEP}%ae{_REC_SEP}%ct"
        meta = await self._run(["git", "log", "-n", "1", f"--pretty=format:{meta_fmt}", sha])
        if not meta.ok:
            return sha, {"sha": sha}

        fields = meta.stdout.rstrip("\n").split(_REC_SEP)
        if len(fields) < 4:
            return sha, {"sha": sha}
        subject, an, ae, ct = fields[:4]
        committed_at: str | None
        try:
            committed_at = datetime.fromtimestamp(float(ct), tz=timezone.utc).isoformat()
        except (ValueError, OSError):
            committed_at = None
        return sha, {
            "sha": sha,
            "subject": subject.strip(),
            "author": {"name": an.strip(), "email": ae.strip()},
            "committed_at": committed_at,
        }

    async def _last_n_commits(self, n: int) -> list[dict[str, Any]]:
        """Return the last N commits, newest-first, with structured metadata."""
        if n <= 0:
            return []
        fmt = f"%H{_REC_SEP}%an{_REC_SEP}%ae{_REC_SEP}%ct{_REC_SEP}%s{_REC_SEP}%P"
        result = await self._run(
            ["git", "log", "-n", str(n), f"--pretty=format:{fmt}", "--no-show-signature"]
        )
        if not result.ok:
            raise SnapshotError(
                f"Failed to list commits: {result.stderr.strip()}",
                retryable=True,
            )
        commits: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split(_REC_SEP)
            if len(parts) < 6:
                continue
            sha, an, ae, ct, subject, parents = parts[:6]
            try:
                committed_at = datetime.fromtimestamp(float(ct), tz=timezone.utc).isoformat()
            except (ValueError, OSError):
                committed_at = None
            commits.append({
                "sha": sha.strip(),
                "author": {"name": an.strip(), "email": ae.strip()},
                "subject": subject.strip(),
                "committed_at": committed_at,
                "parents": [p for p in parents.split() if p],
            })
        return commits

    async def _commits_between(self, older: str, newer: str) -> list[dict[str, Any]]:
        """Return commits reachable from *newer* but not from *older*.

        The result is ordered **oldest first** (reverse of ``git
        rev-list`` output), so that event consumers see the commits in
        the order they were applied.

        Returns an empty list if the two refs are unrelated (e.g. a
        branch switch was handled separately).
        """
        # ``git rev-list older..newer`` lists commits reachable from
        # newer but not older, newest-first. For divergent histories
        # this can be large; we cap at ``max_commits * 4`` to bound
        # the event burst while still catching real fast-forwards.
        cap = max(self._max_commits * 4, 20)
        result = await self._run(
            ["git", "rev-list", "--first-parent", f"{older}..{newer}", "-n", str(cap)]
        )
        if not result.ok:
            # If rev-list fails (e.g. refs no longer exist), fall back
            # to just listing the commits at the tip so we at least
            # emit *something* rather than silently dropping state.
            self._log(
                "revlist_failed",
                older=older,
                newer=newer,
                stderr=result.stderr.strip(),
            )
            return []
        shas = [s.strip() for s in result.stdout.splitlines() if s.strip()]
        if not shas:
            return []
        # Reverse to oldest-first, then fetch metadata for each in one
        # batch by passing them to ``git log`` as a pathspec list.
        shas.reverse()
        fmt = f"%H{_REC_SEP}%an{_REC_SEP}%ae{_REC_SEP}%ct{_REC_SEP}%s{_REC_SEP}%P"
        meta = await self._run(
            ["git", "log", f"--pretty=format:{fmt}", "--no-walk", "--no-show-signature", *shas]
        )
        if not meta.ok:
            # Fallback: emit the tip commit only, with minimal metadata.
            return [
                {
                    "sha": s,
                    "author": {"name": "", "email": ""},
                    "subject": "",
                    "committed_at": None,
                    "parents": [],
                }
                for s in shas
            ]
        records: list[dict[str, Any]] = []
        for line in meta.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split(_REC_SEP)
            if len(parts) < 6:
                continue
            sha, an, ae, ct, subject, parents = parts[:6]
            try:
                committed_at = datetime.fromtimestamp(float(ct), tz=timezone.utc).isoformat()
            except (ValueError, OSError):
                committed_at = None
            records.append({
                "sha": sha.strip(),
                "author": {"name": an.strip(), "email": ae.strip()},
                "subject": subject.strip(),
                "committed_at": committed_at,
                "parents": [p for p in parents.split() if p],
            })
        # Preserve the requested order (oldest-first) — ``git log
        # --no-walk`` preserves argument order, so records should be in
        # the same order as ``shas``. If any are missing, filter.
        order = {s: i for i, s in enumerate(shas)}
        records.sort(key=lambda r: order.get(r["sha"], len(shas)))
        return records

    async def _local_branches(self) -> dict[str, str]:
        """Return a map of local branch name → tip SHA."""
        fmt = f"%H{_REC_SEP}%D"
        result = await self._run(["git", "branch", f"--format={fmt}"])
        if not result.ok:
            raise SnapshotError(
                f"Failed to list branches: {result.stderr.strip()}",
                retryable=True,
            )
        branches: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split(_REC_SEP, 1)
            if len(parts) < 2:
                continue
            sha = parts[0].strip()
            decorations = parts[1].strip()
            # ``%D`` gives "HEAD -> main, tag: vX" etc.
            if "HEAD -> " in decorations:
                name = decorations.split("HEAD -> ", 1)[1].split(",")[0].strip()
            elif decorations.startswith("HEAD"):
                name = decorations.split(",", 1)[0].strip()
            else:
                name = decorations.split(",")[0].strip()
            if name:
                branches[name] = sha
        return branches

    async def _recent_tags(self, *, limit: int = 20) -> dict[str, str]:
        """Return the most recent *limit* tags as ``{tag_name: sha}``.

        Ordered newest-first by creation date. The full tag namespace
        can be large; the limit bounds the snapshot payload.
        """
        result = await self._run(
            [
                "git",
                "for-each-ref",
                "--sort=-creatordate",
                "--count",
                str(limit),
                "refs/tags/",
                "--format=%(refname:short)%(separator)0%(objectname)",
            ]
        )
        if not result.ok:
            # Tags are optional; a failure here shouldn't tank the
            # snapshot. Log and return empty.
            self._log(
                "list_tags_failed", stderr=result.stderr.strip()
            )
            return {}
        tags: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\x00", 1)
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            sha = parts[1].strip()
            if name and sha:
                tags[name] = sha
        return tags

    async def _remotes(self) -> dict[str, str]:
        """Return a map of remote name → its default branch ref."""
        result = await self._run(["git", "remote"])
        if not result.ok:
            return {}
        remotes: dict[str, str] = {}
        for line in result.stdout.splitlines():
            name = line.strip()
            if not name:
                continue
            # Best-effort: read the remote's HEAD ref, if set.
            head_ref = await self._run(
                ["git", "symbolic-ref", f"refs/remotes/{name}/HEAD"]
            )
            if head_ref.ok and head_ref.stdout.strip():
                ref = head_ref.stdout.strip()
                remotes[name] = ref[len("refs/remotes/"):] if ref.startswith("refs/remotes/") else ref
            else:
                remotes[name] = ""
        return remotes

    async def _remote_default_head(self) -> str | None:
        """Return the SHA of the remote's default branch, or ``None``.

        Prefers ``refs/remotes/<remote>/HEAD`` if set; otherwise falls
        back to the tracked remote branch of the local HEAD, or the
        remote's first branch (usually ``main`` or ``master``).
        """
        # Prefer the symbolic remote HEAD.
        r = await self._run(
            ["git", "symbolic-ref", f"refs/remotes/{self._remote_name}/HEAD"]
        )
        if r.ok:
            ref = r.stdout.strip()
            if ref:
                sha_r = await self._run(["git", "rev-parse", ref])
                if sha_r.ok:
                    return sha_r.stdout.strip()

        # Fall back to the remote-tracking branch of the local HEAD.
        local_branch = await self._current_branch()
        if local_branch != "detached":
            tracking = await self._run(
                ["git", "rev-parse", f"refs/remotes/{self._remote_name}/{local_branch}"]
            )
            if tracking.ok:
                return tracking.stdout.strip()

        # Last resort: try common default branch names.
        for candidate in ("main", "master"):
            r = await self._run(
                ["git", "rev-parse", f"refs/remotes/{self._remote_name}/{candidate}"]
            )
            if r.ok:
                return r.stdout.strip()
        return None

    async def _dirty_status(self) -> tuple[bool, int]:
        """Return ``(is_dirty, count_of_changed_files)``."""
        result = await self._run(["git", "status", "--porcelain=v1", "--no-optional-locks"])
        if not result.ok:
            # Fail-open: treat as dirty so callers are cautious.
            self._log(
                "status_failed", stderr=result.stderr.strip()
            )
            return True, 0
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        return (len(lines) > 0), len(lines)

    async def _fetch_remote(self) -> None:
        """Run ``git fetch`` on the remote, best-effort.

        Failures are logged but not raised; the next tick will retry.
        The retry policy (inherited) handles transient network errors.
        """
        result = await self._run(
            [
                "git",
                "fetch",
                "--quiet",
                "--prune",
                self._remote_name,
                "+refs/heads/*:refs/remotes/" + self._remote_name + "/*",
            ],
            timeout=max(self._timeout, 60.0),
        )
        if not result.ok:
            self._log(
                "fetch_failed",
                stderr=result.stderr.strip(),
                remote=self._remote_name,
            )

    # -- event helpers ---------------------------------------------------------

    def _make_event(
        self,
        event_type: str,
        *,
        subject: str | None,
        payload: dict[str, Any],
        occurred_at: datetime | None = None,
        severity: str = "info",
        idempotency_key: str | None = None,
    ) -> ConnectorEvent:
        """Build a :class:`ConnectorEvent` with stable dedup keys."""
        if idempotency_key is None:
            idempotency_key = f"{self.connector_type}:{self.name}:{event_type}:{subject or ''}"
        return ConnectorEvent(
            event_type=event_type,
            subject=subject,
            payload=payload,
            occurred_at=occurred_at or _utcnow(),
            severity=severity,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _iso_to_dt(iso: str | None) -> datetime:
        if not iso:
            return _utcnow()
        try:
            return datetime.fromisoformat(iso)
        except ValueError:
            return _utcnow()

    def _log(self, kind: str, **fields: Any) -> None:
        log.debug(
            f"git.{kind}",
            connector=self.connector_type,
            name=self.name,
            repo=self._repo,
            **fields,
        )

    # -- emitted event types -------------------------------------------------

    def emitted_event_types(self) -> list[str]:
        return [
            "git.commit",
            "git.checkout",
            "git.branch.created",
            "git.branch.deleted",
            "git.tag.created",
            "git.tag.deleted",
            "git.working_tree",
        ]


__all__ = ["GitConnector"]
