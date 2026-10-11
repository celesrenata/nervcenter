#!/usr/bin/env python3
"""LocalStack capability probe for NerveCenter (NC-SPEC-2026-010, §10).

Read-only capability probe against the operator's own, authenticated
LocalStack environment.

Environment (read from the process environment ONLY -- never from files,
never from the network, never logged):

  LOCALSTACK_ENDPOINT    base URL (default: http://localhost:4566)
  LOCALSTACK_AUTH_TOKEN  optional token; if set it is sent as
                         ``Authorization: Bearer <token>`` on probe
                         requests and is NEVER written to any output.

Safety contract
---------------
* The token value is never persisted: not to stdout, not to the results
  file, not to any log. It is only ever transmitted on the wire.
* Every string destined for output passes through :class:`Redactor`,
  which strips the exact token value and generic credential patterns.
* Remote error bodies are reduced to an error class/code only. Message
  bodies are never persisted because AWS-style errors may echo request
  headers, which could contain tokens.
* No stack traces are printed; every check degrades to a classified
  result record.

Checks performed
----------------
1.  Endpoint reachability + ``GET /_localstack/health`` (service map).
2.  ``GET /_localstack/plan`` -- endpoint name is unverified against
    docs.localstack.cloud (the API reference does not document it); on
    HTTP 404 the check is recorded as ``unknown`` and the probe falls
    back to health + per-service probing. ``GET /_localstack/info`` is
    then recorded as a server-claimed informational fallback only.
3.  Per-service availability (S3, Lambda, EventBridge, SQS, SNS,
    StepFunctions, DynamoDB, IAM, CloudFormation) via boto3 when
    installed (lazy import), otherwise via raw HTTP checks with no
    SigV4 (the run is flagged ``boto3-missing``).
4.  ENFORCE_IAM detection: one deliberately deny-expected
    ``iam:CreateRole`` call; an AccessDenied-style response indicates
    IAM enforcement is active. This asserts nothing about plan tier.
    If no denial occurs the probe role is removed (best effort).
5.  Lifecycle CLI inventory: ``localstack`` binary presence
    (``shutil.which``) and advertised lifecycle subcommands
    (bootstrap/snapshot/reset/destroy/replay/export); ``unknown`` if
    the binary is absent.

Output
------
``tools/localstack/probe-results.jsonl`` -- one JSON object per check
(``ts``, ``check``, ``result``, ``detail_class``, safe extras) plus a
console summary. If the endpoint is unreachable the file is NOT
written (the README documents the blocked state instead).

Exit codes: 0 = probe executed, 2 = endpoint unreachable.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import quote

DEFAULT_ENDPOINT = "http://localhost:4566"
HTTP_TIMEOUT_S = 10
HEALTH_TIMEOUT_S = 5
RESULTS_PATH = Path(__file__).resolve().parent / "probe-results.jsonl"

# Lifecycle subcommands the README asks us to inventory.
LIFECYCLE_SUBCOMMANDS = ("bootstrap", "snapshot", "reset", "destroy", "replay", "export")

# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

# Conservative generic patterns: (compiled pattern, replacement).
# Applied in order; value side is replaced, key side kept.
_GENERIC_CREDENTIAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b(authorization)\s*:\s*(?:bearer\s+)?[^\s\"',;]+"),
        r" \1: [REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(authorization|token|secret|password|passwd|api[ _-]?key|access[_ -]?key|session[_ -]?token)\s*[=:]\s*[^\s\"',;]+"
        ),
        r" \1=[REDACTED]",
    ),
    (
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+"),
        r" Bearer [REDACTED]",
    ),
)


class Redactor:
    """Strips the localstack token value and generic credential patterns.

    The token value is only ever held in memory to detect and erase it;
    it is never rendered itself.
    """

    def __init__(self, token: str | None) -> None:
        self._token = token

    def redact(self, value: object) -> str:
        text = value if isinstance(value, str) else str(value)
        if self._token:
            text = text.replace(self._token, "[REDACTED]")
            text = text.replace(f"Bearer {self._token}", "Bearer [REDACTED]")
        for pattern, repl in _GENERIC_CREDENTIAL_PATTERNS:
            text = pattern.sub(repl, text)
        return text

    def safe(self, value: object) -> object:
        """Recursively redact every string in a JSON-like structure."""
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, dict):
            return {
                (self.redact(str(k)) if isinstance(k, str) else k): self.safe(v)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.safe(v) for v in value]
        return value


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

def _headers(token: str | None, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = dict(extra or {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def http_call(
    endpoint: str,
    method: str,
    path: str,
    token: str | None,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = HTTP_TIMEOUT_S,
) -> tuple[int, bytes, str]:
    """Perform one request. Returns (status, body, content_type). Raises
    URLError on connection-level failure (classified by the caller, not
    re-raised into output)."""
    url = endpoint.rstrip("/") + path
    req = urlrequest.Request(url, data=body, headers=_headers(token, headers), method=method)
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read(), str(resp.headers.get("Content-Type", ""))


def http_call_tolerant(
    endpoint: str, method: str, path: str, token: str | None,
    headers: dict[str, str] | None = None, body: bytes | None = None,
    timeout: float = HTTP_TIMEOUT_S,
) -> tuple[int, bytes, str, str]:
    """Like :func:`http_call` but converts HTTPError into
    (status, body, content_type, "") and connection failures into
    (-1, b"", "", "<exception-class>")."""
    try:
        status, resp_body, content_type = http_call(endpoint, method, path, token, headers, body, timeout)
        return status, resp_body, content_type, ""
    except HTTPError as err:  # response was received; status in err.code
        try:
            body = err.read()
        except Exception:
            body = b""
        content_type = str(err.headers.get("Content-Type", "")) if err.headers else ""
        return err.code, body, content_type, ""
    except URLError as err:
        reason = getattr(err, "reason", None)
        reason_cls = type(reason).__name__ if reason is not None else "URLError"
        return -1, b"", "", f"URLError:{reason_cls}"
    except Exception as err:  # e.g. socket.timeout
        return -1, b"", "", f"{type(err).__name__}"


# ---------------------------------------------------------------------------
# Result classification helpers
# ---------------------------------------------------------------------------

_XML_CODE = re.compile(r"<Code>\s*([^<]+?)\s*</Code>")
_JSON_TYPE = re.compile(r'"__type"\s*:\s*"([^"]+)"')
_JSON_CODE = re.compile(r'"(?:code|Code)"\s*:\s*"([^"]+)"')
_DISABLED_HINT = re.compile(r"is not enabled|not enabled|ServiceDisabled|InvalidServiceName", re.IGNORECASE)
_CREDENTIAL_LIKE = re.compile(
    r"(?i)\b(bearer|authorization|token|secret|password|api[ _-]?key|access[_ -]?key|session[_ -]?token)\b"
)


def error_class_from_body(body: bytes) -> str:
    """Extract ONLY an error class/code from a response body.

    The body itself is never returned or persisted.
    """
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return "unparseable-body"
    for pattern in (_XML_CODE, _JSON_TYPE, _JSON_CODE):
        match = pattern.search(text)
        if match:
            code = match.group(1).strip()
            # class names only: drop anything that looks like a sentence.
            if code and len(code) <= 64 and not _CREDENTIAL_LIKE.search(code):
                return code
    return "unclassified"


def is_service_disabled(body: bytes) -> bool:
    """In-memory classification only (never persisted)."""
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return False
    return bool(_DISABLED_HINT.search(text[:2000]))


def classify_http(status: int, body: bytes, conn_error: str) -> tuple[str, str]:
    """Return (result, detail_class) for a probe response.

    result in {available, unavailable, error-401, error-other, unknown}.
    detail_class is a raw error class/code only -- never a message body.
    """
    if conn_error:
        return "error-other", conn_error
    if 200 <= status < 300:
        return "available", f"http-{status}"
    if status in (401, 403):
        return "error-401", error_class_from_body(body) or f"http-{status}"
    if is_service_disabled(body):
        return "unavailable", error_class_from_body(body) or f"service-disabled-http-{status}"
    return "error-other", error_class_from_body(body) or f"http-{status}"


# ---------------------------------------------------------------------------
# Record bookkeeping
# ---------------------------------------------------------------------------

class Probe:
    def __init__(self, endpoint: str, token: str | None, redactor: Redactor) -> None:
        self.endpoint = endpoint
        self.token = token
        self.redactor = redactor
        self.records: list[dict[str, object]] = []

    def record(self, check: str, result: str, detail_class: str, **extra) -> dict[str, object]:
        entry: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "check": check,
            "result": result,
            "detail_class": detail_class,
        }
        for key, value in extra.items():
            if value is None:
                continue
            entry[key] = self.redactor.safe(value)
        self.records.append(entry)
        return entry


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_env(probe: Probe) -> None:
    probe.record(
        "env-endpoint",
        "configured",
        "env-var" if os.environ.get("LOCALSTACK_ENDPOINT") else "default",
        endpoint=probe.endpoint,
    )
    probe.record(
        "env-token",
        "set" if probe.token else "not-set",
        "env-var" if probe.token else "absent",
    )
    probe.record("env-python", "ok", sys.version.split()[0], python=sys.version.split()[0])


def check_boto3(probe: Probe) -> bool:
    try:
        import boto3  # type: ignore  # lazy optional import (may be absent)
        import botocore  # type: ignore

        probe.record("boto3-presence", "available", "import-ok", version=boto3.__version__)
        try:
            probe.records[-1]["botocore-version"] = botocore.__version__
        except Exception:
            pass
        return True
    except Exception as err:
        probe.record("boto3-presence", "boto3-missing", type(err).__name__)
        return False


def check_health(probe: Probe) -> dict[str, object] | None:
    status, body, _ct, conn_err = http_call_tolerant(
        probe.endpoint, "GET", "/_localstack/health", probe.token, timeout=HEALTH_TIMEOUT_S
    )
    if conn_err:
        probe.record("endpoint-health", "unreachable", conn_err)
        return None
    if 200 <= status < 300:
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
            services = payload.get("services", {})
            probe.record(
                "endpoint-health",
                "available",
                "http-200",
                features=payload.get("features", {}),
                services=services,
            )
            return payload
        except Exception:
            probe.record("endpoint-health", "available", "http-200-json-unparseable")
            return {}
    probe.record("endpoint-health", "error-other", error_class_from_body(body) or f"http-{status}")
    return {}


def check_plan(probe: Probe) -> bool:
    """GET /_localstack/plan.

    The endpoint name is NOT documented on docs.localstack.cloud (API
    reference page not found as of 2026-10-10) and returns HTTP 404 on
    the live instance, so a non-404 response would be treated as
    available-but-unverified and a 404 as ``unknown`` with fallback to
    health + service probing (per spec §10).
    """
    status, body, _ct, conn_err = http_call_tolerant(probe.endpoint, "GET", "/_localstack/plan", probe.token)
    if conn_err:
        probe.record("plan-endpoint", "error-other", conn_err)
        return False
    if status == 404:
        probe.record(
            "plan-endpoint",
            "unknown",
            "http-404",
            note="endpoint name unverified against docs.localstack.cloud; 404 on live instance; falling back to health + service probing",
        )
        return False
    if 200 <= status < 300:
        probe.record(
            "plan-endpoint",
            "available",
            "http-200",
            note="endpoint responded; name unverified against docs.localstack.cloud; payload not asserted as plan tier",
        )
        return True
    result, detail = classify_http(status, body, "")
    probe.record("plan-endpoint", result, detail)
    return False


def check_plan_info_fallback(probe: Probe) -> None:
    """GET /_localstack/info -- informational fallback ONLY.

    Fields are recorded verbatim as server claims; they do NOT verify
    plan tier or licensing terms (see README licensing section).
    """
    status, body, _ct, conn_err = http_call_tolerant(probe.endpoint, "GET", "/_localstack/info", probe.token)
    if conn_err:
        probe.record("plan-info-fallback", "error-other", conn_err)
        return
    if not (200 <= status < 300):
        probe.record("plan-info-fallback", "error-other", error_class_from_body(body) or f"http-{status}")
        return
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        probe.record("plan-info-fallback", "error-other", "json-unparseable")
        return
    probe.record(
        "plan-info-fallback",
        "server-claim",
        "http-200",
        server_version=payload.get("version"),
        server_edition_claim=payload.get("edition"),
        server_license_activated_claim=payload.get("is_license_activated"),
        note="server self-report via /_localstack/info; NOT a plan-tier verification; licensing per docs.localstack.cloud/aws/licensing/",
    )


RAW_PROBES: dict[str, tuple[str, str, dict[str, str], bytes | None]] = {
    "s3": ("GET", "/", {}, None),
    "lambda": (
        # NOTE: the emulator routes by the X-Amz-Target header, not the path;
        # a versioned path such as /2015-03-31/functions/ misroutes to
        # CreateFunction. Use the root path so ListFunctions is selected.
        "POST",
        "/",
        {"X-Amz-Target": "AWSLambda.ListFunctions", "Content-Type": "application/x-amz-json-1.1"},
        b"{}",
    ),
    "events": (
        "POST",
        "/",
        {"X-Amz-Target": "AmazonEventBridge.ListEventBuses", "Content-Type": "application/x-amz-json-1.0"},
        b"{}",
    ),
    "sqs": (
        "POST",
        "/",
        {"Content-Type": "application/x-www-form-urlencoded"},
        b"Action=ListQueues&Version=2012-11-05",
    ),
    "sns": (
        "POST",
        "/",
        {"Content-Type": "application/x-www-form-urlencoded"},
        b"Action=ListTopics&Version=2010-03-31",
    ),
    "stepfunctions": (
        "POST",
        "/2016-11-23/action/ListStateMachines",
        {"Content-Type": "application/x-www-form-urlencoded"},
        b"Action=ListStateMachines&Version=2016-11-23",
    ),
    "dynamodb": (
        "POST",
        "/",
        {"X-Amz-Target": "DynamoDB_20120810.ListTables", "Content-Type": "application/x-amz-json-1.0"},
        b'{"Limit":20}',
    ),
    "iam": (
        "POST",
        "/",
        {"Content-Type": "application/x-www-form-urlencoded"},
        b"Action=ListRoles&Version=2010-05-08",
    ),
    "cloudformation": (
        "POST",
        "/",
        {"Content-Type": "application/x-www-form-urlencoded"},
        b"Action=ListStacks&Version=2010-05-15",
    ),
}

BOTO3_LIST_CALLS = {
    "s3": lambda c: c.list_buckets(),
    "lambda": lambda c: c.list_functions(),
    "events": lambda c: c.list_event_buses(),
    "sqs": lambda c: c.list_queues(),
    "sns": lambda c: c.list_topics(),
    "stepfunctions": lambda c: c.list_state_machines(),
    "dynamodb": lambda c: c.list_tables(),
    "iam": lambda c: c.list_roles(),
    "cloudformation": lambda c: c.list_stacks(),
}

ACCESS_DENIED_CODES = {"accessdenied", "accessdeniedexception", "unauthorizedaccess", "forbidden"}


def probe_service_raw(probe: Probe, service: str) -> None:
    method, path, headers, body = RAW_PROBES[service]
    status, resp_body, _content_type, conn_err = http_call_tolerant(
        probe.endpoint, method, path, probe.token, headers, body
    )
    result, detail = classify_http(status, resp_body, conn_err)
    if result == "available" and not resp_body.strip():
        # An HTTP 200 with an empty body is ambiguous under raw HTTP: the
        # JSON-1.1 (Lambda/EventBridge) and query (StepFunctions) protocols
        # returned empty 200s that do not prove a real result payload.
        # Record Unknown and require a boto3 re-run for confirmation.
        result, detail = "unknown", "http-200-empty-body"
    probe.record(
        f"service-{service}",
        result,
        detail,
        probe_method="raw-http",
        note="raw-HTTP 200 with no result body; verify with boto3"
        if result == "unknown"
        else None,
    )


def probe_service_boto3(probe: Probe, service: str) -> None:
    import boto3  # type: ignore  # already verified present by check_boto3

    access_key = os.environ.get("AWS_ACCESS_KEY_ID") or "probe"
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY") or "probe"
    region = os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    try:
        client = boto3.client(
            service,
            endpoint_url=probe.endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        BOTO3_LIST_CALLS[service](client)
        probe.record(f"service-{service}", "available", "boto3-call-ok", probe_method="boto3")
    except Exception as err:  # noqa: BLE001 -- classify, never print
        cls = type(err).__name__
        code = ""
        try:  # botocore ClientError carries the AWS error code
            response = getattr(err, "response", None)
            if isinstance(response, dict):
                code = str(response.get("Error", {}).get("Code", "")).lower()
        except Exception:
            code = ""
        if code in ACCESS_DENIED_CODES or cls in ("ClientError",) and code:
            result = "error-401" if code in ACCESS_DENIED_CODES else "error-other"
        elif cls in ("NoAuthError", "PartialCredentialsError", "UnknownFingerprintException"):
            result = "error-401"
        else:
            result = "error-other"
        probe.record(
            f"service-{service}",
            result,
            f"{cls}:{code}" if code else cls,
            probe_method="boto3",
        )


def check_services(probe: Probe, boto3_present: bool) -> None:
    for service in RAW_PROBES:
        try:
            if boto3_present:
                probe_service_boto3(probe, service)
            else:
                probe_service_raw(probe, service)
        except Exception as err:  # defensive: a check must never abort the run
            probe.record(f"service-{service}", "error-other", type(err).__name__, probe_method="defensive")


def check_enforce_iam(probe: Probe) -> None:
    """One deliberately deny-expected iam:CreateRole.

    If AccessDenied-style is returned -> IAM enforcement active.
    If no denial -> a probe role is created; it is deleted best-effort
    immediately after. No plan tier is asserted.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    role_name = f"nc-cap-probe-deny-{stamp}"
    policy_doc = (
        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
        '"Principal":{"Service":"lambda.amazonaws.com"},'
        '"Action":"sts:AssumeRole"}]}'
    )
    form_body = (
        "Action=CreateRole&Version=2010-05-08"
        f"&RoleName={quote(role_name)}"
        "&Path=/"
        f"&AssumeRolePolicyDocument={quote(policy_doc, safe='')}"
    ).encode("utf-8")
    status, body, _ct, conn_err = http_call_tolerant(
        probe.endpoint,
        "POST",
        "/",
        probe.token,
        {"Content-Type": "application/x-www-form-urlencoded"},
        form_body,
    )
    if conn_err:
        probe.record("enforce-iam", "error-other", conn_err)
        return
    code = error_class_from_body(body).lower()
    if status in (401, 403) or code in ACCESS_DENIED_CODES:
        probe.record(
            "enforce-iam",
            "enforcement-detected",
            code or f"http-{status}",
            note="AccessDenied-style response; IAM enforcement appears active; no plan tier asserted",
        )
        return
    if status == 200:
        # Not denied: clean up the probe role we just created (best effort).
        delete_body = (
            "Action=DeleteRole&Version=2010-05-08"
            f"&RoleName={quote(role_name)}"
        ).encode("utf-8")
        d_status, d_body, _dct, d_err = http_call_tolerant(
            probe.endpoint,
            "POST",
            "/",
            probe.token,
            {"Content-Type": "application/x-www-form-urlencoded"},
            delete_body,
        )
        cleanup = "cleanup-ok" if (200 <= d_status < 300) else f"cleanup-{d_err or error_class_from_body(d_body) or d_status}"
        probe.record(
            "enforce-iam",
            "no-denial",
            f"created-and-{cleanup}",
            note="no AccessDenied; enforcement not detected from this probe; role name pattern nc-cap-probe-deny-*",
        )
        return
    probe.record("enforce-iam", "error-other", code or f"http-{status}")


def check_cli(probe: Probe) -> None:
    binary = shutil.which("localstack")
    if not binary:
        probe.record("cli-presence", "absent", "shutil.which-miss")
        probe.record(
            "cli-subcommands",
            "unknown",
            "cli-binary-not-on-PATH",
            note="lifecycle subcommands (bootstrap/snapshot/reset/destroy/replay/export) unverifiable",
        )
        return
    probe.record("cli-presence", "present", "shutil.which-hit", path=binary)
    try:
        out = subprocess.run(
            [binary, "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        help_text = (out.stdout or "") + (out.stderr or "")
        advertised = [name for name in LIFECYCLE_SUBCOMMANDS if re.search(rf"\b{re.escape(name)}\b", help_text)]
        probe.record(
            "cli-subcommands",
            "available" if advertised else "none-advertised",
            f"help-exit-{out.returncode}",
            advertised=advertised,
            checked=list(LIFECYCLE_SUBCOMMANDS),
        )
    except Exception as err:
        probe.record("cli-subcommands", "unknown", type(err).__name__)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    endpoint = os.environ.get("LOCALSTACK_ENDPOINT") or DEFAULT_ENDPOINT
    token = os.environ.get("LOCALSTACK_AUTH_TOKEN") or None
    redactor = Redactor(token)
    probe = Probe(endpoint, token, redactor)

    check_env(probe)

    health = check_health(probe)
    if health is None:
        # Unreachable: per spec the results file is NOT written; the
        # README documents the blocked state.
        print(redactor.redact(
            "BLOCKED: no reachable LocalStack instance "
            f"(endpoint {probe.endpoint} unreachable). "
            "Set LOCALSTACK_ENDPOINT to your instance and re-run. "
            "No probe-results.jsonl written."
        ))
        return 2

    check_plan(probe)
    check_plan_info_fallback(probe)
    boto3_present = check_boto3(probe)
    check_services(probe, boto3_present)
    check_enforce_iam(probe)
    check_cli(probe)

    # Write results (all strings redacted on the way in).
    with RESULTS_PATH.open("w", encoding="utf-8") as handle:
        for entry in probe.records:
            handle.write(json.dumps(entry, ensure_ascii=True, default=str) + "\n")

    # Console summary.
    print("LocalStack capability probe -- summary")
    print(f"endpoint: {redactor.redact(endpoint)}")
    print(f"token:    {'set (value never printed)' if token else 'not set'}")
    print(f"boto3:    {'present' if boto3_present else 'missing (raw-HTTP path)'}")
    print("-" * 64)
    for entry in probe.records:
        print(f"{entry['check']:<28} {entry['result']:<16} {entry['detail_class']}")
    print("-" * 64)
    print(f"results: {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
