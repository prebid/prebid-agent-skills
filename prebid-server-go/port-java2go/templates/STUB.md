# port-java2go templates — placeholder

Phase D3 fills this directory with Jinja templates for Go artifact emission. Each template is `gofmt -s -w`-clean by construction; emission flow includes a post-process step that runs `gofmt -s -w` against every emitted `.go` file before commit.

Expected templates:

- `bidder.go.j2` — `adapters/{bidder}/{bidder}.go` (Builder + MakeRequests + MakeBids per Go canonical pattern)
- `bidder-test.go.j2` — `adapters/{bidder}/{bidder}_test.go` (thin `RunJSONBidderTest` wrapper)
- `imp-ext-pojo.go.j2` — `openrtb_ext/imp_{bidder}.go` (struct emitted from Java's `ExtImp{Bidder}.java`; Lombok annotations stripped)
- `params-test.go.j2` — `adapters/{bidder}/params_test.go` (validates schema)
- `bidder-info.yaml.j2` — `static/bidder-info/{bidder}.yaml` (camelCase keys; converted from Java's kebab-case)
- `exemplary-fixture.json.j2` — flat exemplary fixtures re-authored from Java IT 4-file split
- `bidders-go-insert.j2` — minimal patch fragment for `openrtb_ext/bidders.go` constant + `coreBidderNames` slice entry (alphabetical, lower-first)
- `adapter-builders-insert.j2` — minimal patch fragment for `exchange/adapter_builders.go` import + map entry (alphabetical)
- `pr-body.md.j2` — destination PR body (Go has no upstream template; this is internally authored per `references/pr-shape.md`)

Until then, see `../SKILL.md` for the design contract.
