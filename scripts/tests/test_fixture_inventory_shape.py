"""A count-named `integration_test_pattern` must agree with its entry count.

WHY
    `tests.integration_test_pattern` names the shape of a Java golden's IT fixture
    set, and two of its values are defined by a file count:
    `4-file-split` is one bidder call plus the auction pair, `6-file-with-cache`
    adds a cache pair. `none` means no integration test at all. So each of those
    three predicts exactly how many `fixture_inventory.integration[]` entries the
    golden should carry, and nothing checked the prediction.

    Both goldens that disagreed were wrong, in opposite directions:

      beachfront   4-file-split with SIX entries. The two extra were
                   test-beachfront-{banner,video}-bid-* filenames that have never
                   existed in upstream history, carrying `pending-operator-fetch`
                   digests so the drift detector could only check presence.

      appnexus     6-file-with-cache with EIGHT entries. Here the inventory was
                   right and the label was wrong: AppnexusVideoTest.java stubs two
                   bidder calls plus a cache call, so eight files is the real shape
                   and `custom` is the value for it.

    One field contradicting another inside the same document is the cheapest kind
    of defect to catch and, unchecked, one of the longest-lived.

WHAT THIS DOES NOT CHECK
    That the named files exist upstream, or that their digests match. That needs a
    checkout, and `scripts/sync-from-upstream.py` owns it. This gate is hermetic:
    it reads one golden and compares two of its own fields.

    `multi-folder` and `custom` are deliberately unconstrained -- neither predicts
    a count, which is what makes them the right home for a non-standard shape.
    `custom` is still held to carrying entries at all, because a shape with no
    inventory is not a custom shape, it is an unread one.

Run: python3 -m unittest scripts.tests.test_fixture_inventory_shape -v
"""

from __future__ import annotations

import glob
import json
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "adapter-spec.schema.json"

# Only the values whose NAME asserts a count.
EXPECTED_COUNT = {"4-file-split": 4, "6-file-with-cache": 6, "none": 0}

# Values that describe a shape without predicting a count.
UNCONSTRAINED = {"multi-folder", "custom"}


def goldens() -> list[Path]:
    out = []
    for lang in ("go", "java"):
        out.extend(sorted(Path(p) for p in glob.glob(
            str(REPO_ROOT / f"prebid-server-{lang}" / "read" / "test-fixtures" / "*.golden.spec.yaml"))))
    return out


def read_tests_block(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("tests") or {}


class TestFixtureInventoryShape(unittest.TestCase):
    def test_corpus_is_not_empty(self):
        """A zero-golden scan is a setup error, not a clean result."""
        self.assertGreater(len(goldens()), 30, "the golden glob stopped matching")

    def test_count_named_patterns_match_their_entry_count(self):
        bad = []
        for path in goldens():
            t = read_tests_block(path)
            pattern = t.get("integration_test_pattern")
            if pattern not in EXPECTED_COUNT:
                continue
            entries = (t.get("fixture_inventory") or {}).get("integration") or []
            if len(entries) != EXPECTED_COUNT[pattern]:
                bad.append(f"{path.name}: integration_test_pattern={pattern!r} predicts "
                           f"{EXPECTED_COUNT[pattern]} entries, inventory carries {len(entries)}")
        self.assertEqual([], bad,
                         "a golden's pattern label contradicts its own inventory. Either the "
                         "inventory names files that are not there, or the label is wrong for "
                         "the shape -- check which against upstream before editing either:\n  "
                         + "\n  ".join(bad))

    def test_every_declared_pattern_is_admitted_by_the_schema(self):
        """The defect that let `custom` be instructed and rejected at once. A value
        a golden declares must be one the schema validates, or Step 4 fails on a
        spec built by following the read skill."""
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

        def find(node, name):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == name and isinstance(v, dict) and "enum" in v:
                        return v["enum"]
                    got = find(v, name)
                    if got is not None:
                        return got
            elif isinstance(node, list):
                for v in node:
                    got = find(v, name)
                    if got is not None:
                        return got
            return None

        bad = []
        for field in ("integration_test_pattern", "java_it_folder_naming"):
            enum = find(schema, field)
            self.assertIsNotNone(enum, f"{field} lost its enum -- nothing constrains it now")
            for path in goldens():
                value = read_tests_block(path).get(field)
                if value not in enum:
                    bad.append(f"{path.name}: {field}={value!r} is not in the schema enum {enum}")
        self.assertEqual([], bad, "\n  ".join(bad))

    def test_unconstrained_patterns_still_carry_an_inventory(self):
        """`multi-folder` and `custom` do not predict a count, but a golden that
        claims a non-standard shape and records nothing has not been read."""
        bad = []
        for path in goldens():
            t = read_tests_block(path)
            if t.get("integration_test_pattern") not in UNCONSTRAINED:
                continue
            entries = (t.get("fixture_inventory") or {}).get("integration") or []
            if not entries:
                bad.append(f"{path.name}: pattern is non-standard with an empty inventory")
        self.assertEqual([], bad, "\n  ".join(bad))


if __name__ == "__main__":
    unittest.main()
