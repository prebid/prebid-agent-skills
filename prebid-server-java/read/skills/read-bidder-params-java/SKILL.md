---
name: read-bidder-params-java
description: USE WHEN extracting the params section of a Java prebid-server adapter spec — reads `src/main/resources/static/bidder-params/{xyz}.json` VERBATIM, parses it for interpretation, reads the corresponding Java POJO `ExtImp{Xyz}.java` (Lombok-annotated) plus helper protos co-located in `proto/openrtb/ext/request/{xyz}/`, detects custom Jackson deserializers, and counts test methods in `{Xyz}BidderTest.java`.
version: 1.0.0
---

# read-bidder-params-java

Java-side counterpart of the Go `read-bidder-params` skill. Extracts the `params:` section of the Adapter Specification from a Java prebid-server bidder, plus the `bidder_params_ref` block that forms the **cross-language contract** with the Go side: the bidder-params JSON file is byte-identical across the two repos for the same bidder (port translation rule R5 in [`port-translation-rules.md`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.md)).

Two specs for the same bidder produced from each language MUST agree on `bidder_params_ref.sha256`, `bidder_params_ref.bytes`, and `params.schema_interpretation` (the JSON Schema interpretation is identical because the JSON is identical). They differ on `params.ext_struct` (Go struct vs Java POJO) and `params.params_test` (Go fixture-driven case counts vs Java JUnit method counts).

## Overview

This skill produces three sub-blocks of the spec:

- `bidder_params_ref:` — `{ path, resolved_commit, sha256, bytes }` for `src/main/resources/static/bidder-params/{xyz}.json`, with the fetched bytes staged at `../../test-fixtures/blobs/<sha256>`. The deprecated inline `bidder_params_json:` / `bidder_params_sha256:` pair stays schema-valid; nothing here depends on it.
- `params:` — three sub-blocks: `schema_interpretation` (normalized JSON Schema), `ext_struct` (the Java POJO file metadata), and `params_test` (the Java JUnit test file metadata). It also feeds the spec-level `ext_pojo_construction` block with `framework_choice`, `flexible_extension_used`, and `custom_unmarshal.{kind, accepts_shapes, where_branched}`.

The skill does NOT read the bidder class itself (`{Xyz}Bidder.java`) — that is the responsibility of `read-bidder-class`. The skill DOES read the proto/ POJO classes co-located in `proto/openrtb/ext/request/{xyz}/` since the params POJO and its helpers all live there.

Cross-link: canonical schema [`adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md), enumerations [`behavior-taxonomy.md`](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md), translation rules [`port-translation-rules.md`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.md).

## Inputs

The skill reads three Java-side files (all under `prebid-server-java/`):

1. **`src/main/resources/static/bidder-params/{xyz}.json`** — the JSON Schema. Fetched and digested by the single command in Step 1; the byte-identical file in `prebid-server-go/static/bidder-params/{xyz}.json` is the cross-language contract.

2. **`src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java`** plus any other classes in that directory (helpers like `ExtImp{Xyz}Param`, `ExtImp{Xyz}Banner`, `ExtImp{Xyz}Deserializer`, request/response payload classes for adapters with custom typed payloads). The directory is also referred to as the proto/ directory.

3. **`src/test/java/org/prebid/server/bidder/{xyz}/{Xyz}BidderTest.java`** — the JUnit test class. Counts `@Test` methods, distinguishing valid-usage tests (`should_*`, `make*ShouldReturn*`) from invalid-input tests (`should_returnError_when_*`, `*ShouldReturnError*`). Also reads (when present) `src/test/java/org/prebid/server/bidder/{xyz}/proto/...` test fixtures for proto-level POJO unit tests.

The skill must be invoked AFTER the orchestrator has resolved the commit and confirmed the file paths. The orchestrator passes the three paths plus the resolved commit SHA.

## Workflow

### Step 1 — Fetch and digest the JSON file in ONE command

Run exactly one command. It fetches `src/main/resources/static/bidder-params/{xyz}.json` at the resolved commit, stages the fetched bytes in the content-addressed blob store, and prints the `sha256` and `bytes` lines. Both numbers come out of the same pipe that fetched the file, so neither can be a measurement of the reader's own text (V2 in [`adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)).

Pick the line matching the orchestrator-supplied source mode, substitute `{xyz}` and the resolved commit, and record the stdout verbatim:

```bash
# local  (run inside the local prebid-server-java clone)
git show <commit>:src/main/resources/static/bidder-params/{xyz}.json | python3 -c 'import sys,hashlib,pathlib;b=sys.stdin.buffer.read();h=hashlib.sha256(b).hexdigest();d=pathlib.Path(sys.argv[1]);d.mkdir(parents=True,exist_ok=True);(d/h).write_bytes(b);print(f"  sha256: {h}\n  bytes: {len(b)}")' prebid-server-java/read/test-fixtures/blobs

# github-raw
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/<commit>/src/main/resources/static/bidder-params/{xyz}.json" | python3 -c 'import sys,hashlib,pathlib;b=sys.stdin.buffer.read();h=hashlib.sha256(b).hexdigest();d=pathlib.Path(sys.argv[1]);d.mkdir(parents=True,exist_ok=True);(d/h).write_bytes(b);print(f"  sha256: {h}\n  bytes: {len(b)}")' prebid-server-java/read/test-fixtures/blobs

# gh-cli
gh api "repos/prebid/prebid-server-java/contents/src/main/resources/static/bidder-params/{xyz}.json?ref=<commit>" --jq .content | base64 -d | python3 -c 'import sys,hashlib,pathlib;b=sys.stdin.buffer.read();h=hashlib.sha256(b).hexdigest();d=pathlib.Path(sys.argv[1]);d.mkdir(parents=True,exist_ok=True);(d/h).write_bytes(b);print(f"  sha256: {h}\n  bytes: {len(b)}")' prebid-server-java/read/test-fixtures/blobs
```

All three read the same Git object and print the same two numbers. Never fetch the bytes through a tool that summarizes content.

### Step 2 — Emit `bidder_params_ref`

Paste the two recorded lines under the reference block:

```yaml
bidder_params_ref:
  path: src/main/resources/static/bidder-params/{xyz}.json
  resolved_commit: <commit>
  sha256: <from Step 1 stdout>
  bytes: <from Step 1 stdout>
```

The blob staged by Step 1 at `../../test-fixtures/blobs/<sha256>` is the spec's copy of the bytes; a downstream `write/` skill reconstructs the file from the blob, so no chomping-style bookkeeping is needed.

This pair is the cross-language contract. The Go-side `read-bidder-params` skill runs its own Step 1 against `prebid-server-go/static/bidder-params/{xyz}.json` and MUST print the same `sha256` and the same `bytes`. A diff is a port-fidelity violation; the orchestrator surfaces it as a `bidder-params-sha-conflict` warning under `provenance.warnings`. Compare only after this reader's own command has produced its numbers.

Two verifications that prove nothing, and are prohibited:

- Hashing the value this skill emitted. A `sha256` over an emitted `bidder_params_json` compares the reader's output to itself: a span the reader dropped is missing from both sides, so the check passes on corrupt output.
- Copying a `sha256` or `bytes` from the Go-side spec, from a golden, from this SKILL, or from `adapter-spec.md`.

#### Encoding a verbatim scalar in YAML (V3)

`bidder_params_json` was **removed at `adapter_spec_version` 2.0.0** — `bidder_params_ref` plus the blob store carry the params bytes, so there is no inline params copy to encode. The probe below outlives the field because the trap is not specific to it: any verbatim scalar emitted inline (`properties[].description`, `user_sync`, fixture payloads) can lose a byte to the wrong YAML style, and the encoding is decided by a round-trip, NOT by defaulting to the literal block.

Run the probe against the bytes being embedded — here, the blob Step 1 staged:

```bash
python3 -c 'import sys,yaml;s=sys.stdin.buffer.read().decode();e=yaml.dump(s,default_style="|");print("encoding:","literal" if e.lstrip().startswith("|") and yaml.safe_load(e)==s else "double-quoted")' < ../../test-fixtures/blobs/<sha256>
```

- `literal` — emit the literal block scalar: `|` when the bytes end in a newline, `|-` when they do not.
- `double-quoted` — the literal block does not survive the round-trip. The double-quoted scalar with explicit escapes (`\n`, `\t`, `\r`, trailing spaces) MUST be used. Add a YAML comment naming the byte that forced it.

This is a required step, not a judgement call. The unconditional literal block this skill previously mandated cannot be trusted for files whose content lines carry a trailing space — the space is invisible in the block, and a hand-written block drops it. `beachfront.json` line 29 at master is that case, and the loss reached both language goldens.

If the bytes are not valid UTF-8, emit the reference only.

### Step 3 — Parse JSON for interpretation

Parse the JSON Schema — the blob Step 1 staged, not a re-fetch — and emit `params.schema_interpretation`:

- `properties[]` — each entry: `{ name, type, description }`. `description` is a **verbatim field** under V1 in [`adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4): it is the JSON Schema `description` string extracted from the blob (`python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["properties"]["<name>"].get("description"))' ../../test-fixtures/blobs/<sha256>`), never retyped, shortened, or summarized, and `null` when the schema declares none. `bidder_params_ref` is what makes the value re-derivable, so it must be present whenever `description` is. `type` is the JSON Schema type (`string`, `integer`, `boolean`, `number`, `object`, `array`) or, for flexible-type fields, an array (e.g., `["integer","string"]`).
- `required_fields[]` — field names listed under top-level `required:`. Empty list when no required fields.
- `flexible_types[]` — field names whose `type` is an array (e.g., `["integer","string"]`). Each entry: `{ name, accepted_types: [...] }`. These are the fields that drive port translation rule R9 (Go `jsonutil.StringInt`/`jsonutil.IntString` ↔ Java `Long` + `@JsonAlias` or custom `@JsonDeserialize`).
- `combinators_used[]` — JSON Schema combinators detected at any depth. Values from [`behavior-taxonomy.md#paramsschema_interpretationcombinators_used`](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md): `oneOf`, `anyOf`, `not`, `oneOf-of-oneOf` (nested oneOf), `json-aliases-present` (informational — populated only if the Java POJO carries `@JsonAlias`).

The interpretation is identical to the Go-side interpretation for the same bidder because the JSON file is byte-identical. If the two specs ever disagree on `schema_interpretation`, one of the readers has a bug.

### Step 4 — Read ext POJO file (and proto/ helpers)

Read `src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java` and emit `params.ext_struct`:

- `package: org.prebid.server.proto.openrtb.ext.request.{xyz}` (extracted from the `package` declaration).
- `file: src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java` (relative to repo root).
- `type_name: ExtImp{Xyz}` (extracted from the class declaration).
- `fields[]` — each entry: `{ name, json_tag, type_native, omitempty, notes[] }`. Detail rules below.
- `custom_unmarshal: true|false` — true when:
  - The class itself carries `@JsonDeserialize(using = {Xyz}Deserializer.class)`, OR
  - Any field in the class carries `@JsonDeserialize(using = ...)`, OR
  - A class in the proto/ directory `extends StdDeserializer<...>` or implements `JsonDeserializer<T>`.
- `custom_unmarshal_accepts[]` — extracted from the deserializer's `deserialize(JsonParser p, DeserializationContext ctxt)` method body. Look for `JsonNode.isArray()`, `isObject()`, `isTextual()`, `isNumber()` branches and record each as an accepted shape (`array`, `object`, `string`, `number`).

#### Field extraction rules

For each `private final {Type} {name}` declaration (Lombok @Value pattern) or `private {Type} {name}` (Lombok @Data pattern):

- `name` — the Java field name (camelCase per Java convention).
- `json_tag` — derived as follows:
  - If the field carries `@JsonProperty("...")`, use that exact string as the json_tag.
  - Otherwise, default to the Java field name (Lombok-style — Jackson serializes field names verbatim).
- `type_native` — the Java type as written: `String`, `Long`, `Integer`, `Boolean`, `BigDecimal`, `JsonNode`, `ObjectNode`, `List<X>`, `Map<K,V>`, `ExtImp{Xyz}Param`, etc.
- `omitempty` — Jackson's default is to include nulls unless `@JsonInclude(JsonInclude.Include.NON_NULL)` is on the class or field. If present, `omitempty: true`. If absent, `omitempty: false` (Jackson includes nulls).
- `notes[]` — a list of structural facts attached to the field. Add an entry for each:
  - `@JsonAlias({"a","b"})` — record `"@JsonAlias({\"a\",\"b\"}) — accepts legacy field names a, b"`. This is the Java mechanism for accepting multiple JSON key spellings on the SAME logical field. It is the typical Java-side answer to Go's `jsonutil.StringInt` / `jsonutil.IntString` flexible-type idiom (port translation rule R9).
  - `@JsonProperty(value = "...", required = true)` — record `"required at deserialization time"`.
  - `@JsonDeserialize(using = ...Deserializer.class)` — record `"custom deserializer: {class}"`.
  - `@JsonInclude(...)` — record the inclusion policy.
  - When the Java field type differs from the Go-side struct field type for the same JSON property (e.g., Go is `jsonutil.StringInt` but Java is `Long` + `@JsonAlias`), record `"flexible-type idiom mismatch with Go (R9): Go uses jsonutil.StringInt, Java uses Long + @JsonAlias"`.
  - When the field type is `JsonNode` rather than a typed POJO, record `"raw JsonNode — adapter parses at runtime"` (this typically pairs with `runtime-isobject-isarray-branching` in `ext_pojo_construction.custom_unmarshal.kind`).

#### Lombok framework_choice detection

Inspect the class-level annotations to determine `ext_pojo_construction.framework_choice`:

- `@Value` + `@Builder` (and optionally `@Jacksonized`) → `lombok-value-builder` (the most common Java pattern — gives an immutable POJO with builder API).
- `@Value(staticConstructor = "of")` → `lombok-value-staticconstructor` (Kobler's choice — gives `ExtImpKobler.of(true)` factory).
- `@Data` + `@NoArgsConstructor` → `lombok-data` (mutable POJO; rare for ExtImp because Jackson default-constructs and field-injects).
- No Lombok at all → `custom` (REQUIRES `quirks` entry).

Also detect:

- `extends FlexibleExtension` (or presence of `@JsonAnyGetter`/`@JsonAnySetter` on individual methods) → `ext_pojo_construction.flexible_extension_used: true`. This is the Java-side equivalent of preserving unknown JSON keys (Appnexus uses this for the `keywords` field).

#### custom_unmarshal kind detection

For `ext_pojo_construction.custom_unmarshal.kind`, choose from [`behavior-taxonomy.md#ext_pojo_constructioncustom_unmarshalkind`](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md):

- `none` — default. No `@JsonDeserialize`, no FlexibleExtension shape branching.
- `jackson-jsondeserialize` — `@JsonDeserialize(using = XyzDeserializer.class)` paired with a custom `JsonDeserializer<T>` class in proto/.
- `jackson-jsonalias-only` — only `@JsonAlias({...})` on individual fields (legacy field-name compatibility); no full deserializer.
- `runtime-isobject-isarray-branching` — the bidder class (NOT the deserializer) inspects `JsonNode.isArray() / isObject() / isTextual()` at runtime. Set `where_branched: bidder-class`. Appnexus keywords field uses this.

`where_branched` values:

- `jsondeserializer-class` — branching lives in a separate `JsonDeserializer<T>` class in proto/.
- `bidder-class` — branching lives in the bidder class (`{Xyz}Bidder.java`). The skill emits this only when explicit evidence is present in the proto/ POJO docstrings or `@JsonDeserialize` annotations pointing OUTSIDE proto/.
- `type-method` — Java equivalent of Go's UnmarshalJSON on the type itself (rare in Java; possible via custom `readObject`/`readResolve`).
- `null` — when `kind: none`.

### Step 5 — Read test file

Read `src/test/java/org/prebid/server/bidder/{xyz}/{Xyz}BidderTest.java` (the JUnit test class) and emit `params.params_test`:

- `file: src/test/java/org/prebid/server/bidder/{xyz}/{Xyz}BidderTest.java`.

Both counts are computed values under V4 in [`adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4) — the recorded number is a command's stdout, not a tally the reader kept while reading:

```bash
<fetch> | grep -oE 'void [A-Za-z0-9_]+' | grep -cE 'Error|Fail|Throw'    # invalid_cases_count
<fetch> | grep -c '^[[:space:]]*@Test'                                   # total; valid = total - invalid
```

- `valid_cases_count: <int>` — `@Test`-annotated methods whose name matches valid-usage patterns: `should_*` (positive), `make*ShouldReturn*` (positive expectation), `*ShouldReturnBid*`, `*ShouldUseDefault*`, etc. The exact pattern set is documented in [`references/schema-interpretation.md`](references/schema-interpretation.md); when the pattern set differs from the two greps above, run the pattern-specific `grep -c` and record ITS output.
- `invalid_cases_count: <int>` — `@Test`-annotated methods whose name matches invalid-input patterns: `should_returnError_when_*`, `*ShouldReturnError*`, `*ShouldFail*`, `creationShouldFailOn*`, `*ShouldThrow*`.
- The two counts must sum to the `grep -c '^[[:space:]]*@Test'` total. A discrepancy means a method matched neither pattern set: record the totals the commands returned and surface the `incomplete-classification` quirk per the reference, rather than adjusting either number.
- `bidder_constant_referenced: null` — Java does NOT have a bidder constant analog. Go uses `openrtb_ext.BidderXyz` enum-like constants in tests; Java uses YAML names directly as strings. The skill ALWAYS emits `null` here. The Go-only `bidder-constant-mismatch` warning under `provenance.warnings` does NOT apply on the Java side. (Cross-language note: a Java spec for the same bidder may carry a quirk recording the Go-side bug for cross-language port awareness — see Kobler golden, where the Java spec carries `bidder-constant-mismatch-test` quirks describing the Go-side mismatches.)

If the test class does not exist (alias bidders typically have only an integration test under `src/test/java/org/prebid/server/it/{Xyz}Test.java`), emit `params_test: { file: null, valid_cases_count: null, invalid_cases_count: null, bidder_constant_referenced: null }` and surface a `quirks` entry with taxon `incomplete-classification`.

### Step 6 — Populate ext_pojo_construction

Top-level `ext_pojo_construction` aggregates the facts from Step 4:

```yaml
ext_pojo_construction:
  framework_choice: lombok-value-builder | lombok-data | lombok-value-staticconstructor | custom
  flexible_extension_used: true | false
  custom_unmarshal:
    kind: none | jackson-jsondeserialize | jackson-jsonalias-only | runtime-isobject-isarray-branching | custom
    accepts_shapes: [array, object, string, number]
    where_branched: jsondeserializer-class | bidder-class | type-method | null
```

The `custom` value in either `framework_choice` or `custom_unmarshal.kind` REQUIRES a paired `quirks[]` entry (per validation rule R3 in [`adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md)).

## Edge case mapping

The skill handles these Java-specific patterns:

| Pattern | Detection | Spec field affected |
|---|---|---|
| `@JsonAlias({"oldName","altName"})` on a field | Field annotation list | `params.ext_struct.fields[].notes[]` + `combinators_used[]` includes `json-aliases-present` |
| `@JsonDeserialize(using = XyzDeserializer.class)` on a class | Class-level annotation | `ext_pojo_construction.custom_unmarshal.kind: jackson-jsondeserialize` + `where_branched: jsondeserializer-class` |
| `extends FlexibleExtension` | `extends` clause in class declaration | `ext_pojo_construction.flexible_extension_used: true` |
| `@JsonAnyGetter`/`@JsonAnySetter` on methods (without FlexibleExtension) | Method annotations | Same — `flexible_extension_used: true` |
| `@Value(staticConstructor = "of")` | Class annotation | `ext_pojo_construction.framework_choice: lombok-value-staticconstructor` |
| Field type `Long` paired with `@JsonAlias` for legacy-name compat | Field type + annotation | `notes: ["flexible-type idiom mismatch with Go (R9): Go uses jsonutil.StringInt, Java uses Long + @JsonAlias"]` |
| Field type `JsonNode` (raw passthrough) | Field type | `notes: ["raw JsonNode — adapter parses at runtime"]`; possible pair with `runtime-isobject-isarray-branching` |
| Multi-class proto/ split (custom request/response payload) | Multiple classes in proto/{xyz}/ | `params.ext_struct.file` lists primary `ExtImp{Xyz}.java`; helper classes recorded under `bidder_class.helper_classes_in_proto[]` (filled by `read-bidder-class`) |
| Test class missing (alias bidder) | File-not-found | `params_test: null` + `quirks: incomplete-classification` |

The Java side does NOT have an analog to the Go-side bidder-constant-mismatch warning (Go-only). The skill ALWAYS emits `bidder_constant_referenced: null` and SKIPS rule R7 of [`adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md).

For port translation rule R9 (`flexible-type idiom mismatch`), see [`references/schema-interpretation.md`](references/schema-interpretation.md).

## Cross-language note

The `bidder_params_ref` block is subject to the cross-language contract (port translation rule R5 in [`port-translation-rules.md`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.md)):

> The bidder-params JSON file at `static/bidder-params/{xyz}.json` is BYTE-IDENTICAL between `prebid-server` (Go) and `prebid-server-java` (Java). A diff between the two SHA-256 hashes is a port-fidelity violation.

The Java reader and the Go reader for the same bidder MUST produce:

1. Identical `bidder_params_ref.sha256`, each measured by that side's own Step 1 command.
2. Identical `bidder_params_ref.bytes` — the second witness, since a length cannot be reconstructed from a transcription the way a re-hash can.
3. Identical `params.schema_interpretation` content (because the JSON is identical), including verbatim `properties[].description` strings.

Where the readers may differ (and SHOULD differ):

- `params.ext_struct` — the language-specific POJO/struct backing the params. Go has `package: openrtb_ext`, Java has `package: org.prebid.server.proto.openrtb.ext.request.{xyz}`.
- `params.params_test` — Go counts JSON test-fixture cases (driven by `params_test.go`); Java counts JUnit `@Test` methods.
- `ext_pojo_construction.framework_choice` — Go always emits `go-struct`; Java emits one of the Lombok variants.

The orchestrator takes the digest from each side's Step 1 stdout independently and surfaces a `bidder-params-sha-conflict` warning under `provenance.warnings` when the two disagree (i.e., the Go and Java repos drifted out of sync). This is a non-blocking warning — the spec is still emitted, but the cross-language port pair flags a fidelity violation that the next reviewer must address.

## Verification

The Java kobler golden at [`prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml) is the reference output; its `bidder_params_ref` records the digest of the bidder-params file at the golden's pinned commit. The Go-side kobler golden at [`prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`](../../../../prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml) MUST carry the same `sha256` and `bytes`. Verify by running Step 1 against both repos at their pinned commits and comparing the two stdouts — do not read either value out of a golden and call it a check (V2).

Per-step verification:

1. **Upstream bytes preserved**: the blob at `../../test-fixtures/blobs/<sha256>` compares byte-equal (`cmp`) against the upstream file re-fetched at `resolved_commit`. Comparing an emitted inline scalar against its own digest is not this check — that comparison passed on a corpus golden that was 31 bytes short of upstream.
2. **Digest byte-equal to Go-side**: Step 1 run in the Java repo prints the same two lines as Step 1 run in the Go repo for the same bidder.
3. **All Lombok variants detected**: corpus tests cover `lombok-value-builder` (default), `lombok-value-staticconstructor` (Kobler), `lombok-data` (rare), and at least one `custom` case (when present).
4. **`@JsonAlias`, `@JsonDeserialize`, `FlexibleExtension` patterns detected**: corpus tests cover Appnexus (`FlexibleExtension`, `@JsonAlias`, `runtime-isobject-isarray-branching`).
5. **Java has no bidder-constant-mismatch warning**: the spec under `provenance.warnings` does NOT contain entries with type `bidder-constant-mismatch` for Java-side bugs. Cross-language quirks describing Go-side bugs ARE allowed under `quirks[]` for awareness (see Kobler Java golden).
6. **Goldens-comparable**: re-running the skill on the resolved commit produces a spec byte-identical to the golden modulo `provenance.read.timestamp_utc` and `provenance.read.operator` (per validation rule R4 of [`adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md)).

## Sources

- Canonical schema: [`prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md) (`bidder_params_ref:`, `params:` block, `ext_pojo_construction`, and rules V1-V4 for verbatim capture and computed values)
- Behavior taxonomy: [`prebid-server-go/read/skills/shared/behavior-taxonomy.md`](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md) (`combinators_used[]`, `framework_choice`, `custom_unmarshal.kind`, `where_branched`)
- Port translation rules: [`prebid-server-go/read/skills/shared/port-translation-rules.md`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.md) (R5 — bidder_params_json byte-identical contract; R9 — flexible-type idiom mismatch)
- Java kobler golden: [`prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml) (`bidder_params_ref` — read the golden for the pinned digest; do not transcribe it into a spec)
- Go counterpart: [`prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`](../../../../prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml) (same digest — cross-language contract)
- Java reference list with `Patterns Demonstrated`: [`prebid-server-java/references/new-bid-adapter-prs.md`](../../../../prebid-server-java/references/new-bid-adapter-prs.md) (Lombok-and-Jackson patterns under "Code & Adapter Patterns (Java-specific)")
- Sister Go skill (structural template, written in parallel): `prebid-server-go/read/skills/read-bidder-params/`
- This skill's reference: [`references/schema-interpretation.md`](references/schema-interpretation.md)
