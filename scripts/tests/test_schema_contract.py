#!/usr/bin/env python3
"""Schema contract test.

Every dotted path used in any SKILL.md under prebid-server-{go,java}/read/skills/
must resolve to a defined section/key in either:
- prebid-server-go/read/skills/shared/adapter-spec.md, or
- prebid-server-go/read/skills/shared/behavior-taxonomy.md.

Catches "phantom field" bugs: a SKILL claims a field that does not exist in
the canonical schema. This bug class drove most Wave 2 fixes in PR #1.

Usage (from repo root):
    python3 scripts/tests/test_schema_contract.py
    python3 scripts/tests/test_schema_contract.py --verbose

Exit codes:
    0  every dotted path resolves
    1  one or more phantom paths detected
    2  schema/taxonomy could not be parsed (sanity-check failure)
"""

from __future__ import annotations

import argparse
import glob
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
ADAPTER_SPEC = os.path.join(
    REPO_ROOT, "prebid-server-go", "read", "skills", "shared", "adapter-spec.md"
)
BEHAVIOR_TAXONOMY = os.path.join(
    REPO_ROOT, "prebid-server-go", "read", "skills", "shared", "behavior-taxonomy.md"
)
SKILL_DIRS = (
    os.path.join(REPO_ROOT, "prebid-server-go", "read", "skills"),
    os.path.join(REPO_ROOT, "prebid-server-java", "read", "skills"),
)

# Top-level keys recognised as belonging to the schema. Phantom-path detection
# runs ONLY on dotted paths whose first segment matches one of these — that
# filters out package paths (prebid/prebid-server.go), URLs (http.example.com),
# and unrelated dotted tokens.
SCHEMA_TOP_LEVEL_KEYS = frozenset({
    "adapter_spec_version", "spec_kind", "source_language",
    "provenance", "meta", "aliases", "lifecycle", "bidder_info",
    "bidder_params_json", "bidder_params_sha256", "params",
    "code", "tests", "spring_config", "bidder_class", "code_naming",
    "iab_category_storage", "ext_pojo_construction", "currency_conversion",
    "headers_constructed", "deploy_time_tokens", "quirks", "cross_language",
})

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


# Explicit registry supplement: schema fields that the markdown parser misses
# because they're documented in prose tables under section headers in formats
# the parser doesn't catch. Curated from `adapter-spec.md` section-by-section.
# Adding here means: "this path EXISTS in the canonical schema even if my
# parser couldn't extract it." Removing or omitting one would re-surface real
# phantoms; keep this list aligned with the schema by hand on schema bumps.
SCHEMA_REGISTRY_EXTRAS = frozenset({
    # cross_language fields
    "cross_language.go_artifacts", "cross_language.java_artifacts",
    "cross_language.go_specific_concerns", "cross_language.java_specific_concerns",
    "cross_language.port_concerns", "cross_language.port_lineage",
    "cross_language.reviewer_cohort",
    "cross_language.go_artifacts.bidder_dir", "cross_language.go_artifacts.package_name",
    "cross_language.go_artifacts.bidder_constant",
    "cross_language.java_artifacts.bidder_dir", "cross_language.java_artifacts.bidder_class",
    "cross_language.java_artifacts.config_class", "cross_language.java_artifacts.yaml_path",
    "cross_language.java_artifacts.proto_dir",
    "cross_language.port_concerns.aliases_inverted", "cross_language.port_concerns.yaml_unification",
    "cross_language.port_concerns.mutation_idiom_divergence",
    "cross_language.port_concerns.package_directory_mismatch",
    "cross_language.port_concerns.multi_file_layout",
    "cross_language.port_concerns.custom_unmarshaljson_present",
    "cross_language.reviewer_cohort.go", "cross_language.reviewer_cohort.java",
    "cross_language.reviewer_cohort.cross_language_coordinator",
    # bidder_info fields
    "bidder_info.disabled", "bidder_info.default_enabled",
    "bidder_info.modifying_vast_xml_allowed", "bidder_info.endpoint",
    "bidder_info.endpoint_compression", "bidder_info.endpoint_construction",
    "bidder_info.endpoint_construction.kind",
    "bidder_info.geoscope", "bidder_info.gvl_vendor_id", "bidder_info.maintainer",
    "bidder_info.maintainer.email", "bidder_info.capabilities", "bidder_info.ortb_version",
    "bidder_info.yaml_field_name_quirks",
    # meta fields
    "meta.alias_of", "meta.disabled", "meta.bidder_name", "meta.is_alias",
    "meta.module_path_major", "meta.java_artifact_version", "meta.parent_aliases",
    "meta.whitelabel_only", "meta.alias_metadata",
    # code fields (general structure)
    "code.make_requests", "code.make_bids",
    "code.make_requests.batching", "code.make_requests.batching.rules",
    "code.make_requests.request_body", "code.make_requests.request_body.kind",
    "code.make_requests.request_body.custom_body_type",
    "code.make_requests.helpers", "code.make_bids.helpers",
    "code.make_requests.mutation", "code.make_requests.mutation.mutates_request",
    "code.make_requests.mutation.go_idiom", "code.make_requests.mutation.java_idiom",
    "code.make_requests.imp_ext_unmarshal", "code.make_requests.imp_ext_unmarshal.kind",
    "code.make_requests.endpoint_resolution", "code.make_requests.endpoint_resolution.kind",
    "code.make_requests.endpoint_resolution.mechanism_go",
    "code.make_requests.endpoint_resolution.mechanism_java",
    "code.make_bids.response_type", "code.make_bids.custom_response_type",
    "code.make_bids.bid_type_resolution", "code.make_bids.bid_type_resolution.method_chain",
    "code.make_bids.http_status_handling", "code.make_bids.http_status_handling.kind",
    "code.make_bids.application_status_handling",
    "code.make_bids.application_status_handling.kind",
    "code.make_bids.bid_pointer_pattern", "code.make_bids.bid_pointer_go_sibling",
    "code.make_bids.currency_overwrite_safety",
    "code.imports", "code.imports.has_jsonutil", "code.imports.has_template_engine",
    "code.imports.has_currency_helper",
    "code.file_layout", "code.file_layout.kind", "code.file_layout.files",
    "code.package_or_class", "code.directory_name", "code.package_directory_mismatch",
    # bidder_class fields (Java-only)
    "bidder_class.name", "bidder_class.parameterized_request_type",
    "bidder_class.parameterized_response_type",
    "bidder_class.constructor", "bidder_class.constructor.parameters",
    "bidder_class.constructor.arity",
    "bidder_class.helper_classes_co_located",
    "bidder_class.helper_classes_in_proto", "bidder_class.static_fields",
    "bidder_class.override_methods",
    # tests fields
    "tests.unit_test_methods_count", "tests.unit_test_loc",
    "tests.hand_written_test_methods", "tests.integration_test_class",
    "tests.integration_test_pattern", "tests.test_root_directory",
    "tests.go_directory_naming", "tests.java_it_folder_naming",
    "tests.uses_canonical_harness", "tests.fixture_handling",
    "tests.test_application_properties_entries_added",
    "tests.fixture_inventory.exemplary", "tests.fixture_inventory.supplemental",
    "tests.fixture_inventory.amp", "tests.fixture_inventory.video",
    "tests.fixture_inventory.videosupplemental", "tests.fixture_inventory.integration",
    "tests.fixture_inventory.dooh",
    # spring_config fields (Java-only)
    "spring_config.factory_class", "spring_config.factory_method",
    "spring_config.property_source_path",
    "spring_config.configuration_properties_class",
    "spring_config.configuration_properties_class.name",
    "spring_config.configuration_properties_class.extends",
    "spring_config.configuration_properties_class.extra_fields",
    "spring_config.configuration_properties_class.nested_classes",
    "spring_config.configuration_properties_class.lombok_annotations",
    "spring_config.bean_dependencies",
    # provenance fields
    "provenance.source", "provenance.source.repo", "provenance.source.ref",
    "provenance.source.resolved_commit", "provenance.source.fetch_method",
    "provenance.read", "provenance.read.skill_versions",
    "provenance.read.timestamp_utc", "provenance.read.operator",
    "provenance.warnings",
    # params fields
    "params.schema_interpretation", "params.ext_struct",
    "params.schema_interpretation.required_fields",
    "params.schema_interpretation.combinators_used",
    "params.schema_interpretation.flexible_types",
    "params.ext_struct.fields", "params.ext_struct.type_name",
    "params.ext_struct.package", "params.ext_struct.custom_unmarshal",
    "params.ext_struct.file",
    # code_naming (top-level)
    "code_naming.yaml_name", "code_naming.class_name_root",
    "code_naming.identifier_workaround", "code_naming.preserves_acronym_case",
    # iab_category_storage fields
    "iab_category_storage.storage_kind", "iab_category_storage.yaml_field",
    "iab_category_storage.go_data_file", "iab_category_storage.table_size",
    "iab_category_storage.injection",
    # ext_pojo_construction fields
    "ext_pojo_construction.framework_choice",
    "ext_pojo_construction.flexible_extension_used",
    "ext_pojo_construction.custom_unmarshal",
    "ext_pojo_construction.custom_unmarshal.kind",
    "ext_pojo_construction.custom_unmarshal.where_branched",
    # currency_conversion fields
    "currency_conversion.used", "currency_conversion.helper",
    "currency_conversion.injection",
    "currency_conversion.bid_request_passed_for_context",
    # headers_constructed fields
    "headers_constructed.pre_built_in_constructor",
    "headers_constructed.per_request_dynamic",
    "headers_constructed.custom_headers",
    "headers_constructed.authentication_kind",
    "headers_constructed.authentication_input",
    # aliases fields
    "aliases.bidder_name", "aliases.parent", "aliases.config_form",
    "aliases.test_assets", "aliases.test_assets.it_class",
    "aliases.test_assets.fixture_dir", "aliases.test_assets.fixture_file_count",
    # lifecycle fields
    "lifecycle.rename", "lifecycle.rename.old_name", "lifecycle.rename.new_name",
    "lifecycle.rename.alias_back", "lifecycle.rename.alias_back_form",
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


def build_schema_registry() -> Set[str]:
    """Union of paths defined by adapter-spec.md and behavior-taxonomy.md."""
    registry: Set[str] = set()
    for path in (ADAPTER_SPEC, BEHAVIOR_TAXONOMY):
        if not os.path.isfile(path):
            sys.stderr.write(f"ERROR: schema source missing: {path}\n")
            sys.exit(2)
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        registry |= parse_yaml_paths_from_codeblocks(text)
        registry |= parse_header_paths(text)
        registry |= parse_table_field_paths(text)
        registry |= parse_section_table_field_paths(text)
    # Defensive — ensure every top-level key is registered even if a typo in
    # either source would otherwise drop a real top-level from the registry.
    registry |= SCHEMA_TOP_LEVEL_KEYS
    # Add the curated supplement: schema fields the markdown parser misses
    # because they're documented in patterns the regex doesn't catch.
    registry |= SCHEMA_REGISTRY_EXTRAS
    return registry


# Match `foo.bar` or `foo.bar.baz` (≥1 dot) where every segment is a snake_case
# identifier. Backticks bracket the dotted form when used as inline code.
DOTTED_PATH_RE = re.compile(r"`([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+(?:\[\])*)`")


def extract_paths_from_skill(md_text: str) -> Iterable[Tuple[str, int]]:
    """Yield (dotted_path, line_number) for every plausible schema path."""
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
    # Open-map: any path under a known open-map prefix is accepted.
    for open_prefix in OPEN_MAP_POINTS:
        if normalized == open_prefix or normalized.startswith(open_prefix + "."):
            return False
    # Walk upward — if a registered prefix is found and the trailing segments
    # are an open-map continuation, accept.
    parts = normalized.split(".")
    for i in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in OPEN_MAP_POINTS:
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
    # Exclude shared/ docs — they ARE the registry; checking them against
    # themselves would be circular.
    out = [f for f in out if "/skills/shared/" not in f.replace(os.sep, "/")]
    return sorted(out)


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
        sys.stderr.write("ERROR: no SKILL.md files found under read/skills/\n")
        return 2

    phantoms: List[Tuple[str, str, int]] = []
    checked = 0
    for sf in skill_files:
        with open(sf, "r", encoding="utf-8") as fh:
            text = fh.read()
        for path, line_no in extract_paths_from_skill(text):
            checked += 1
            if is_phantom(path, registry):
                rel = os.path.relpath(sf, REPO_ROOT)
                phantoms.append((rel, path, line_no))
            elif args.verbose:
                rel = os.path.relpath(sf, REPO_ROOT)
                print(f"OK   {rel}:{line_no} {path}")

    print(f"=== Schema contract test ===")
    print(f"Files scanned: {len(skill_files)}")
    print(f"Schema paths in registry: {len(registry)}")
    print(f"Dotted paths checked: {checked}")
    if phantoms:
        print(f"Phantom paths detected: {len(phantoms)}")
        for rel, path, line_no in phantoms:
            print(f"  PHANTOM {rel}:{line_no}  `{path}`")
        print("EXIT 1 — at least one SKILL references a path absent from the canonical schema.")
        return 1
    print("All paths resolve to the canonical schema. EXIT 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
