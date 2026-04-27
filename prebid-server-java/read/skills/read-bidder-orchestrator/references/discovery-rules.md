# Discovery Rules (Java)

File globs the orchestrator uses to discover a Java bidder's artifacts. Used in Workflow Step 2. All paths are relative to the prebid-server-java repository root and resolved at `provenance.source.resolved_commit`.

The discovery substitution variable `{xyz}` is the lowercase YAML name (e.g., `kobler`, `feedad`, `152media`). The TitleCase class root `{Xyz}` follows Java identifier rules with two known workarounds documented below.

## File globs (per domain)

| Domain | Glob | Required? | Read-by skill |
|---|---|---|---|
| Bidder class (main) | `src/main/java/org/prebid/server/bidder/{xyz}/{Xyz}Bidder.java` | yes (unless alias) | `read-bidder-class` |
| Bidder helper classes (co-located) | `src/main/java/org/prebid/server/bidder/{xyz}/*.java` (all `.java` files in the dir other than `{Xyz}Bidder.java`) | optional | `read-bidder-class` |
| Spring `@Configuration` | `src/main/java/org/prebid/server/spring/config/bidder/{Xyz}Configuration.java` (canonical) OR `{Xyz}BidderConfiguration.java` (variance — Adverxo, Connatix) | yes (unless alias) | `read-bidder-class` |
| Unified bidder YAML | `src/main/resources/bidder-config/{xyz}.yaml` | yes | `read-bidder-config` |
| Bidder params JSON | `src/main/resources/static/bidder-params/{xyz}.json` | yes | `read-bidder-params-java` |
| Ext-imp proto class | `src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java` | optional (none for free-form-imp-ext like Ogury) | `read-bidder-params-java` |
| Other proto helper classes | `src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/*.java` (all `.java` files in the dir other than `ExtImp{Xyz}.java`) | optional | `read-bidder-params-java` (if request-related) or `read-bidder-class` (if response-related, e.g., Mediasquare custom response DTOs) |
| Unit test class | `src/test/java/org/prebid/server/bidder/{xyz}/{Xyz}BidderTest.java` | strongly recommended | `read-bidder-class` (unit-test-method count + LOC) |
| Integration test class (main) | `src/test/java/org/prebid/server/it/{Xyz}Test.java` | strongly recommended | `read-bidder-class` |
| Integration test classes (per-alias) | `src/test/java/org/prebid/server/it/{Alias}Test.java` (one per alias of THIS bidder, when this bidder is a parent) | optional | `read-bidder-class` (records alias `test_assets`) |
| Integration test fixtures (4-file split) | `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/test-{name}-{request,response,auction-request,auction-response}.json` | strongly recommended | `read-bidder-class` |
| Test application properties | `src/test/resources/test-application.properties` | always present (CENTRAL registry — every adapter appends 2-4 lines) | `read-bidder-class` (entries-added count) |

## Java identifier rules

The TitleCase class root `{Xyz}` is computed from the lowercase YAML name `{xyz}` per Java identifier rules. The orchestrator MUST handle the following edge cases.

### Standard case

`{xyz}=kobler` → `{Xyz}=Kobler`. Class names: `KoblerBidder`, `KoblerConfiguration`, `KoblerBidderTest`, `KoblerTest`, `ExtImpKobler`. Test fixture folder: `kobler/`.

### TitleCase brand-acronym preservation

Some bidders preserve original-brand TitleCase capitalization rather than apply naive lower-camel-to-PascalCase conversion. The orchestrator's discovery code MUST recognize these by allow-list:

| YAML name | Class root | Files preserved |
|---|---|---|
| `elementaltv` | `ElementalTV` | `ElementalTVBidder.java`, `ElementalTVConfiguration.java`, `ElementalTVTest.java`, `ExtImpElementalTV.java` |
| `feedad` | `FeedAd` | `FeedAdBidder.java`, `FeedAdConfiguration.java`, `FeedAdTest.java`, `ExtImpFeedAd.java` |
| `bidtheatre` | `BidTheatre` | `BidTheatreBidder.java`, `BidTheatreConfiguration.java`, `BidTheatreTest.java`, `ExtImpBidTheatre.java` |
| `bidscube` | `BidsCube` | `BidsCubeBidder.java`, etc. |
| `boldwinrapid` | `BoldwinRapid` | preserves the camelCase `Boldwin` + `Rapid` split |

Spec field: `code.naming.preserves_acronym_case: true` is set when the discovered class root differs from the naive PascalCase. The R6 (`package-directory-mismatch`) warning is suppressed for these cases — the heuristic checks against this allow-list before warning.

The allow-list is maintained in this file; new entries require a Phase 2 sample (a real prebid-server-java PR demonstrating the preservation). The current allow-list reflects state at v3.41.0 (resolved_commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a`).

### Identifier-rule workaround (digit-leading)

Java identifiers cannot start with a digit. Some bidders have digit-leading YAML names:

| YAML name | Class root | Notes |
|---|---|---|
| `152media` | `OneFiveTwoMedia` | Class root is the spelled-out digits in PascalCase. Files: `OneFiveTwoMediaBidder.java`, `OneFiveTwoMediaConfiguration.java`, `OneFiveTwoMediaTest.java`, `ExtImpOneFiveTwoMedia.java`. |
| `33across` | `Thirtythree` | (Note: 33across is an alias-only on Java side; the Go side has `ttx` — see Go-side cross-language stub.) |

Spec field: `code.naming.{yaml_name, class_name_root, identifier_workaround: true}` is set. The R6 warning is suppressed for these cases. Quirk taxon: `identifier-rule-workaround` (per `behavior-taxonomy.md`).

### Snake-case bidder names

Some bidders carry snake-case YAML names (e.g., `boldwinrapid`, `aboveall`). The class root is the PascalCase concatenation of the snake-case parts. The orchestrator handles this by splitting on `_` (none in current corpus, all are concatenated lowercase) or by applying a normalization that joins the parts. PR #4285 (`BoldwinRapid`) is the canonical example.

## Alias short-circuit (Step 4)

If the bidder is found in some parent's `aliases:` map (rather than having its own `bidder/{xyz}/` directory), it's an alias. Discovery skips the bidder/proto/test files and instead gathers:

1. The parent's full file set (the bidder inherits behavior from the parent).
2. The alias-specific test assets, if present:
   - `src/test/java/org/prebid/server/it/{Alias}Test.java` (per-alias IT class — required by Java convention; a missing file is a `missing-expected-file` warning).
   - `src/test/resources/org/prebid/server/it/openrtb2/{alias}/test-{alias}-{request,response,auction-request,auction-response}.json` (4 files).
3. The alias's entry in `test-application.properties` (typically 2-4 lines per alias).

The parent's `bidder-config/{parent}.yaml` is the source of truth for the alias's config. The alias's overrides (if any) live in the parent's `aliases.{alias}` block — when it's `~` (tilde), full inheritance; when it's a populated block, partial override.

### Bidder rename three-step refactor (edge case #33)

When a bidder is renamed (Adoppler → ElementalTV is the canonical example):

1. The OLD YAML (`bidder-config/adoppler.yaml`) is DELETED.
2. The NEW YAML (`bidder-config/elementaltv.yaml`) is CREATED.
3. The NEW YAML declares the OLD name as an alias: `aliases: { adoppler: ~ }` for backward compatibility (existing publishers still pass `bidder=adoppler`).

Discovery handles this transparently:
- `--bidder=adoppler` resolves as an alias of `elementaltv` in Step 4.
- `--bidder=elementaltv` resolves as a full read in Step 5.
- The orchestrator emits `lifecycle.rename.{old_name, new_name, yaml_deletes, yaml_adds, alias_back}` data on the NEW spec.

## Discovery validation

After file gathering, the orchestrator runs these checks (Step 6 R-rules cite them):

1. Every file required by the spec sections is reachable at `resolved_commit` (R1). Missing required files abort the read with a clear error.
2. Cross-file naming alignment:
   - `KoblerConfiguration.java`'s `@PropertySource("classpath:/bidder-config/kobler.yaml")` matches the YAML filename.
   - `KoblerBidder.java`'s `parseImpExt` `TypeReference<ExtPrebid<?, ExtImpKobler>>` matches the proto class.
   - `KoblerBidderTest.java` references `KoblerBidder` (not, e.g., `KargoBidder` — Java analog of the Go bidder-constant-mismatch).
   Misalignments emit `class-yaml-name-mismatch` warnings.
3. The proto/ directory's class set is consistent with the bidder's needs:
   - If the bidder has params (non-empty bidder-params JSON schema), `ExtImp{Xyz}.java` MUST exist.
   - For `Bidder<MediasquareRequest>` style custom payloads, additional `MediasquareRequest.java`, `MediasquareCode.java`, etc. must exist in proto/.

## Sources

- Master plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md` (Edge cases #18–#34, Discovery rules narrative).
- Canonical schema: `../../../../../prebid-server-go/read/skills/shared/adapter-spec.md` (Per-section field reference: `code.naming.*`).
- Behavior taxonomy: `../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md` (`identifier-rule-workaround`, `acronym-case-preservation`, `bidder-rename-three-step` taxa).
- Java reference list: `../../../references/new-bid-adapter-prs.md` (49 PRs with `Patterns Demonstrated` tags — source for the TitleCase + identifier-workaround allow-lists).
- Sibling Go discovery rules: `../../../../../prebid-server-go/read/skills/read-adapter-orchestrator/references/discovery-rules.md` (when authored — Go has different file hierarchy).
