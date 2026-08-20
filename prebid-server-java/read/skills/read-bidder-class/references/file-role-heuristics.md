# File Role Heuristics (Java)

Deterministic mapping rules from `src/main/java/org/prebid/server/bidder/{xyz}/**/*.java` filename to the `code.file_layout.files[].role` enum value. Consumed by [SKILL.md](../SKILL.md) Step 1.

The role enum (closed 5-value set, mirrors Go's 6-value enum minus `data-table` — `data-table` is Go-only because Java records IAB-category tables in YAML config (`iab_category_storage.storage_kind: yaml-inlined`) per ADR-001 D2 rather than a separate file): `implementation, models, parsers, types, utils`.

Cross-language counterpart: [../../../../../prebid-server-go/read/skills/read-adapter-code/references/file-role-heuristics.md](../../../../../prebid-server-go/read/skills/read-adapter-code/references/file-role-heuristics.md). The Java rules below intentionally produce the same role tags for analogous files so cross-language pair fixtures stay diffable.

---

## Rule order (deterministic)

For each `*.java` file under the bidder package (`src/main/java/org/prebid/server/bidder/{xyz}/**`), apply these rules in order. The FIRST matching rule wins.

| # | Pattern | Role | Notes |
|---|---|---|---|
| 1 | `{Xyz}Bidder.java` (the file declaring `class XyzBidder implements Bidder<T>`) | `implementation` | Always present; the bidder's main class. Holds `makeHttpRequests`, `makeBids`, the constructor wiring. Canonical: `AppnexusBidder.java`. |
| 2 | `*Validator.java`, `*Resolver.java`, `*Formatter.java`, `*Util.java`, `*Utils.java`, `*Helper.java` | `utils` | Generic helpers split out for organization. Canonical: `SameValueValidator.java` (appnexus); `HuaweiUtils.java`, `CountryCodeResolver.java`, `ClientTimeFormatter.java`, `HuaweiEndpointResolver.java` (huaweiads); `model/response/AdmUtils.java` (huaweiads — note the buried `model/response/` location). |
| 3 | `*Builder.java`, `*Parser.java`, `*Deserializer.java` | `parsers` | Builder helpers that construct request payloads OR custom Jackson deserializers. Canonical: `HuaweiAdmBuilder.java`, `HuaweiAdSlotBuilder.java`, `HuaweiAppBuilder.java`, `HuaweiDeviceBuilder.java`, `HuaweiNetworkBuilder.java` (huaweiads). |
| 4 | Files under `proto/` subpackage where `bidder_class.parameterized_request_type == BidRequest` (standard OpenRTB wire-format) | `models` | OpenRTB-extension POJOs: `ExtImp{Xyz}`, `BidExt{Xyz}`, `ImpExt{Xyz}`, `KeyVal`, `ReqExt`, etc. Canonical: appnexus `proto/AppnexusBidExt.java` and siblings. |
| 5 | Files under `proto/request/` or `proto/response/` subpackages where `bidder_class.parameterized_request_type ≠ BidRequest` (custom wire-format adapter) | `types` | Custom adapter request/response type definitions. Canonical: rubicon `proto/request/RubiconExtPrebidBidders.java` and siblings (full custom OpenRTB-like type tree). |
| 6 | Files under `request/` or `response/` subpackages (no `proto/` parent) where the adapter has a custom wire-format | `types` | Same intent as Rule 5 but for adapters that don't use a `proto/` namespace. Canonical: mediasquare `request/MediasquareRequest.java`, `response/MediasquareResponse.java`. |
| 7 | Param-ext POJO at the cross-package location `src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java` | `models` | Tagged `models` even though it lives outside the bidder package. Recorded in `file_layout.files[]` with a `..` -prefixed relative path. Canonical: appnexus `../../proto/openrtb/ext/request/appnexus/ExtImpAppnexus.java`. |
| 8 | Any other `*.java` file in the bidder package not matching Rules 1–7 | role: emit as a `quirks[]` entry for human review (taxon: `unclassifiable-bidder-package-file`) | Catch-all. The corpus at the pinned commits has none. |

**Tie-breaking**: the first matching rule wins. Rules 1–7 are exclusive. Rule 8 is a defensive catch-all that fires only on novel layouts.

**Multi-suffix collisions**: a file like `XyzKeyValBuilder.java` matches both Rule 3 (`*Builder.java` → `parsers`) and the implicit "anything proto-extension-shaped" hint. Rule 3 wins because rule order is deterministic and Builder-suffix takes precedence over location-based classification when both apply. If a future bidder ships such a file under `proto/` and the human reviewer wants it tagged `models` instead, that override goes through `quirks[]` plus an ADR amendment to add the file to the appropriate role family.

---

## LOC counting

`loc` is a computed value under V4 in [`../../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4): it is the stdout of one command run against the bytes at `provenance.source.resolved_commit`.

```bash
<fetch> | wc -l
```

Blank lines, comments, license headers, and import blocks all count. `wc -l` counts `\n` occurrences, so a file with no terminal newline reports one less than its visible line count — record what the command prints, without a correction term, and leave the terminal-newline question to the `bytes` witness on that file's reference. Record as `code.file_layout.files[].loc`. Examples (each reproducible with the command above):

- `src/main/java/org/prebid/server/bidder/appnexus/AppnexusBidder.java:553` at e3ffd57 (appnexus golden spec). LOC drifts with upstream, so the pin is part of the claim — this example read 561 against an earlier commit.
- `src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java` — run the command; the Go-side counterpart `kobler.go` prints 177. LOC is per-file, so the two languages are not expected to agree, and neither number may be copied from the other spec.

---

## Multi-file detection

`code.file_layout.kind`:

- `single-file` if the bidder package contains ONLY the implementation file (no `proto/`, no helpers, no parsers, no custom-wire types).
- `multi-file` otherwise.

The kind is computed over bidder-package files PLUS the param-ext POJO at the cross-package location (Rule 7). Files outside both — `spring/config/bidder/{Xyz}Configuration.java`, `bidder-config/{xyz}.yaml`, `test/**/*.java` — do NOT count toward `file_layout.kind`. They surface elsewhere:

- `XyzConfiguration.java` → consumed by Step 3 (`spring_config.*` extraction); never recorded in `file_layout.files[]`.
- `bidder-config/{xyz}.yaml` → consumed by `read-bidder-config` skill via orchestrator merge.
- Test files (`*IT.java`, `*Test.java`) → consumed by Step 10 (`tests.*` extraction); recorded under `tests.fixture_inventory.integration[]` and `tests.integration_test_class`.

Counts for the canonical pattern (most adapters):

- 1 × `implementation` — always present.
- 0+ × `models` — proto/* (most common — ExtImp, BidExt, ImpExt POJOs).
- 0+ × `utils` — validators, helpers, formatters, resolvers.
- 0+ × `parsers` — builders, custom deserializers.
- 0+ × `types` — custom wire-format types (rare; only when `parameterized_request_type ≠ BidRequest`).

The 19 Java goldens at the pinned commits distribute as: 14 single-file (just `implementation`), 5 multi-file (appnexus, huaweiads, mediasquare, rubicon, kobler).

---

## Cross-language alignment (vs. Go)

| Java role | Go role | Notes |
|---|---|---|
| `implementation` | `implementation` | Same — the bidder's main entry-point file. |
| `models` | `models` | Java has more `models` files due to the `proto/*` sub-package convention (ExtImp/BidExt POJOs). Go uses `bidder.go` to declare the same shapes inline. |
| `parsers` | `parsers` | Both languages tag custom-deserialization helpers here. |
| `types` | `types` | Used when the wire-format is NOT standard OpenRTB. Java canonical: mediasquare, rubicon. Go canonical: similar adapters using `structs.go`/`models.go` for non-OpenRTB wire shapes. |
| `utils` | `utils` | Generic helpers split out. |
| n/a | `data-table` | Go-only — Java records IAB category tables as `iab_category_storage.storage_kind: yaml-inlined` (no separate file) per ADR-001 D2. |

When a cross-language pair is being read, the role tags should match for analogous files. R5 and Rule 36 (test fixture inventory parity) consume `file_layout.files[].role` as part of their structural-parity checks; mismatched roles for analogous files surface as warnings.

---

## Edge cases

1. **Aliases (`meta.is_alias: true`)** — alias goldens may have empty `code.file_layout.files[]` because aliases inherit the parent's code. The lint script (`scripts/lib/lint-java-roles.py`) treats empty `file_layout` on an alias as PASS, on a non-alias as WARN.

2. **Nested helper packages** — files like `huaweiads/model/response/AdmUtils.java` use a deeper path. Tag by Rule 2 (`*Utils.java` → `utils`); the path depth doesn't change the role.

3. **Multi-suffix files** — see "Multi-suffix collisions" above. Rule order is the tie-breaker.

4. **Non-OpenRTB wire-format detection** — driven by `bidder_class.parameterized_request_type`. If it's `BidRequest` (default), use Rule 4 for proto/* files (`models`). If it's a custom type (e.g., `MediasquareRequest`, `HuaweiAdsRequest`), use Rule 5 or Rule 6 (`types`).

5. **Unclassifiable files** — Rule 8 catch-all. Emit a `quirks[]` entry with taxon `unclassifiable-bidder-package-file` and a free-text summary describing why no rule fired. Record the file with `role: null` in `file_layout.files[]`.

---

## Sources

- [SKILL.md](../SKILL.md) Step 1 — file inventory.
- [../../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md) — full schema reference for `code.file_layout.*`.
- [../../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json](../../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json) (`$defs/Code`) — JSON Schema declaration.
- Go counterpart: [../../../../../prebid-server-go/read/skills/read-adapter-code/references/file-role-heuristics.md](../../../../../prebid-server-go/read/skills/read-adapter-code/references/file-role-heuristics.md).
- Lint script: [../../../../../scripts/lib/lint-java-roles.py](../../../../../scripts/lib/lint-java-roles.py) — gates the enum at CI time.
