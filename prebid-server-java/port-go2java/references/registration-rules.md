# Registration insertion rules (Java target)

Phase D1.3 deliverable — alphabetical insertion-position rules for Java-side files where adding a new adapter requires editing a registry-style file. The port-go2java SKILL Step 5 invokes `scripts/lib/port_engine.alphabetical_insert` (or APPENDS, when no sort is used) per the per-file rule below.

## Files the port skill writes

| File | Edit kind | Sort | Helper |
|---|---|---|---|
| `src/main/resources/bidder-config/{bidder}.yaml` | Create | N/A (one file per bidder) | direct write |
| `src/main/resources/static/bidder-params/{bidder}.json` | Create | N/A (one file per bidder) | `byte_copy` |
| `src/main/java/org/prebid/server/bidder/{bidder}/{Bidder}Bidder.java` | Create | N/A | direct write |
| `src/main/java/org/prebid/server/spring/config/bidder/{Bidder}Configuration.java` | Create | N/A (Spring auto-discovery) | direct write |
| `src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/ExtImp{Bidder}.java` | Create | N/A | direct write |
| `src/test/java/org/prebid/server/bidder/{bidder}/{Bidder}BidderTest.java` | Create | N/A | direct write |
| `src/test/java/org/prebid/server/it/{Bidder}Test.java` | Create | N/A | direct write |
| `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-*.json` | Create | N/A | direct write |
| `src/test/resources/org/prebid/server/it/test-application.properties` | INSERT at end of `adapters.*` cluster (not sorted) | none | insert two lines |

Java's Spring DI does most registry work automatically — there is no `bidders.go`-equivalent constants file or `adapter_builders.go`-equivalent dispatch map to keep alphabetical. The {Bidder}Configuration class is auto-discovered by Spring at startup.

## test-application.properties insertion shape

> **Corrected 2026-07-06 (F-new-110).** Earlier versions of this doc said "append at the end of the file" — that is WRONG against the live file. The `adapters.*` entries form one contiguous cluster in the FIRST part of the file; the file's tail carries non-adapter settings (`ccpa.enforce`, mock endpoints, etc.). An EOF append lands the new bidder ~60 lines below the cluster, which reads as misplaced and was flagged by a fresh-eyes upstream review on the rtbstack canary.

The IT-test resource at `src/test/resources/org/prebid/server/it/test-application.properties` carries two lines per bidder. Insert exactly two lines at the END of the contiguous `adapters.*` cluster (immediately after the last existing `adapters.*` line):

```properties
adapters.{bidder}.enabled=true
adapters.{bidder}.endpoint=http://localhost:8090/{bidder}-exchange
```

NO alphabetical sort within the cluster. NO empty-line separation between bidders. Entries land in the order they were added historically. Two concurrent ports inserting at the cluster end produce a trivially-resolvable adjacent-line conflict (both orderings are valid).

## Why no `bidders.go`-equivalent exists

Spring's `@Configuration`-annotated `{Bidder}Configuration` class registers itself with the `BidderCatalog` at startup. The catalog uses the bidder's `BIDDER_NAME` constant (declared inside the Configuration class as a private string) as the lookup key. There is no central Java file enumerating all bidder names — adding a new bidder requires zero edits to existing registry files.

Implication for the port skill: the Java side has FEWER mechanical registry edits than the Go side, but more files to create.

## Per-alias asymmetry

When the source spec is an alias-empire parent (Rule 33, Rule 44), the Java emission consolidates aliases into the parent's `bidder-config/{parent}.yaml`:

```yaml
adapters:
  smarthub:
    endpoint: https://example.com/{{Host}}/bid
    aliases:
      host_a: ~  # alias inherits parent
      host_b:
        endpoint: https://host-b.example.com/bid
```

The skill's Rule 33 helper (`scripts/lib/port_engine.alias_graph_invert(direction='go-to-java')`) builds the `aliases:` block content from the source spec's per-alias bidder-info diffs. Per-alias YAML files are NOT emitted on the Java side (Java consolidates; Go splits).

For empire children, EACH child gets its own `{Bidder}{Alias}Test.java` IT class even when the bidder logic is shared with the parent. Per Java edge case #19 + Rule 44 alias-empire flavor coherence; the templates in `../templates/it-test.java.j2` parameterize the alias suffix.

## Connection to other rules

- Rule 38 (`byte_copy`): drives the `bidder-params/{bidder}.json` create step.
- Rule 46 (`normalize_bidder_name`): Resolves `{bidder}` lowercase form for paths.
- Rule 33 (`alias_graph_invert`): Builds the `aliases:` block for the parent YAML.
- [`pr-template-mapping.md`](pr-template-mapping.md): How the upstream `pull_request_template.md` is auto-populated against the spec's behavioral fields.

## See also

- [`java-artifact-shapes.md`](java-artifact-shapes.md) — checkstyle + import-order + emission templates that produce these files.
- Upstream porting guide: [`prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md`](https://github.com/prebid/prebid-server-java/blob/master/docs/developers/bid-adapter-porting-guide.md).
