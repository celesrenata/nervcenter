# `nc://` Canonical Resource URI Grammar

**Status:** Frozen (Phase 1 contracts freeze, NC-WS-001 / T002) · **Date:** 2026-10-11
**Spec:** NC-SPEC-2026-010 §3 (canonical resource identity) · **Backed by:** ADR-0001
**Grammar version:** `nc-grammar v1`

This document freezes the exact BNF production for the canonical `nc://`
resource URI required by spec §3 ("the exact BNF production is a C1 contracts
deliverable"). Every discoverable resource is addressable by exactly one
canonical `nc://` URI (NC-REQ-001); the URI is the stable identity of the
resource across connector restarts and re-discovery.

---

## 1. Version header

The grammar production is versioned. Every normative artifact that states this
grammar (schemas, validators, console help text) must carry the header:

```
nc-grammar v1
```

A grammar version bump is a contract break: it requires a new C1-phase ADR and
an explicit migration for already-issued URIs. URIs minted under a frozen
version are stable forever; renaming is handled by aliases, never by
reissuing URIs (ADR-0001).

## 2. Production (frozen, `nc-grammar v1`)

```
nc-uri        = "nc://" namespace "/" provider "/" scope "/" kind "/" resource-id
namespace     = "personal" / "shared" / "system" / task-namespace
provider      = unreserved
scope         = unreserved
kind          = unreserved
resource-id   = rid-segment *( "/" rid-segment )
rid-segment   = 1*( unreserved / sub-delims / pct-encoded )
```

Normative form (what the registry and the `NCResource.uri` field carry):

```
nc://<namespace>/<provider>/<scope>/<kind>/<resource-id>
```

- **`namespace`** — isolation boundary (spec §3 `Namespace`; §10 rule 6).
  Reserved literals: `personal`, `shared`, `system`; plus task namespaces
  `<task>` (opaque tokens matching `unreserved`, e.g. an idea/experiment id)
  that must not collide with the reserved literals or with any other
  namespace already registered.
- **`provider`** — the connector instance's *provider id* (e.g. `homeassistant`,
  `gmail`). This is the connector kind's provider identifier as registered in
  the platform; it is **never** a connector-instance id (those carry a
  `conn_` prefix) and never a free-form display name.
- **`scope`** — connector-instance-scoped path segment (e.g. `home`,
  `account-work`). This is the unit of identity isolation *within* a provider
  (e.g. which Gmail account, which HA instance), fixed at registration and
  part of the canonical identity.
- **`kind`** — the connector kind id (e.g. `devices`, `threads`, `dashboards`):
  the class of thing the provider exposes.
- **`resource-id`** — the provider-native id, path-escaped. It may span
  multiple `/`-separated segments to mirror a provider-native hierarchical id
  (e.g. `accounts/primary/threads/abc`); segment boundaries in the resource-id
  are meaningful and preserved.

### Segment character sets (RFC 3986 terminology)

```
unreserved    = ALPHA / DIGIT / "-" / "." / "_" / "~"
sub-delims    = "!" / "$" / "&" / "'" / "(" / ")" / "*" / "+" / "," / ";" / "="
pct-encoded   = "%" HEXDIG HEXDIG   ; uppercase hex digits
```

`namespace`, `provider`, `scope`, and `kind` are single segments of
`unreserved` only. `rid-segment` additionally allows `sub-delims` and
`pct-encoded`. All segments are **non-empty**.

## 3. Case sensitivity

Per spec §3, the URI **scheme, authority position, and every path segment are
case-sensitive**. `NC://personal/...` and `nc://Personal/...` are different
(different, and invalid) URIs. The scheme must be exactly lowercase `nc`.
Providers and namespaces minted in a different case are different identities —
registry reconciliation must not case-fold (NC-MS-001 "two Gmail identities,
no leak").

## 4. Reserved segments

The following tokens are reserved by the platform and are **forbidden** as
`provider`, `scope`, or `kind` values (and as any `rid-segment`):

| Token | Reason |
|---|---|
| `nc` | scheme name; never a segment value |
| `*` | wildcard policy/action syntax (NC-CAP-007); wildcard URIs are forbidden |
| `null`, `undefined`, `none` | null-token leakage |
| `__system` | reserved internal prefix |

Reserved literal `namespace` values (`personal`, `shared`, `system`) may not
be reused as task namespaces. Segment values consisting solely of dots (`..`)
or tildes are rejected (path-normalization ambiguity).

## 5. Validation (frozen regex)

The canonical URI matches exactly:

```
^nc://(personal|shared|system|[A-Za-z0-9\-._~]+)/[A-Za-z0-9\-._~]+/[A-Za-z0-9\-._~]+/[A-Za-z0-9\-._~]+/(?:[A-Za-z0-9\-._~!$&'()*+,;=]+|%[0-9A-F]{2})+(?:/(?:(?:[A-Za-z0-9\-._~!$&'()*+,;=]+|%[0-9A-F]{2})+))*$
```

with case-sensitive matching (no case-folding flag), in addition to the
reserved-segment check of §4. Implementation: [`schemas/nc_platform.py`](../../schemas/nc_platform.py)
(`NcUriValidator`), which mirrors this regex and adds the reserved-segment
denial list.

## 6. Round-trip rules

A URI must round-trip losslessly through
`parse → (namespace, provider, scope, kind, resource-id) → build`:

1. **Exact provider ids preserved.** The `provider` segment is reproduced
   byte-for-byte on rebuild; no normalization, lowercasing, or alias
   substitution is permitted anywhere in parse or build.
2. **Path escaping.** `build()` percent-encodes each `rid-segment` character
   outside the `unreserved` / `sub-delims` set as `%XX` (uppercase hex, UTF-8
   bytes); `%` itself is encoded as `%25`. `parse()` reverses exactly one
   layer of percent-decoding. A URI containing a double-encoded sequence
   (e.g. `%252F`) is a different, valid resource-id — it is *not* an error.
3. **Tombstone = alias kept, resource tombstoned, never deleted.** When a
   resource disappears from its provider, the registry marks
   `sync_status = "tombstoned"` on the canonical row (the `nc://` URI and all
   its `ResourceAlias` rows remain resolvable); the row is **never** deleted
   (NC-REQ-008: outage → stale status, not deletion). `parse()` of a
   tombstoned URI succeeds; registry resolution returns the row with its
   tombstone state. Alias re-mapping to a *new* canonical URI is only the
   reconciliation path (ADR-0001 decision records).
4. **Resolution without live contact.** Parsing is a pure function; resolution
   (alias → canonical URI, relations, latest snapshot) is served entirely
   from registry data (spec §3: "resolvable from the registry without live
   connector contact").

## 7. Examples (from spec §3 + §11 connectors)

```
nc://personal/homeassistant/home/devices/bedroom-lamp
nc://personal/gmail/account-work/threads/abc
nc://shared/grafana/account-work/dashboards/infra-overview
nc://system/prometheus/home/dashboards/alerts
nc://personal/homeassistant/home/devices/kitchen/door-lock
nc://shared/omniroute/system/routes/claude-hybrid-code
```

Parse of the spec example `nc://personal/homeassistant/home/devices/bedroom-lamp`:

| Segment | Value |
|---|---|
| namespace | `personal` |
| provider | `homeassistant` |
| scope | `home` |
| kind | `devices` |
| resource-id | `bedroom-lamp` |

## 8. Error cases

Each failure is a *different* error class; a validator must report which one
applied (never a generic "invalid URI"):

| # | Input | Error |
|---|---|---|
| 1 | `http://personal/homeassistant/home/devices/x` | wrong scheme (only `nc`) |
| 2 | `NC://personal/homeassistant/home/devices/x` | scheme must be lowercase |
| 3 | `nc://homeassistant/home/devices/bedroom-lamp` | missing namespace (4 path segments expected before resource-id) |
| 4 | `nc://personal/homeassistant/home/devices/` | empty resource-id |
| 5 | `nc://personal//home/devices/x` | empty provider segment |
| 6 | `nc://personal/Homeassistant/home/devices/x` | distinct identity; rejected on registration unless `Homeassistant` is a registered provider (case-sensitive) |
| 7 | `nc://personal/* /home/devices/x` | reserved segment `*` (wildcard URIs forbidden) |
| 8 | `nc://personal/gmail/account-work/threads/..` | dot-only segment rejected (normalization ambiguity) |
| 9 | `nc://personal/gmail/account-work/threads/%zz` | malformed percent-encoding |
| 10 | `nc://personal/gmail//threads/abc` | empty scope |
| 11 | `nc://personal/homeassistant/home/ devices/x` | space is not in any segment character set |

## 9. This is NOT an AWS ARN

`nc://` URIs are deliberately *not* modeled on AWS ARNs (`arn:aws:<service>:
<region>:<account>:<type>/<id>`):

- No account/region axis — `nc://` identifies platform-native resources; the
  connector scope (`home`, `account-work`) is the isolation unit, not an
  AWS account id.
- The colon-delimited ARN positional grammar is replaced by a `/`-delimited,
  case-sensitive, grammar-versioned production (§2) whose segments are
  independently registered in the platform registry.
- Where LocalStack (NC-CAP-010) or AWS S3 appear, they are *provider
  instances behind* a connector; their native ids appear only inside the
  path-escaped `resource-id`, never in the URI structure. Sandbox and
  production identities are never conflated (NC-REQ-009).
