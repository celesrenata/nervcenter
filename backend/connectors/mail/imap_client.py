"""IMAP liveness probe (prompt2 §46 — connector registry / liveness).

NerveCenter's backend never *holds* an open mailbox — the macOS Personal Relay
does the actual capture/ingest (§47). What the backend owns here is a *probe*:
given the host/port and the credential the user just typed in, open a single
IMAP connection, complete login, and report whether the mailbox answers. The
result becomes the connector's ``status`` (CONNECTED / AUTH_EXPIRED / ERROR).

The real probe (:class:`ImapImapClient`) uses the stdlib :mod:`imaplib` so the
backend has no new dependency. The probe is a small protocol
(:class:`ImapClient`) so tests inject a deterministic stub and never open a
socket — same seam the email service uses for its attention dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ImapProbeResult(StrEnum):
    """Outcome of a single liveness probe."""

    OK = "ok"                  # LOGIN + CAPABILITY succeeded
    AUTH_FAILED = "auth-failed"  # LOGIN rejected (bad / expired credential)
    CONNECT_FAILED = "connect-failed"  # host/port/TLS — network-level failure


@dataclass(frozen=True)
class ProbeResult:
    """One probe's outcome, ready to map onto a connector status."""

    outcome: ImapProbeResult
    host: str
    port: int
    error: str | None = None
    capabilities: tuple[str, ...] = field(default_factory=tuple)


class ImapClient(Protocol):
    """Liveness-probe seam. Production uses :class:`ImapImapClient`; tests
    inject a scripted :class:`StubImapClient`."""

    def probe(self, host: str, port: int, ssl: bool, username: str, password: str) -> ProbeResult: ...


class ImapImapClient:
    """Real probe over :mod:`imaplib`.

    Deliberately minimal: connect → (LOGIN or IDLE-free CAPABILITY) →
    disconnect. We only need to know the mailbox answers; we do not select a
    mailbox or fetch messages (that is the relay's job). A ``timeout`` keeps a
    hostile/unreachable host from hanging the request thread.
    """

    def __init__(self, timeout: float = 8.0) -> None:
        self._timeout = timeout

    def probe(
        self, host: str, port: int, ssl: bool, username: str, password: str
    ) -> ProbeResult:
        import imaplib

        conn: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None
        try:
            if ssl:
                conn = imaplib.IMAP4_SSL(host, port, timeout=self._timeout)
            else:
                conn = imaplib.IMAP4(host, port, timeout=self._timeout)
            code, _ = conn.login(username, password)
            if str(code).upper() not in {"OK"}:
                return ProbeResult(
                    outcome=ImapProbeResult.AUTH_FAILED,
                    host=host,
                    port=port,
                    error=f"LOGIN -> {code}",
                )
            code, data = conn.noop()
            caps = tuple(
                str(item).upper()
                for item in (data[0].split(b" ") if data and data[0] else [])
            )
            return ProbeResult(
                outcome=ImapProbeResult.OK,
                host=host,
                port=port,
                capabilities=caps,
            )
        except (OSError, ConnectionError) as exc:
            # Network-level: unreachable host, TLS handshake, reset.
            return ProbeResult(
                outcome=ImapProbeResult.CONNECT_FAILED,
                host=host,
                port=port,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 — LOGIN rejected / protocol error
            # imaplib surfaces a rejected LOGIN as a generic Exception (via
            # IMAP4.error()); the credential is the usual cause.
            return ProbeResult(
                outcome=ImapProbeResult.AUTH_FAILED,
                host=host,
                port=port,
                error=str(exc),
            )
        finally:
            if conn is not None:
                try:
                    conn.logout()
                except Exception:  # noqa: BLE001 — logout is best-effort
                    pass


class StubImapClient:
    """Deterministic probe for tests / the connector screen's mock mode."""

    def __init__(
        self,
        outcome: ImapProbeResult = ImapProbeResult.OK,
        *,
        capabilities: tuple[str, ...] = ("IMAP4rev1", "IDLE"),
        error: str | None = None,
    ) -> None:
        self._outcome = outcome
        self._caps = capabilities
        self._error = error
        self.calls: list[tuple[str, int, str, str]] = []

    def probe(
        self, host: str, port: int, ssl: bool, username: str, password: str
    ) -> ProbeResult:
        self.calls.append((host, port, username, password))
        return ProbeResult(
            outcome=self._outcome,
            host=host,
            port=port,
            error=self._error,
            capabilities=self._caps if self._outcome is ImapProbeResult.OK else (),
        )
