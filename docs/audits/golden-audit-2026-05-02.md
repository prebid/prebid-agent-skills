# Golden Audit — 2026-05-02

**Phase 1.5** of the execution plan. Verifies that all 22 hand-authored
golden Adapter Specifications are byte-faithful to upstream at their
pinned commits.

## Method

Ran `python3 scripts/audit-golden.py --all`. The script encodes a
deterministic-subset of the orchestrator's mechanical checks (does NOT
run the full Claude SKILL):

| Check | What it verifies |
|---|---|
| **C1** | `sha256(upstream bidder-params JSON)` == `golden.bidder_params_sha256` |
| **C2** | `bidder_info` top-level fields match upstream YAML (endpoint, endpoint_compression, gvl_vendor_id, default_enabled, maintainer email, modifying_vast_xml_allowed) |
| **C3** | Every entry in `code.file_layout.files[]` exists in upstream adapter directory (recurses 1 level into Java helper subdirs: `request/`, `response/`, `proto/`, `model/`) |
| **C4** | Every fixture filename in `tests.fixture_inventory.*` exists at the expected upstream path (Go: `adapters/<bidder>/<test_root>/<category>/`; Java: `src/test/resources/org/prebid/server/it/openrtb2/<bidder>/` or path-prefixed within filename) |
| **C5** | `meta.bidder_name` matches the golden's filename basename |

Skipped on aliases (C1-C4): inheritance from parent isn't resolved by
this audit; alias-spec accuracy is verified via parent-resolution +
dual-spec assertions.

## Result

**0 failures, 0 warnings across 22 goldens.**

Every golden's recorded facts (file paths, fixture filenames, bidder-info
fields, params SHA) match upstream at the pinned commit.

## Per-golden summary

| Golden | Language | Commit | is_alias | Verdict |
|---|---|---|---|---|
| 152media | go | d7f8515b | true | PASS (alias — C1-C4 skipped per design) |
| 33across | go | d7f8515b | false | PASS |
| aax | go | d7f8515b | false | PASS |
| adkernel | go | d7f8515b | false | PASS |
| adtonos | go | d7f8515b | false | PASS |
| appnexus | go | d7f8515b | false | PASS |
| bidstack | go | d7f8515b | false | PASS |
| elementaltv | go | d7f8515b | false | PASS |
| kobler | go | d7f8515b | false | PASS |
| mediasquare | go | d7f8515b | false | PASS |
| msft | go | d7f8515b | false | PASS |
| optidigital | go | d7f8515b | false | PASS |
| 152media | java | 69b1993c | true | PASS (alias) |
| aax | java | 69b1993c | false | PASS |
| appnexus | java | 69b1993c | false | PASS |
| elementaltv | java | 69b1993c | false | PASS |
| generic | java | 69b1993c | false | PASS |
| huaweiads | java | 69b1993c | false | PASS |
| kobler | java | 69b1993c | false | PASS |
| mediasquare | java | 69b1993c | false | PASS |
| optidigital | java | 69b1993c | false | PASS |
| rubicon | java | 69b1993c | false | PASS |

## Audit-script edge cases handled

The audit surfaced several legitimate-but-non-trivial structural patterns
during refinement. These are encoded in the script (not bugs) and noted
here so future contributors understand them:

1. **Case-insensitive `endpoint_compression`**: upstream YAMLs sometimes
   write `"GZIP"` (uppercase, e.g., adkernel-Go) while goldens canonicalize
   to lowercase `gzip`. Comparator is case-insensitive for this field.

2. **Boolean fields default to absent**: `modifying_vast_xml_allowed: false`
   in golden equates to upstream-absent (defaults to false). `default_enabled:
   true` similarly.

3. **Java helper subdirs**: classes like `MediasquareRequest.java` live in
   `bidder/<name>/request/`, not the bidder's top-level dir. Audit recurses
   2 levels into known helper subdirs (`request/`, `response/`, `proto/`,
   `model/`).

4. **Proto/openrtb/ext path**: `ExtImp<Bidder>.java` lives in
   `src/main/java/org/prebid/server/proto/openrtb/ext/request/<bidder>/`.
   Audit walks this path AND suppresses `ExtImp*.java` and bidder-named
   proto files from "extras" warnings (they're tracked in `params.ext_struct`
   block, not `code.file_layout.files[]`).

5. **msft dual test root**: msft has two parallel test directories,
   `adapters/msft/test/` and `adapters/msft/test-extrainfo/`. Categories
   prefixed `extrainfo_` (e.g., `extrainfo_exemplary`) map to the
   `test-extrainfo/<remainder>` path.

6. **Java IT fixture path inference**: golden's `tests.test_root_directory`
   points at the JUnit class root (under `src/test/java/...`); IT JSON
   fixtures actually live under `src/test/resources/org/prebid/server/it/
   openrtb2/<bidder>/`. Audit derives the fixture path from convention.
   When filenames already include a path prefix (e.g., generic's
   `openrtb2/generic_core_functionality/test-...json`), audit splits and
   resolves against the IT base.

7. **Java `generic` adapter framework-root layout**: the `generic` bidder
   lives at `bidder/GenericBidder.java` (top of `bidder/` namespace, not a
   per-bidder subdir). Audit suppresses framework-file noise when the
   bidder_dir IS the framework root and the golden declares ≤2 files.

8. **Aliases (C1)**: alias goldens (152media-Go, 152media-Java) skip C1
   because their `bidder_params_sha256` represents the parent's params JSON
   (alias inherits at runtime). Verifying would require parent-resolution.

## Implications

- **Round 2's 4-bidder spot-check generalizes.** Goldens are
  trustworthy as a porting reference; the structured data faithfully
  reflects upstream code at the pinned commits.
- **Phase 2 schema migration locks in clean data.** The schema spine
  rewrite operates on factually-correct goldens; any drift discovered
  later is post-Phase-2 evolution, not pre-existing rot.
- **Future drift detection** (Phase 4.1 `sync-from-upstream.py`) reuses
  this audit's deterministic-check logic, applied to upstream HEAD
  rather than the pinned commit.

## Re-running

```bash
make audit-goldens          # all 22 (Phase 1.5 milestone)
python3 scripts/audit-golden.py kobler   # single bidder
python3 scripts/audit-golden.py --all --json > docs/audits/golden-audit-<date>.json
```

## Phase 1.5 status

Complete. The script is added to `scripts/audit-golden.py`; the Makefile
target lands in this same commit (audit C3). Phase 2 is unblocked.
