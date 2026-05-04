"""Phase 2.5 CI gate: port-translation-rules.md must match the rendered output
of port-translation-rules.yaml.

Catches the case where someone edits the .md directly (instead of the .yaml
source-of-truth) — the next CI run flags the drift.

Also enforces structural invariants on the YAML:
- Required top-level keys present
- 46 rules total (post-Phase-2.5)
- Rule IDs are unique
- Rules 44, 45, 46 (Phase 2.5 additions) are present
- Each rule has the required fields
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "render-port-rules.py"

spec = importlib.util.spec_from_file_location("render_port_rules", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise unittest.SkipTest(f"Cannot load {SCRIPT_PATH}")
render_port_rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_port_rules)


class TestPortRulesRenderDrift(unittest.TestCase):
    """`port-translation-rules.md` MUST equal `render(port-translation-rules.yaml)`."""

    def test_md_matches_yaml_render(self):
        data = render_port_rules.load_yaml()
        rendered = render_port_rules.render(data)
        with open(render_port_rules.MD_PATH) as fp:
            on_disk = fp.read()
        if on_disk != rendered:
            import difflib
            diff = "\n".join(list(difflib.unified_diff(
                on_disk.splitlines(),
                rendered.splitlines(),
                fromfile="port-translation-rules.md (on disk)",
                tofile="port-translation-rules.yaml (rendered)",
                n=2,
            ))[:50])
            self.fail(
                "port-translation-rules.md is out of sync with port-translation-rules.yaml.\n"
                "Run `python3 scripts/render-port-rules.py` to regenerate, then commit.\n\n"
                f"Diff (first 50 lines):\n{diff}"
            )

    def test_yaml_loads_with_required_top_level_keys(self):
        data = render_port_rules.load_yaml()
        for required in ("rules_version", "intro", "toc", "how_to_use", "sections", "summary", "sources"):
            self.assertIn(required, data,
                          f"port-translation-rules.yaml missing top-level key {required!r}")

    def test_rule_count_is_46(self):
        """Phase 2.5 brings the rule count to 46 (Rules 44-46 added per ADR-003/004/005)."""
        data = render_port_rules.load_yaml()
        rules = []
        for sec in data["sections"]:
            if sec.get("kind") == "rules":
                rules.extend(sec["rules"])
        self.assertEqual(len(rules), 46,
                         f"Expected 46 rules, found {len(rules)}: {sorted(r['id'] for r in rules)}")

    def test_rule_ids_are_unique_and_contiguous(self):
        """Rule IDs MUST be the integers 1..46 with no gaps or duplicates."""
        data = render_port_rules.load_yaml()
        ids = []
        for sec in data["sections"]:
            if sec.get("kind") == "rules":
                ids.extend(r["id"] for r in sec["rules"])
        self.assertEqual(sorted(ids), list(range(1, 47)),
                         f"Rule IDs are not 1..46: got {sorted(ids)}")

    def test_phase_2_5_rules_present(self):
        """Rules 44 (alias-empire), 45 (disabled-by-default), 46 (naming-convention) MUST exist."""
        data = render_port_rules.load_yaml()
        rules_by_id = {}
        for sec in data["sections"]:
            if sec.get("kind") == "rules":
                for r in sec["rules"]:
                    rules_by_id[r["id"]] = r
        self.assertIn(44, rules_by_id, "Rule 44 (alias-empire-consolidation) missing")
        self.assertIn(45, rules_by_id, "Rule 45 (disabled-by-default-Java-alias) missing")
        self.assertIn(46, rules_by_id, "Rule 46 (naming-convention-normalization) missing")
        # Spot-check titles to catch accidentally-renamed rules
        self.assertIn("alias-empire", rules_by_id[44]["title"].lower())
        self.assertIn("disabled-by-default", rules_by_id[45]["title"].lower())
        self.assertIn("naming-convention", rules_by_id[46]["title"].lower())

    def test_rule_43_sub_types_documented(self):
        """ADR-006: Rule 43 body MUST mention the five sub-types (refined
        2026-05-03 — added mirror-topology and inverted-parent)."""
        data = render_port_rules.load_yaml()
        rule_43 = None
        for sec in data["sections"]:
            if sec.get("kind") == "rules":
                for r in sec["rules"]:
                    if r["id"] == 43:
                        rule_43 = r
                        break
        assert rule_43 is not None, "Rule 43 not found"
        body = rule_43["body"]
        for subtype in (
            "bilateral", "java-leads", "go-leads",
            "mirror-topology", "inverted-parent",
        ):
            self.assertIn(subtype, body,
                          f"Rule 43 body missing sub-type {subtype!r} (ADR-006)")

    def test_rules_have_required_fields(self):
        """Every rule MUST have: id, title, pattern, spec_field_driver, body."""
        data = render_port_rules.load_yaml()
        missing = []
        for sec in data["sections"]:
            if sec.get("kind") != "rules":
                continue
            for r in sec["rules"]:
                for key in ("id", "title", "pattern", "spec_field_driver", "body"):
                    if key not in r or not r[key]:
                        missing.append(f"Rule {r.get('id', '?')!r} missing {key!r}")
        self.assertEqual(missing, [], "\n".join(missing))

    def test_rules_version_is_phase_2_5(self):
        """Phase 2.5 bumps rules_version to 0.2.0 (was 0.1.0 with 43 rules)."""
        data = render_port_rules.load_yaml()
        self.assertEqual(data["rules_version"], "0.2.0",
                         f"Expected rules_version 0.2.0 (Phase 2.5), got {data['rules_version']!r}")

    def test_render_rejects_unknown_yaml_keys(self):
        """Wave 11b B4 C4: render() must raise ValueError when the YAML grows
        a new top-level key the renderer doesn't consume. Catches the silent-
        drop class of bug where someone adds YAML data and forgets to wire it
        through render().
        """
        data = render_port_rules.load_yaml()
        data_with_phantom = {**data, "phantom_section_added_by_test": "bogus"}
        with self.assertRaises(ValueError) as cm:
            render_port_rules.render(data_with_phantom)
        self.assertIn("phantom_section_added_by_test", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
