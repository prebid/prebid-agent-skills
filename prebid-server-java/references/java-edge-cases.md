# Java Edge Cases #18–#34 (Phase 2 reconnaissance catalog)

The 17 Java-specific edge cases discovered during Phase 2 reconnaissance,
each mapped to the Adapter Specification field that captures it. These are
referenced by number throughout the Java read skills (e.g., "Java edge case
#33" in `read-bidder-config/SKILL.md`); this file is the canonical home.

None of the 17 require a `custom` + `quirks[]` fallback — every case maps to
a typed schema field. The orchestrator (`read-bidder-orchestrator`) merges
contributions from `read-bidder-config`, `read-bidder-class`, and
`read-bidder-params-java` to populate them.

| # | Edge case | Captured by | Owner skill | Master sample(s) |
|---|---|---|---|---|
| 18 | Spring `@Configuration` class with `@PropertySource` | `spring_config.{factory_class, factory_method, property_source_path}` | `read-bidder-class` | Kobler |
| 19 | Configuration-class naming variance (`KoblerConfiguration` vs `AdverxoBidderConfiguration`) | `spring_config.factory_class` (verbatim) | `read-bidder-class` | Kobler, Adverxo |
| 20 | `BidderConfigurationProperties` subclass for custom YAML fields | `spring_config.configuration_properties_class.{name, extends, extra_fields[], nested_classes[], lombok_annotations[]}` | `read-bidder-class` | Kobler `devEndpoint`, Appnexus `platformId`+`iabCategories`, Huaweiads `ExtraInfo` |
| 21 | IAB categories inlined in YAML (vs Go data file) | `iab_category_storage.{storage_kind: yaml-inlined, yaml_field, table_size, delivery_mechanism}` | `read-bidder-class` | Appnexus (120 entries) |
| 22 | Hand-written N `@Test` methods (no JSON harness) | `tests.{unit_test_methods_count, unit_test_loc, uses_canonical_harness, hand_written_test_methods[]}` | `read-bidder-class` | Huaweiads |
| 23 | Wiremock + 4-file IT fixture pattern | `tests.integration_test_pattern: 4-file-split`, `tests.fixture_inventory.integration[]` | `read-bidder-class` | All Java IT tests |
| 24 | Per-alias IT class + 4-file fixture set required (Java-only Rule 37) | `aliases[].test_assets.{it_class, fixture_dir, fixture_file_count}` | `read-bidder-class` | Connektai (alias of xeworks) |
| 25 | Central `test-application.properties` registry append | `tests.test_application_properties_entries_added: N` (canonical) + `aliases[].test_application_properties_entries[]` | `read-bidder-class` | All Java adapter PRs |
| 26 | Class names break Java identifier rules for digit-leading bidders | `code_naming.{yaml_name, class_name_root, identifier_workaround: digit-leading-rename}` (top-level) + quirk `identifier-rule-workaround` | `read-bidder-class` | `152media → OneFiveTwoMedia`, `33across → Thirtythree` |
| 27 | TitleCase brand-acronym preservation | `code_naming.preserves_acronym_case: true` + quirk `acronym-case-preservation` | `read-bidder-class` | ElementalTV, FeedAd, BidTheatre, BidsCube |
| 28 | `Bidder<T>` generic parameterization for custom payloads | `bidder_class.parameterized_request_type` + `code.make_requests.request_body.{kind: custom, custom_body_type}` | `read-bidder-class` | Mediasquare (`MediasquareRequest`), Huaweiads (`HuaweiAdsRequest`) |
| 29 | `ortb-version: "2.6"` quoted-string field | `bidder_info.ortb_version` | `read-bidder-config` | Bidders supporting OpenRTB 2.6 |
| 30 | `enabled: false` opt-in default | `bidder_info.default_enabled: false` | `read-bidder-config` | Optidigital, Adverxo aliases (Rule 45 canonical case) |
| 31 | `modifying-vast-xml-allowed: true` | `bidder_info.modifying_vast_xml_allowed: true` | `read-bidder-config` | FeedAd PR #3869, Mediasquare PR #4031 |
| 32 | Tilde-syntax empty alias `oldname: ~` | `aliases[].config_form: tilde_inherit` | `read-bidder-config` | Most Java alias-empires |
| 33 | Bidder rename three-step refactor (DELETE old + CREATE new + alias-back via tilde) | `lifecycle.rename.*` (orchestrator-merged) | orchestrator | Adoppler→ElementalTV (PR `prebid/prebid-server-java#4326`); Rule 43 `bilateral` sub-type |
| 34 | `endpoint-compression` vs `endpointCompression` typo regression | `bidder_info.yaml_field_name_quirks[]` + `yaml-field-name-typo` warning | `read-bidder-config` | Ogury PR #3788 (silent no-op — compression NOT applied) |

## Notes

- Edge cases #18–#28 are owned by `read-bidder-class` (Spring/Java patterns).
- Edge cases #29–#34 are owned by `read-bidder-config` (YAML patterns).
- The orchestrator validates cross-domain consistency (e.g., #33 lifecycle.rename data must come from BOTH `read-bidder-config` and `read-bidder-class` — orchestrator merges).
- Each case has at least one master sample in the corpus goldens; deeper write-ups live in the per-domain reference files (`read-bidder-class/references/spring-config-patterns.md`, `read-bidder-config/references/yaml-unification-rules.md`, etc.).

## Cross-references

- Per-case implementation: see the relevant `references/*.md` file under the owner skill.
- Schema fields: `prebid-server-go/read/skills/shared/adapter-spec.schema.json`.
- Quirks taxa cited above (`identifier-rule-workaround`, `acronym-case-preservation`): `prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`.
- Port-translation rules these surface in: Rule 27 (#26 digit-leading), Rule 33 (#32 alias inversion), Rule 34 (#21 IAB), Rule 35 (#20 config-subclass), Rule 37 (#24 per-alias IT), Rule 42 (#21 IAB), Rule 43 (#33 rename), Rule 45 (#30 default-enabled), Rule 46 (#26 + #27 naming).
- Phase 2 reconnaissance (canonical findings document): `docs/decisions/`.
