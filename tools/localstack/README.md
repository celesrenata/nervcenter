# LocalStack capability probe (NC-SPEC-2026-010 §10)

Read-only capability probe for the NerveCenter AWS-sandbox requirement.
It runs against **the operator's own, authenticated LocalStack
environment** and records what is actually available, without printing
or persisting any credentials.

Status: **probe executed** — results in
[`probe-results.jsonl`](probe-results.jsonl). (If a future run finds no
reachable instance, the probe writes no results file and prints a
`BLOCKED` line; re-run with `LOCALSTACK_ENDPOINT` set to your instance.)

## Files

| File | Purpose |
| --- | --- |
| `probe.py` | The probe (stdlib only; lazy `boto3` import). |
| `probe-results.jsonl` | One JSON record per check: `ts`, `check`, `result`, `detail_class`, safe extras. |
| `README.md` | This document. |

## Usage

```sh
# Optional; only if your instance is not on the default endpoint.
export LOCALSTACK_ENDPOINT="http://localhost:4566"

# Optional; only if the emulator requires a plan token. NEVER echo this.
export LOCALSTACK_AUTH_TOKEN="$(get-token-from-your-credential-store)"

python3 tools/localstack/probe.py
```

- `LOCALSTACK_ENDPOINT` — base URL, default `http://localhost:4566`.
- `LOCALSTACK_AUTH_TOKEN` — optional. If set, it is sent as
  `Authorization: Bearer …` on probe requests and is **never written to
  any output** (stdout, results file, or logs). If unset, the probe runs
  unauthenticated, which is sufficient for an unauthenticated dev
  emulator.
- `boto3` is imported lazily. If it is installed, per-service probes use
  real boto3 calls (correct SigV4 when a token/credentials are present).
  If it is missing, the probe falls back to raw HTTP checks with **no
  SigV4** and records `boto3-missing`; raw results are valid for
  availability classification but weaker for auth-behavior questions.
- Exit code `0` = probe executed (results file written); `2` = endpoint
  unreachable (no results file written).

## Safety rules

1. **Never persist tokens.** The token is read from the environment only
   (never from files), transmitted only, and redacted from every output
   string. The probe additionally scrubs generic credential patterns
   (`Authorization: …`, `token=…`, `Bearer …`) from any value it records.
2. **Never expose the sandbox publicly.** The emulator must stay on a
   private/local network interface (e.g. `localhost`). Do not forward
   port 4566 to a public address; it emulates cloud APIs and, when
   unauthenticated, will execute operations against your local machine.
3. **Read-only intent.** The probe performs list/read operations only.
   The single write is the ENFORCE_IAM check: one deliberately
   deny-expected `iam:CreateRole` with a `nc-cap-probe-deny-*` name. If
   the emulator does not deny it (no IAM enforcement), the probe deletes
   the role it created (best effort). No other resources are created,
   modified, or deleted.
4. **No secrets in error output.** Remote error bodies are reduced to an
   error class/code only (e.g. `AccessDenied`, `InternalError`); message
   bodies are never recorded because AWS-style errors can echo request
   values. No stack traces containing environment values are printed.

## Probe checklist (what `probe.py` records, in order)

1. `env-endpoint` / `env-token` / `env-python` — configuration context
   (endpoint value, token *presence* only, Python version).
2. `endpoint-health` — `GET /_localstack/health`: readiness map and
   per-service `available/disabled/running` flags. Unreachable ⇒ probe
   stops with exit 2 and writes no results file.
3. `plan-endpoint` — `GET /_localstack/plan`. **The endpoint name is
   unverified**: docs.localstack.cloud's API reference does not document
   `/_localstack/plan` (reference pages returned 404 as of 2026-10-10)
   and the live instance answers HTTP 404. Per §10 the probe therefore
   records `unknown` and falls back to health + service probing.
4. `plan-info-fallback` — `GET /_localstack/info` (the documented
   internal endpoint): recorded as a **server self-report only**
   (`version`, `edition`, `is_license_activated` claims). It does not
   verify a plan tier or licensing terms.
5. `boto3-presence` — `available` / `boto3-missing`.
6. `service-{s3,lambda,events,sqs,sns,stepfunctions,dynamodb,iam,cloudformation}`
   — one probe per service: `ListBuckets`, `ListFunctions`,
   `ListEventBuses`, `ListQueues`, `ListTopics`, `ListStateMachines`,
   `ListTables`, `ListRoles`, `ListStacks`. Each records
   `available` / `unavailable` (service disabled by `SERVICES` config) /
   `error-401` (auth required/denied) / `error-other` / `unknown`, with
   only the raw error class. Two raw-HTTP caveats:
   - The emulator routes by the `X-Amz-Target` header, so Lambda is
     probed at `POST /`; a versioned path misroutes to `CreateFunction`.
   - The JSON-1.1 (S3, Lambda, EventBridge) and query (StepFunctions)
     protocols answer `200` with an **empty body** under SigV4-free raw
     HTTP, which does not prove a real result payload. Those are
     recorded `unknown` (detail `http-200-empty-body`) and must be
     confirmed by a boto3 run. Services with real result bodies (SQS,
     SNS, DynamoDB, IAM, CloudFormation) classify `available`/
     `unavailable` directly. The `endpoint-health` service map remains
     the authoritative availability signal in either case.
7. `enforce-iam` — the one deny-expected `iam:CreateRole`:
   `enforcement-detected` (AccessDenied-style ⇒ IAM enforcement active,
   **no plan tier asserted**) or `no-denial` (role created then cleaned
   up).
8. `cli-presence` / `cli-subcommands` — `localstack` CLI via
   `shutil.which`; advertised lifecycle subcommands checked from
   `--help`: `bootstrap`, `snapshot`, `reset`, `destroy`, `replay`,
   `export`. Recorded `unknown` if the binary is absent or help is
   unreadable.

## Licensing open questions

- **Plan tier unknown until verified.** The probe reports the server's
  self-claimed edition (`/_localstack/info`) and which services are
  enabled, but there is no machine-verifiable plan endpoint
  (`/_localstack/plan` → 404; name unverified in docs). The actual
  subscription tier must be confirmed from the operator's LocalStack
  account.
- **Shared-platform terms need consultation.** Per
  [docs.localstack.cloud/aws/licensing/](https://docs.localstack.cloud/aws/licensing/),
  current plans are Hobby (non-commercial), Base, Ultimate, Enterprise;
  "customers … use[d] primarily in automated environments or through
  shared infrastructure, such as an internal developer platform are
  encouraged to reach out to our sales team", and "Each workspace can
  only be assigned a single pricing plan". **NerveCenter's sandbox
  qualifies as a shared/automated platform, so its use case requires
  direct consultation with LocalStack (sales/licensing) before relying
  on the emulator for NC-sandbox features.** Until that is settled, the
  capability below is capability-only evidence, not a licensing
  clearance.
- The license token is a personal credential assigned to an individual
  user; it must never be committed, logged, or shared into the repo.

## Planned sandbox mapping (NerveCenter constructs)

| LocalStack service | NerveCenter construct | Conditions |
| --- | --- | --- |
| EventBridge (`events`) | NC Event | Direct: bus ≈ event channel; rule filters ≈ NC subscriptions. |
| Lambda | NC Function | Direct: one function ≈ one NC function execution; invoke ≈ NC invocation. |
| StepFunctions | NC Workflow | **Only via an explicit supported-construct mapping**: every NC workflow construct must be expressible in the StepFunctions ASL subset the sandbox supports (state types, integrations, retry/timeout semantics). Any NC construct without an explicit mapping is **unsupported** in the sandbox and must fail loudly (honest failure), not silently degrade. |
| SQS | (transport, not a NC construct) | Candidate event transport; availability must match `service-sqs` result. |
| SNS | (fan-out transport) | Disabled on the probed instance; treat as unavailable until `SERVICES` config changes. |
| S3 / DynamoDB | (storage backing) | Availability per probe results (S3 needs a boto3 run for list-level confirmation under raw HTTP); storage adapters already target S3/MinIO/LocalStack (see [`backend/storage/s3.py`](../../backend/storage/s3.py)). |
| IAM / CloudFormation | (provisioning/permission surface) | Probed for capability only; NC does not map constructs to these directly. |

Mapping rule: a construct is considered *sandbox-supported* only when
(i) the backing service probed `available`, (ii) for StepFunctions the
explicit construct mapping table covers the construct, and (iii) auth
behavior (ENFORCE_IAM) is understood — if enforcement is active, NC
sandbox clients must be provisioned with explicit least-privilege roles
instead of relying on anonymous access.
