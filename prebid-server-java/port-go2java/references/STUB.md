# port-go2java references — placeholder

Phase D1.3 fills this directory with Java-target emission references:

- `java-artifact-shapes.md` — license headers, Java package decls, test-application.properties shape, checkstyle ImportOrder + EmptyLineSeparator + ban-list rules
- `pr-template-mapping.md` — Java PR-template auto-population mapping (mandatory `do not port` label, `Port {Bidder}: New Adapter` title, `[x]` checkbox population against source spec behavioral fields)
- `registration-rules.md` — alphabetical insertion-position rules across `bidders.go`, `adapter_builders.go`, alias YAML maps, `test-application.properties`
- `porting-guide.md` — version-pinned snapshot of upstream `prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md` (PR #3768)
- `framework-utilities-java.md` — companion file at `../../prebid-server-java/read/skills/shared/framework-utilities-java.md` (sibling read-side; consumed port-side)

Until then, see `../SKILL.md` for the design contract.
