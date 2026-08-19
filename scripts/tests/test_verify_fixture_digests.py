"""The fixture-digest verifier's statuses, and the two ways it could lie.

WHY THE STATUSES MATTER SEPARATELY
    Three of the four are ways of NOT being verified, and collapsing any of them
    into a pass reproduces the gap this script closes:

      MISMATCH      a recorded value disagrees with the file at the pin. The
                    defect that already happened: fourteen digests in the Go
                    adverxo golden were 40 hex characters, sha1 length and not the
                    sha1 either, while every `bytes` beside them was right.
      UNMEASURED    nothing recorded to check. `bytes: 0` beside no digest is
                    indistinguishable from a genuinely empty file, which is why it
                    is a status rather than a pass.
      UNVERIFIABLE  the path is not at the pin, the entry is prose, or the whole
                    BUCKET is one the resolver does not handle. That last one was
                    invisible before: `java/huaweiads` records 23 entries under
                    `integration_subdirs` and the Java resolver reads only
                    `integration`, so nothing ever looked at them.

    `bytes` is checked alongside the digest deliberately. It is the second witness,
    and on adverxo it was the witness that had been measured correctly.

Run: python3 -m unittest scripts.tests.test_verify_fixture_digests -v
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify-fixture-digests.py"

_spec = importlib.util.spec_from_file_location("vfd", SCRIPT)
if _spec is None or _spec.loader is None:
    raise unittest.SkipTest(f"cannot load {SCRIPT}")
vfd = importlib.util.module_from_spec(_spec)
sys.modules["vfd"] = vfd
_spec.loader.exec_module(vfd)

BODY = b'{"ok": true}\n'
SHA = hashlib.sha256(BODY).hexdigest()


def make_checkout(tmp: Path, files: dict[str, bytes]) -> tuple[Path, str]:
    """A real one-commit git checkout, so `git show <pin>:<path>` is exercised
    rather than stubbed. The pin is what this script is about."""
    root = tmp / "upstream"
    root.mkdir()
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin:/usr/local/bin"}
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True, env=env)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                         capture_output=True, text=True, env=env).stdout.strip()
    return root, sha


def golden_doc(pin: str, inventory: dict) -> dict:
    return {
        "adapter_spec_version": "2.1.0",
        "provenance": {"source": {"resolved_commit": pin}},
        "meta": {"bidder_name": "kobler", "is_alias": False, "alias_of": None},
        "cross_language": {"go_artifacts": {"bidder_dir": "adapters/kobler"}},
        "tests": {"test_root_directory": "koblertest", "fixture_inventory": inventory},
    }


class TestStatuses(unittest.TestCase):
    def _run(self, inventory: dict, files: dict[str, bytes] | None = None):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, pin = make_checkout(tmp, files if files is not None else
                                      {"adapters/kobler/koblertest/exemplary/a.json": BODY})
            gp = tmp / "kobler.golden.spec.yaml"
            gp.write_text(yaml.safe_dump(golden_doc(pin, inventory)))
            return vfd.verify_golden(gp, "go", root, "unused-remote", offline=True)

    def test_matching_sha_and_bytes_verify(self):
        got = self._run({"exemplary": [{"filename": "a.json", "sha256": SHA,
                                        "bytes": len(BODY)}]})
        self.assertEqual([vfd.VERIFIED], [r.status for r in got], [r.detail for r in got])

    def test_wrong_sha_is_a_mismatch(self):
        got = self._run({"exemplary": [{"filename": "a.json", "sha256": "b" * 64,
                                        "bytes": len(BODY)}]})
        self.assertEqual([vfd.MISMATCH], [r.status for r in got])
        self.assertIn("sha256", got[0].detail)

    def test_wrong_bytes_is_a_mismatch_even_when_the_sha_is_right(self):
        """The adverxo shape, inverted. `bytes` is a witness, not decoration."""
        got = self._run({"exemplary": [{"filename": "a.json", "sha256": SHA,
                                        "bytes": len(BODY) + 1}]})
        self.assertEqual([vfd.MISMATCH], [r.status for r in got])
        self.assertIn("bytes", got[0].detail)

    def test_sha1_length_digest_is_a_mismatch_not_a_skip(self):
        """40 hex characters is not a sha256, and the resolver hands back None for
        it. Without the `bytes` claim beside it there would be nothing left to
        compare, so this asserts the entry still fails rather than passing."""
        got = self._run({"exemplary": [{"filename": "a.json", "sha256": "a" * 40,
                                        "bytes": len(BODY) + 5}]})
        self.assertEqual([vfd.MISMATCH], [r.status for r in got])

    def test_zero_bytes_and_no_digest_is_unmeasured(self):
        got = self._run({"exemplary": [{"filename": "a.json", "bytes": 0}]})
        self.assertEqual([vfd.UNMEASURED], [r.status for r in got])

    def test_absent_path_is_unverifiable(self):
        got = self._run({"exemplary": [{"filename": "gone.json", "sha256": SHA,
                                        "bytes": len(BODY)}]})
        self.assertEqual([vfd.UNVERIFIABLE], [r.status for r in got])
        self.assertIn("absent at", got[0].detail)

    def test_prose_entry_is_unverifiable(self):
        got = self._run({"exemplary": [{"filename": "40 fixtures (error paths)",
                                        "sha256": "pending-operator-fetch", "bytes": 0}]})
        self.assertEqual([vfd.UNVERIFIABLE], [r.status for r in got])

    def test_a_bucket_the_resolver_does_not_handle_is_reported(self):
        """The huaweiads hole: a bucket outside the resolver's set produced no
        result at all, so it was neither checked nor reported."""
        got = self._run({"exemplary": [{"filename": "a.json", "sha256": SHA,
                                        "bytes": len(BODY)}],
                         "some_other_bucket": ["x", "y", "z"]})
        statuses = [r.status for r in got]
        self.assertIn(vfd.UNVERIFIABLE, statuses)
        unver = [r for r in got if r.status == vfd.UNVERIFIABLE][0]
        self.assertIn("some_other_bucket", unver.origin)
        self.assertIn("3 entries", unver.detail)

    def test_an_empty_unhandled_bucket_is_not_reported(self):
        """`amp: []` is every golden's normal state; reporting it would bury the
        real finding under noise."""
        got = self._run({"exemplary": [{"filename": "a.json", "sha256": SHA,
                                        "bytes": len(BODY)}],
                         "amp": [], "video": []})
        self.assertEqual([vfd.VERIFIED], [r.status for r in got])

    def test_missing_resolved_commit_is_unverifiable(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _ = make_checkout(tmp, {"adapters/kobler/koblertest/exemplary/a.json": BODY})
            doc = golden_doc("", {"exemplary": [{"filename": "a.json", "sha256": SHA,
                                                "bytes": len(BODY)}]})
            doc["provenance"]["source"] = {}
            gp = tmp / "kobler.golden.spec.yaml"
            gp.write_text(yaml.safe_dump(doc))
            got = vfd.verify_golden(gp, "go", root, "unused", offline=True)
            self.assertEqual([vfd.UNVERIFIABLE], [r.status for r in got])
            self.assertIn("no resolved_commit", got[0].detail)

    def test_unreachable_commit_offline_is_unverifiable_not_pass(self):
        """A run that reaches nothing must not report zero failures."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _ = make_checkout(tmp, {"adapters/kobler/koblertest/exemplary/a.json": BODY})
            gp = tmp / "kobler.golden.spec.yaml"
            gp.write_text(yaml.safe_dump(golden_doc("f" * 40, {
                "exemplary": [{"filename": "a.json", "sha256": SHA, "bytes": len(BODY)}]})))
            got = vfd.verify_golden(gp, "go", root, "unused", offline=True)
            self.assertEqual([vfd.UNVERIFIABLE], [r.status for r in got])


class TestResolverIsNotDuplicated(unittest.TestCase):
    def test_path_resolution_comes_from_sync_from_upstream(self):
        """One resolver, not two. A bare filename resolved by searching upstream
        for anything ending in it reports correct digests as wrong, because
        `simple-banner.json` exists in over a hundred adapter directories."""
        self.assertTrue(hasattr(vfd.sfu, "_derive_fixture_paths"))
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("sfu._derive_fixture_paths", source)
        self.assertNotIn("def _derive_fixture_paths", source,
                         "this script must not define its own resolver")


class TestCli(unittest.TestCase):
    def test_no_checkout_is_a_setup_error(self):
        self.assertEqual(2, vfd.main([]))

    def test_non_checkout_path_is_a_setup_error(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(2, vfd.main(["--go-checkout", td]))


if __name__ == "__main__":
    unittest.main()
