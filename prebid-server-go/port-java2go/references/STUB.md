# port-java2go references — placeholder

Phase D1.3 fills this directory with Go-target emission references:

- `go-artifact-shapes.md` — canonical Builder/MakeRequests/MakeBids skeletons; minimal-header convention; per-bidder package layout. Distilled from existing read-side `read-adapter-code/references/{file-role-heuristics,adapter-code-patterns}.md` plus inversion-specific guidance.
- `pr-shape.md` — Go PR-shape convention. Title `New Adapter: {Bidder}` (capital A, observed 100% of merged PRs); body distilled from real PRs; no mandatory label (Go has no upstream PR template).
- `registration-rules.md` — alphabetical insertion-position rules (case-insensitive lower-first) across `bidders.go`, `adapter_builders.go`. Driven by `TestBidderUniquenessGatekeeping` (first-6-letter uniqueness) and the upstream alphabetical-insert convention.
- `porting-guide.md` — internally-authored inverse porting guide (analogue of upstream Java's `bid-adapter-porting-guide.md`). Distilled from Java→Go research findings + observed real-world Go-side new-adapter PRs. Captures: "treat as re-implementation," lossy-direction asymmetries (Rule 35 typed-config-subclass demotion), test-fixture re-authoring contract, prohibited patterns.

Until then, see `../SKILL.md` for the design contract.
