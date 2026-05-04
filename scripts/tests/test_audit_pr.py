"""Phase 4.2 unit tests for scripts/audit-pr.py.

Verifies URL parsing, prompt construction, and Claude-response JSON
extraction. Does not exercise the network/API call path.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit-pr.py"

spec = importlib.util.spec_from_file_location("audit_pr", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise unittest.SkipTest(f"Cannot load {SCRIPT_PATH}")
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)


class TestParsePrUrl(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(("prebid", "prebid-server", 4639),
                         ap.parse_pr_url("https://github.com/prebid/prebid-server/pull/4639"))

    def test_trailing_slash(self):
        self.assertEqual(("prebid", "prebid-server-java", 4326),
                         ap.parse_pr_url("https://github.com/prebid/prebid-server-java/pull/4326/"))

    def test_http_accepted(self):
        self.assertEqual(("foo", "bar", 1),
                         ap.parse_pr_url("http://github.com/foo/bar/pull/1"))

    def test_invalid_url_raises(self):
        with self.assertRaises(ValueError):
            ap.parse_pr_url("https://example.com/foo/bar")
        with self.assertRaises(ValueError):
            ap.parse_pr_url("not a url")
        with self.assertRaises(ValueError):
            ap.parse_pr_url("https://github.com/foo/bar/issues/1")  # not /pull/


class TestLoaders(unittest.TestCase):
    def test_load_taxonomy_taxa_returns_list(self):
        taxa = ap.load_taxonomy_taxa()
        self.assertIsInstance(taxa, list)
        self.assertGreater(len(taxa), 30, "Phase 2.4 onward: 50+ taxa")
        for t in taxa[:5]:
            self.assertIn("id", t)

    def test_load_rule_summaries_returns_46(self):
        # Wave 11b B5 #6: hardcoded count assertion removed (was tautology against
        # len(rules) and required manual update on every rule-count change).
        # Function name kept for human-readability; test now validates that rules
        # are loaded non-empty with the required per-rule fields, which is the
        # genuine drift gate.
        rules = ap.load_rule_summaries()
        self.assertGreater(len(rules), 0, "load_rule_summaries returned empty list")
        for r in rules[:5]:
            self.assertIn("id", r)
            self.assertIn("title", r)

    def test_load_java_edge_cases_nonempty(self):
        text = ap.load_java_edge_cases()
        self.assertIn("#18", text)
        self.assertIn("#34", text)


class TestBuildPrompt(unittest.TestCase):
    def test_includes_pr_metadata(self):
        pr_meta = {
            "title": "Add ExampleAdapter",
            "body": "This PR adds the ExampleAdapter bidder...",
            "author": {"login": "alice"},
            "state": "MERGED",
            "mergedAt": "2026-05-02T00:00:00Z",
            "headRefOid": "abc123",
            "files": [{"path": "f1"}, {"path": "f2"}],
            "additions": 10,
            "deletions": 5,
            "diff": "diff --git a/foo b/foo\n+example\n",
        }
        prompt = ap.build_prompt(pr_meta, "https://github.com/prebid/prebid-server/pull/9999",
                                  ap.load_taxonomy_taxa(), ap.load_rule_summaries(),
                                  ap.load_java_edge_cases())
        self.assertIn("ExampleAdapter", prompt)
        self.assertIn("alice", prompt)
        self.assertIn("Files changed: 2", prompt)
        self.assertIn("(+10 / -5)", prompt)
        self.assertIn("abc123", prompt)
        self.assertIn("Existing taxonomy taxa", prompt)
        self.assertIn("Existing port-translation rules", prompt)
        self.assertIn("Java edge cases #18-#34 catalog", prompt)

    def test_truncates_long_diff(self):
        pr_meta = {"title": "T", "body": "B", "diff": "X" * 20000, "files": [], "additions": 0, "deletions": 0}
        prompt = ap.build_prompt(pr_meta, "https://github.com/foo/bar/pull/1",
                                  ap.load_taxonomy_taxa(), ap.load_rule_summaries(),
                                  ap.load_java_edge_cases())
        self.assertIn("[... truncated for prompt size ...]", prompt)


class TestParseClaudeJson(unittest.TestCase):
    def test_extracts_codefenced_json(self):
        text = '''Here is my analysis:

```json
{"verdict": "no-novelty", "rationale": "matches taxon X"}
```

End.'''
        out = ap.parse_claude_json(text)
        self.assertEqual("no-novelty", out["verdict"])

    def test_extracts_balanced_braces_no_codefence(self):
        text = 'Some preamble. {"verdict": "novel-pattern", "rationale": "..."} trailing.'
        out = ap.parse_claude_json(text)
        self.assertEqual("novel-pattern", out["verdict"])

    def test_extracts_nested_objects(self):
        text = '{"verdict": "novel-pattern", "novel_pattern_proposal": {"name": "foo", "extends_existing": null}}'
        out = ap.parse_claude_json(text)
        self.assertEqual("foo", out["novel_pattern_proposal"]["name"])

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            ap.parse_claude_json("just plain prose, no JSON")

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            ap.parse_claude_json("```json\n{not valid json}\n```")


class TestRenderMd(unittest.TestCase):
    def test_no_novelty_render(self):
        verdict = {
            "verdict": "no-novelty",
            "rationale": "Matches existing taxon `bidder-rename-three-step`.",
            "matched_taxa": ["bidder-rename-three-step"],
            "matched_rules": [43],
            "matched_java_edge_cases": [33],
            "novel_pattern_proposal": None,
        }
        pr_meta = {"title": "T", "author": {"login": "alice"}, "files": [],
                   "additions": 0, "deletions": 0, "headRefOid": "abc"}
        md = ap.render_md(verdict, pr_meta, "https://github.com/foo/bar/pull/1")
        self.assertIn("Verdict: `no-novelty`", md)
        self.assertIn("`bidder-rename-three-step`", md)
        self.assertIn("Rule 43", md)
        self.assertNotIn("Proposed novel pattern", md)

    def test_novel_pattern_render(self):
        verdict = {
            "verdict": "novel-pattern",
            "rationale": "PR introduces a brand-new auth method (mTLS pinning).",
            "matched_taxa": [],
            "matched_rules": [],
            "matched_java_edge_cases": [],
            "novel_pattern_proposal": {
                "name": "mtls-pinned-auth",
                "description": "Adapter authenticates via mTLS with cert pinning",
                "extends_existing": None,
                "proposed_artifact": "taxon",
                "rationale_for_promotion": "Distinct from bearer-token, hmac-digest",
            },
        }
        pr_meta = {"title": "T", "author": {"login": "bob"}, "files": [],
                   "additions": 0, "deletions": 0, "headRefOid": "def"}
        md = ap.render_md(verdict, pr_meta, "https://github.com/foo/bar/pull/2")
        self.assertIn("Proposed novel pattern", md)
        self.assertIn("`mtls-pinned-auth`", md)
        self.assertIn("`taxon`", md)


if __name__ == "__main__":
    unittest.main()
