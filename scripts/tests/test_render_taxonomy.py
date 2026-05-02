"""Phase 2.4 CI gate: behavior-taxonomy.md must match the rendered output
of behavior-taxonomy.yaml.

Catches the case where someone edits the .md directly (instead of the .yaml
source-of-truth) — the next CI run flags the drift.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "render-taxonomy.py"

# Load the script as a module without running its main()
spec = importlib.util.spec_from_file_location("render_taxonomy", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise unittest.SkipTest(f"Cannot load {SCRIPT_PATH}")
render_taxonomy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_taxonomy)


class TestTaxonomyRenderDrift(unittest.TestCase):
    """`behavior-taxonomy.md` must equal `render_taxonomy(behavior-taxonomy.yaml)`."""

    def test_md_matches_yaml_render(self):
        taxonomy = render_taxonomy.load_yaml()
        rendered = render_taxonomy.render(taxonomy)
        with open(render_taxonomy.MD_PATH) as fp:
            on_disk = fp.read()
        if on_disk != rendered:
            # Show a small diff for fast triage
            import difflib
            diff = "\n".join(list(difflib.unified_diff(
                on_disk.splitlines(),
                rendered.splitlines(),
                fromfile="behavior-taxonomy.md (on disk)",
                tofile="behavior-taxonomy.yaml (rendered)",
                n=2,
            ))[:40])
            self.fail(
                "behavior-taxonomy.md is out of sync with behavior-taxonomy.yaml.\n"
                "Run `python3 scripts/render-taxonomy.py` to regenerate, then commit.\n\n"
                f"Diff (first 40 lines):\n{diff}"
            )

    def test_yaml_loads_with_required_top_level_keys(self):
        taxonomy = render_taxonomy.load_yaml()
        for required in ("taxonomy_version", "intro", "how_to_read", "enumerations", "quirks_taxa", "sources"):
            self.assertIn(required, taxonomy,
                          f"behavior-taxonomy.yaml missing top-level key {required!r}")

    def test_taxa_have_required_fields(self):
        taxonomy = render_taxonomy.load_yaml()
        missing = []
        for taxon in taxonomy["quirks_taxa"]:
            for key in ("id", "description", "surfaces_in"):
                if key not in taxon:
                    missing.append(f"taxon {taxon.get('id', '?')!r} missing {key!r}")
        self.assertEqual(missing, [], "\n".join(missing))

    def test_taxa_ids_are_unique(self):
        taxonomy = render_taxonomy.load_yaml()
        ids = [t["id"] for t in taxonomy["quirks_taxa"]]
        seen = set()
        dupes = set()
        for tid in ids:
            if tid in seen:
                dupes.add(tid)
            seen.add(tid)
        self.assertEqual(dupes, set(), f"duplicate taxon ids: {sorted(dupes)}")


if __name__ == "__main__":
    unittest.main()
