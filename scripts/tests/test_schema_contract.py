#!/usr/bin/env python3
"""Schema contract test — phantom-path detector with documented gaps.

Every dotted path used in any `*.md` under the four skill surfaces —
`prebid-server-{go,java}/read/skills/`, `prebid-server-{go,java}/review/skills/`,
`prebid-server-go/port-java2go/` and `prebid-server-java/port-go2java/` — is
checked against the canonical schema vocabulary derived from:
- prebid-server-go/read/skills/shared/adapter-spec.schema.json (Phase 2.0+ canonical)
- prebid-server-go/read/skills/shared/behavior-taxonomy.md (taxonomy enums, still markdown)

The test catches "phantom field" bugs (a SKILL claims a field that does not
exist in the canonical schema) BUT only for paths under CLOSED schema blocks.

## Coverage

Caught: phantom paths under closed top-level blocks — `bidder_info`
(non-`{capabilities,user_sync,yaml_extra_fields,yaml_field_name_quirks}`),
`provenance`, `meta`, `params.{ext_struct,schema_interpretation}` non-leaf,
`ext_pojo_construction` non-`custom_unmarshal`, `currency_conversion`.
Concretely: `bidder_info.fakey_fake` and `provenance.read.NOT_REAL` are
caught.

NOT caught: paths under the open-map prefixes the schema declares with
`additionalProperties: true` (post-Wave-11b: 11 such prefixes remain —
4 EXTENSION-SLOTS + 7 LEGITIMATELY-OPEN). Concretely:
`bidder_info.yaml_extra_fields.fakey_field`, `tests.fixture_inventory.x`
all pass; closures applied in Wave 11b mean `code.this_does_not_exist`
and `quirks.fake` are now CAUGHT.

## Open-map prefix history

Pre-Wave-11b the schema had 28 open-map prefixes (13 top-level + 15
nested). Wave 11b / Phase 2.8 closed 17 accidentally-open sites (B1
Tier A: 6 sites; B2 Tier B: 9 sites; B3 Tier C: 4 lift-to-$defs; B3+
round-2 sweep: 8 sites under code.* and cross_language.*). Post-Wave-11b
the schema has 11 open-map prefixes:

  4 EXTENSION-SLOTS (ADR-007 F1/F3/F4/F5 `$defs`, NOT yet $ref-wired
  into Code; per-pattern wiring is a future wave's task):
  EndpointResolution, EntityStrategy, BidPostProcessing, ImpExtUnmarshal.

  7 LEGITIMATELY-OPEN (keyed by arbitrary user/upstream name):
  - `tests.fixture_inventory` (keyed by category)
  - `params.schema_interpretation.properties` (keyed by JSON Schema property name)
  - `bidder_info.yaml_extra_fields` (arbitrary upstream YAML)
  - `bidder_info.yaml_field_name_quirks` (arbitrary upstream YAML quirk names)
  - `bidder_info.user_sync` (sub-keys vary per usersync mechanism)
  - `bidder_info.capabilities` (keyed by ad format pair)
  - `provenance.read.skill_versions` (keyed by skill name; patternProperties)

Wave 11c will close 3 of the 7 LEGITIMATELY-OPEN sites if the corpus
canonical-encoding decisions (Alias canonical name, fixture_inventory
typed-values, registry migration) land. See `CHANGELOG.md` entry [adapter_spec_version 1.2.0] for the full closure-tier breakdown.

The sibling phantom-path test at
`test_schema_jsonschema.py:test_no_truly_invented_keys_outside_open_maps`
was rewritten in Wave 11b B5 #1 to use path-aware vocabulary (closes
the prior leaf-key permissive escape gap).

Phase 2.3 note (2026-05-02): the schema registry is derived from
`adapter-spec.schema.json`; the legacy 180-entry hand-curated
SCHEMA_REGISTRY_EXTRAS is gone (Wave 2 deleted the dead block).

Usage (from repo root):
    python3 scripts/tests/test_schema_contract.py
    python3 scripts/tests/test_schema_contract.py --verbose

Exit codes:
    0  every dotted path resolves under the coverage rules above
    1  one or more phantom paths detected (under closed blocks)
    2  schema/taxonomy could not be parsed (sanity-check failure)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Iterable, List, Set, Tuple

try:
    import yaml  # PyYAML
except ImportError:
    sys.stderr.write("ERROR: PyYAML is required (pip install pyyaml)\n")
    sys.exit(2)


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
ADAPTER_SPEC_SCHEMA_JSON = os.path.join(
    REPO_ROOT, "prebid-server-go", "read", "skills", "shared", "adapter-spec.schema.json"
)
BEHAVIOR_TAXONOMY = os.path.join(
    REPO_ROOT, "prebid-server-go", "read", "skills", "shared", "behavior-taxonomy.md"
)
# Every skill surface the repo ships. The read/ suites were the original
# scope; the review/ suites and the two port skills are the surfaces that
# actually run against real upstream PRs, so a phantom path there is the
# one that reaches a reviewer. All four are scanned identically.
SKILL_DIRS = (
    os.path.join(REPO_ROOT, "prebid-server-go", "read", "skills"),
    os.path.join(REPO_ROOT, "prebid-server-java", "read", "skills"),
    os.path.join(REPO_ROOT, "prebid-server-go", "review", "skills"),
    os.path.join(REPO_ROOT, "prebid-server-java", "review", "skills"),
    os.path.join(REPO_ROOT, "prebid-server-go", "port-java2go"),
    os.path.join(REPO_ROOT, "prebid-server-java", "port-go2java"),
)

# Directories holding the canonical vocabulary itself. A doc that IS the
# registry cannot be checked against itself — every path it defines would
# have to already be in the registry it defines. Only these two trees are
# circular; `*/review/skills/shared/` holds framework-utility references,
# not vocabulary, so it is scanned like any other skill doc.
#
# Paths are repo-relative with forward slashes and a trailing slash.
REGISTRY_DIRS = (
    "prebid-server-go/read/skills/shared/",
    "prebid-server-java/read/skills/shared/",
)

# Phantom paths accepted for now, keyed by (repo-relative path, dotted path).
# Line numbers are deliberately NOT part of the key — an edit above the site
# must not silently retire the waiver.
#
# This list is a two-way gate. A listed phantom is downgraded to a WAIVED
# report instead of failing the run; a listed phantom that NO LONGER fires
# fails the run so the stale entry gets deleted rather than accumulating.
#
# Each entry carries the date it was accepted and why. Adding one is a
# deliberate act, not a way to keep the gate quiet.
# Dated waivers for phantom paths a gate-widening PR surfaces but does not own.
# Empty is the correct steady state: the widening that introduced this list also
# carried the one violation it found (`macros[]` -> `macros_used`), so the entry
# it shipped with was deleted in the same change. A waiver here is a two-way
# ratchet -- it fails when the underlying path is fixed and the entry lingers.
KNOWN_PHANTOMS: dict[tuple[str, str], str] = {}

# Top-level keys recognised as belonging to the schema. Phantom-path detection
# runs ONLY on dotted paths whose first segment matches one of these — that
# filters out package paths (prebid/prebid-server.go), URLs (http.example.com),
# and unrelated dotted tokens.
def _schema_top_level_keys() -> frozenset[str]:
    """Read the gate's filter out of the schema instead of restating it.

    This was a hand-maintained copy of the schema's top-level property names, and
    it drifted in the direction that loses coverage: it still listed
    `bidder_params_json` after 2.0.0 removed it, and never gained
    `bidder_params_ref` -- so every `bidder_params_ref.*` path a skill cited was
    filtered out of phantom detection and silently unchecked. A filter that has to
    be updated by hand to keep covering new fields will always lag the fields.
    """
    with open(ADAPTER_SPEC_SCHEMA_JSON, "r", encoding="utf-8") as fh:
        return frozenset(json.load(fh).get("properties", {}))


SCHEMA_TOP_LEVEL_KEYS = _schema_top_level_keys()

# Tokens that resemble schema paths but are noise. Add here as new false
# positives surface; never silence a real phantom by adding to this list.
DENYLIST_PREFIXES = frozenset({
    "prebid.server", "github.com", "openrtb_ext.Bidder",
    "errortypes.BadInput", "errortypes.BadServerResponse",
    "macros.EndpointTemplateParams", "url.URL", "url.Values",
    "ext.bidder", "imp.ext.bidder", "imp.ext.prebid",
    "bid.ext.prebid", "request.Imp", "response.SeatBid",
    "device.geo.country", "user.geo.country",
})

# Open-map points: schema declares a parent path with arbitrary sub-keys.
# Any path under one of these prefixes is accepted without registry lookup.
OPEN_MAP_POINTS = frozenset({
    "bidder_info.user_sync",
    "bidder_info.yaml_extra_fields",
    "params.params_test",
    "params.schema_interpretation.properties",
    "code.adapter_struct",
    "code.builder",
    "code.make_requests.mutation.entity_strategies",
    "spring_config.bidder_creator_lambda",
    "tests.fixture_inventory",
})


def parse_yaml_paths_from_codeblocks(md_text: str) -> Set[str]:
    """Walk every ```yaml block in `md_text` and collect dotted leaf paths."""
    paths: Set[str] = set()
    fence = re.compile(r"^```ya?ml\s*\n(.*?)\n```", re.MULTILINE | re.DOTALL)
    for m in fence.finditer(md_text):
        block = m.group(1)
        # Comment lines beginning with `# - name:` are pseudo-yaml that PyYAML
        # ignores. Strip leading `# ` from such lines so the structure parses.
        cleaned_lines: List[str] = []
        for line in block.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("# ") and (stripped[2:3] in {"-", " "} or ":" in stripped):
                cleaned_lines.append(line.replace("# ", "  ", 1))
            else:
                cleaned_lines.append(line)
        cleaned = "\n".join(cleaned_lines)
        try:
            tree = yaml.safe_load(cleaned)
        except yaml.YAMLError:
            continue
        if not isinstance(tree, dict):
            continue
        _collect(tree, "", paths)
    return paths


def _collect(node, prefix: str, out: Set[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            sub = f"{prefix}.{k}" if prefix else str(k)
            out.add(sub)
            _collect(v, sub, out)
    elif isinstance(node, list):
        for v in node:
            _collect(v, prefix, out)


def parse_header_paths(md_text: str) -> Set[str]:
    """Collect dotted paths cited in markdown H1-H4 backticked spans."""
    paths: Set[str] = set()
    header = re.compile(r"^#{1,4}\s+`([a-z_][a-z0-9_.\[\]]*)`", re.MULTILINE)
    for m in header.finditer(md_text):
        token = m.group(1).rstrip(".")
        normalized = token.replace("[]", "")
        if not normalized:
            continue
        paths.add(normalized)
        # Register every prefix so partial paths match too.
        parts = normalized.split(".")
        for i in range(1, len(parts)):
            paths.add(".".join(parts[:i]))
    return paths


def parse_table_field_paths(md_text: str) -> Set[str]:
    """Collect dotted paths cited inline in markdown tables and prose.

    Pattern: `<dotted.path>` in any markdown context. Some specs
    document fields by citing the path inline rather than via headers.
    """
    paths: Set[str] = set()
    inline = re.compile(r"`([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+(?:\[\])*)`")
    for m in inline.finditer(md_text):
        token = m.group(1)
        normalized = token.replace("[]", "")
        head = normalized.split(".")[0]
        if head in SCHEMA_TOP_LEVEL_KEYS:
            paths.add(normalized)
            parts = normalized.split(".")
            for i in range(1, len(parts)):
                paths.add(".".join(parts[:i]))
    return paths


# Section headers introducing a field-reference table — accept any subsequent
# table-row leading-cell as a relative field path under the section's prefix.
# Pattern: `### \`<section>\`` followed by a table where first cell holds the
# field name in backticks (possibly a dotted relative path).
SECTION_HEADER_RE = re.compile(r"^#{2,4}\s+`([a-z_][a-z0-9_.]*)`", re.MULTILINE)
TABLE_ROW_FIRST_CELL = re.compile(r"^\|\s*`([a-z_][a-z0-9_.\[\]]*)`")


def parse_section_table_field_paths(md_text: str) -> Set[str]:
    r"""For each section header ``### `<section>` ``, scan subsequent table rows
    until the next H2/H3/H4. Each row's first backticked cell becomes a
    relative path under <section>; promote to the full dotted form.

    This handles the dominant adapter-spec.md pattern:

        ### `cross_language`
        | Field | Type | Required | Description |
        |---|---|---|---|
        | `go_artifacts` | object | yes | Go-side artifact path hints. |
        | `go_specific_concerns[]` | array | yes | ... |
    """
    paths: Set[str] = set()
    sections: List[Tuple[int, str]] = [
        (m.start(), m.group(1).rstrip(".")) for m in SECTION_HEADER_RE.finditer(md_text)
    ]
    if not sections:
        return paths
    for i, (start, section_path) in enumerate(sections):
        end = sections[i + 1][0] if i + 1 < len(sections) else len(md_text)
        body = md_text[start:end]
        for line in body.splitlines():
            row = TABLE_ROW_FIRST_CELL.match(line)
            if not row:
                continue
            relative = row.group(1).replace("[]", "").rstrip(".")
            # Skip table-divider rows where the first cell is "Field" / "Type".
            if relative.lower() in {"field", "type", "kind", "value", "method"}:
                continue
            full = f"{section_path}.{relative}"
            paths.add(full)
            # Register every prefix.
            parts = full.split(".")
            for j in range(1, len(parts)):
                paths.add(".".join(parts[:j]))
    return paths


def _resolve_ref(schema: dict, node):
    """If node is `{"$ref": "#/$defs/X"}`, return $defs.X. Otherwise return node verbatim."""
    if isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if ref.startswith("#/$defs/"):
            ref_name = ref[len("#/$defs/"):]
            return schema.get("$defs", {}).get(ref_name, node)
    return node


def _walk_schema(schema: dict, node, prefix: str, registry: Set[str], open_maps: Set[str]) -> None:
    """Walk a JSON Schema 2020-12 node, collecting all dotted property paths.

    Resolves $ref to #/$defs/* inline. Detects open-map points (objects with
    `additionalProperties: true`). Walks oneOf/anyOf/allOf and if/then/else
    branches uniformly so the source_language discrimination is unwrapped.
    """
    node = _resolve_ref(schema, node)
    if not isinstance(node, dict):
        return

    # additionalProperties open at this level -> open map keyed by `prefix`.
    # Per JSON Schema Draft 2020-12, omitted additionalProperties defaults to
    # true (open). Treat both explicit `true` and omitted as open.
    addl = node.get("additionalProperties", True)
    types = node.get("type")
    if isinstance(types, str):
        types = [types]
    is_object = isinstance(types, list) and "object" in types
    if (addl is True or (isinstance(addl, dict) and addl)) and is_object and prefix:
        open_maps.add(prefix)

    # Walk explicit properties
    props = node.get("properties")
    if isinstance(props, dict):
        for k, v in props.items():
            p = f"{prefix}.{k}" if prefix else k
            registry.add(p)
            _walk_schema(schema, v, p, registry, open_maps)

    # Walk array items (items inherit the parent's prefix — array indices
    # are not part of the dotted path)
    items = node.get("items")
    if isinstance(items, dict):
        _walk_schema(schema, items, prefix, registry, open_maps)

    # Walk all branches uniformly
    for keyword in ("oneOf", "anyOf", "allOf"):
        branches = node.get(keyword)
        if isinstance(branches, list):
            for branch in branches:
                _walk_schema(schema, branch, prefix, registry, open_maps)

    # if/then/else for source_language discrimination (Phase 2.1)
    for keyword in ("if", "then", "else"):
        if keyword in node:
            _walk_schema(schema, node[keyword], prefix, registry, open_maps)


def build_schema_registry() -> Set[str]:
    """Union of property paths from adapter-spec.schema.json + behavior-taxonomy.md.

    Phase 2.3: the JSON Schema is the source of truth for the structural
    contract. Markdown taxonomy paths from behavior-taxonomy.md are still
    parsed (taxon enum tables haven't been migrated to data yet — that's
    Phase 2.4).
    """
    registry: Set[str] = set()

    # Primary source: JSON Schema
    if not os.path.isfile(ADAPTER_SPEC_SCHEMA_JSON):
        sys.stderr.write(f"ERROR: schema missing: {ADAPTER_SPEC_SCHEMA_JSON}\n")
        sys.exit(2)
    with open(ADAPTER_SPEC_SCHEMA_JSON, "r", encoding="utf-8") as fh:
        try:
            schema_json = json.load(fh)
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"ERROR: invalid JSON in {ADAPTER_SPEC_SCHEMA_JSON}: {exc}\n")
            sys.exit(2)
    schema_open_maps: Set[str] = set()
    _walk_schema(schema_json, schema_json, "", registry, schema_open_maps)

    # Merge schema-derived open-maps with the static OPEN_MAP_POINTS so
    # the existing constant continues to work for legacy callers. Phase 2.4
    # may consolidate.
    global _DERIVED_OPEN_MAPS
    _DERIVED_OPEN_MAPS = schema_open_maps

    # Secondary source: behavior-taxonomy.md (markdown) — taxon enum paths
    # such as `code.make_bids.bid_type_resolution.method_chain[].method` etc.
    if not os.path.isfile(BEHAVIOR_TAXONOMY):
        sys.stderr.write(f"ERROR: taxonomy missing: {BEHAVIOR_TAXONOMY}\n")
        sys.exit(2)
    with open(BEHAVIOR_TAXONOMY, "r", encoding="utf-8") as fh:
        taxonomy_text = fh.read()
    registry |= parse_yaml_paths_from_codeblocks(taxonomy_text)
    registry |= parse_header_paths(taxonomy_text)
    registry |= parse_table_field_paths(taxonomy_text)
    registry |= parse_section_table_field_paths(taxonomy_text)

    # Defensive: every top-level key registered even if the schema walker
    # somehow drops one.
    registry |= SCHEMA_TOP_LEVEL_KEYS
    return registry


# Module-level cache of open-maps derived from the last build_schema_registry()
# call. Populated by _walk_schema; consumed by is_phantom.
_DERIVED_OPEN_MAPS: Set[str] = set()


# Match `foo.bar` or `foo.bar.baz` (≥1 dot) where every segment is a snake_case
# identifier. Backticks bracket the dotted form when used as inline code.
DOTTED_PATH_RE = re.compile(r"`([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+(?:\[\])*)`")


def extract_paths_from_skill(md_text: str) -> Iterable[Tuple[str, int]]:
    """Yield (dotted_path, line_number) for every plausible schema path
    found in INLINE PROSE — i.e., backticked dotted paths embedded in
    paragraphs, headers, table cells, and bullet lists.

    Wave 11b post-review (3a) scope clarification: this function does NOT
    descend into ```yaml ... ``` code blocks. Phantom paths added inside
    YAML examples in any of the 6 SKILL.md files that use them currently
    pass silently. The schema-validator test (test_schema_jsonschema.py's
    test_no_truly_invented_keys_outside_open_maps) catches phantom keys
    in actual goldens; YAML examples in SKILLs are documentation, not
    authoritative claims, and are out of scope for this gate. If a future
    reviewer wants tighter coverage, extend this function to also yield
    paths from `parse_yaml_paths_from_codeblocks(md_text)` (a helper that
    already exists for parsing the taxonomy registry — its application to
    SKILL example blocks would be the natural extension)."""
    for i, line in enumerate(md_text.splitlines(), start=1):
        for m in DOTTED_PATH_RE.finditer(line):
            yield m.group(1), i


def is_phantom(path: str, registry: Set[str]) -> bool:
    """A path is phantom iff its first segment is a schema top-level AND
    neither the path nor any of its `[]`-stripped prefixes appears in the
    registry, AND no open-map prefix swallows it."""
    head = path.split(".")[0]
    if head not in SCHEMA_TOP_LEVEL_KEYS:
        return False
    if any(path.startswith(prefix) for prefix in DENYLIST_PREFIXES):
        return False
    normalized = path.replace("[]", "")
    if normalized in registry:
        return False
    # Open-map: any path under a known open-map prefix is accepted. Two
    # sources merge: the static OPEN_MAP_POINTS (legacy) and the
    # _DERIVED_OPEN_MAPS populated from adapter-spec.schema.json's
    # additionalProperties:true blocks during build_schema_registry().
    all_open_maps = OPEN_MAP_POINTS | _DERIVED_OPEN_MAPS
    for open_prefix in all_open_maps:
        if normalized == open_prefix or normalized.startswith(open_prefix + "."):
            return False
    # Walk upward — if a registered prefix is found and the trailing segments
    # are an open-map continuation, accept.
    parts = normalized.split(".")
    for i in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in all_open_maps:
            return False
    # Final defensive check: registered top-level alone is OK.
    if len(parts) == 1 and head in registry:
        return False
    return True


def discover_skill_files() -> List[str]:
    files: List[str] = []
    for root in SKILL_DIRS:
        files.extend(glob.glob(os.path.join(root, "**", "SKILL.md"), recursive=True))
        files.extend(glob.glob(os.path.join(root, "**", "*.md"), recursive=True))
    seen: Set[str] = set()
    out: List[str] = []
    for f in files:
        if f not in seen and os.path.isfile(f):
            seen.add(f)
            out.append(f)
    # Exclude the registry trees — they ARE the vocabulary; checking them
    # against themselves would be circular. See REGISTRY_DIRS.
    root_prefix = REPO_ROOT.replace(os.sep, "/").rstrip("/") + "/"
    filtered: List[str] = []
    for f in out:
        rel = f.replace(os.sep, "/")
        if rel.startswith(root_prefix):
            rel = rel[len(root_prefix):]
        if any(rel.startswith(d) for d in REGISTRY_DIRS):
            continue
        filtered.append(f)
    return sorted(filtered)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verbose", action="store_true", help="Print every checked path")
    args = p.parse_args(argv)

    registry = build_schema_registry()
    if not registry:
        sys.stderr.write("ERROR: schema registry empty (parse failure)\n")
        return 2

    skill_files = discover_skill_files()
    if not skill_files:
        sys.stderr.write(
            "ERROR: no *.md files found under any of SKILL_DIRS\n")
        return 2

    # An empty per-tree result is a finding, not a pass: a directory rename
    # would otherwise silently drop a whole skill surface from the gate
    # while the run still reported EXIT 0.
    for root in SKILL_DIRS:
        if not any(f.startswith(root + os.sep) for f in skill_files):
            sys.stderr.write(
                f"ERROR: skill dir contributed zero scanned files: {root}\n"
                f"       (moved/renamed tree, or every file excluded by REGISTRY_DIRS)\n")
            return 2

    phantoms: List[Tuple[str, str, int]] = []
    waived: List[Tuple[str, str, int]] = []
    waivers_hit: Set[Tuple[str, str]] = set()
    checked = 0
    for sf in skill_files:
        with open(sf, "r", encoding="utf-8") as fh:
            text = fh.read()
        for path, line_no in extract_paths_from_skill(text):
            checked += 1
            if is_phantom(path, registry):
                rel = os.path.relpath(sf, REPO_ROOT).replace(os.sep, "/")
                key = (rel, path)
                if key in KNOWN_PHANTOMS:
                    waivers_hit.add(key)
                    waived.append((rel, path, line_no))
                else:
                    phantoms.append((rel, path, line_no))
            elif args.verbose:
                rel = os.path.relpath(sf, REPO_ROOT)
                print(f"OK   {rel}:{line_no} {path}")

    stale_waivers = sorted(set(KNOWN_PHANTOMS) - waivers_hit)

    print(f"=== Schema contract test ===")
    print(f"Files scanned: {len(skill_files)}")
    print(f"Schema paths in registry: {len(registry)}")
    print(f"Dotted paths checked: {checked}")
    if waived:
        print(f"Waived phantom paths: {len(waived)} (see KNOWN_PHANTOMS)")
        for rel, path, line_no in waived:
            print(f"  WAIVED  {rel}:{line_no}  `{path}`")
    if stale_waivers:
        print(f"Stale waivers: {len(stale_waivers)}")
        for rel, path in stale_waivers:
            print(f"  STALE   {rel}  `{path}` — no longer phantom; delete this KNOWN_PHANTOMS entry")
        print("EXIT 1 — a waived phantom was fixed; the waiver must shrink with it.")
        return 1
    if phantoms:
        print(f"Phantom paths detected: {len(phantoms)}")
        for rel, path, line_no in phantoms:
            print(f"  PHANTOM {rel}:{line_no}  `{path}`")
        print("EXIT 1 — at least one SKILL references a path absent from the canonical schema.")
        return 1
    print("All paths resolve to the canonical schema (waivers aside). EXIT 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
