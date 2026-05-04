# port-go2java templates — placeholder

Phase D2 fills this directory with Jinja templates for Java artifact emission. Each template is checkstyle-compliant by construction (ImportOrder strict 3-group with blank-line separation; LineLength≤120; EmptyLineSeparator).

Expected templates:

- `bidder.java.j2` — `{Bidder}Bidder.java` (the Bidder<T> implementation)
- `configuration-properties.java.j2` — `{Bidder}Configuration.java` (Spring config + `BidderInfoCreator`-driven beans)
- `ext-imp-pojo.java.j2` — `proto/openrtb/ext/request/{bidder}/ExtImp{Bidder}.java` (Lombok-annotated POJO)
- `bidder-test.java.j2` — `{Bidder}BidderTest.java` (unit test scaffold)
- `it-test.java.j2` — `{Bidder}Test.java` (integration test class)
- `bidder-config.yaml.j2` — `bidder-config/{bidder}.yaml`
- `it-fixture-{auction,bid}-{request,response}.json.j2` — IT 4-file fixture pairs
- `pr-body.md.j2` — destination PR body, populated against the upstream `pull_request_template.md`

Until then, see `../SKILL.md` for the design contract.
