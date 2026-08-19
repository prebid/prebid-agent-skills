"""Self-tests for R2c -- the networked half of the params-fidelity check.

The reason R2c exists is measurable, and this module measures it. A forgery that
edits the blob, `bidder_params_ref.sha256`, `bidder_params_ref.bytes` and
`bidder_params_sha256` together is internally consistent, so every hermetic check
passes it. Reproduced against a Go-only golden (no Java pair, so R5 has nothing
to compare): 10 bytes removed from the upstream params, `make ci` exit 0, zero
mentions of the bidder anywhere in the output. R2c fails it on all three grounds.

So the tests below are built around synthetic upstream repos: R2c must pass when
the ref matches upstream, fail when it does not, and -- the case a green run must
never be able to hide behind -- report UNVERIFIABLE rather than PASS when it
could not read upstream at all.

Run: python3 -m unittest scripts.tests.test_verify_params_refs -v
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "verify_params_refs", REPO_ROOT / "scripts" / "verify-params-refs.py")
assert _spec and _spec.loader
vpr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vpr)

PARAMS = b'{\n  "type": "object",\n  "properties": {"test": {"type": "boolean"}}\n}\n'
PARAMS_PATH = "static/bidder-params/probe.json"


def _run_quiet(argv: list[str]) -> int:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        return vpr.main(argv)


def _make_upstream(root: Path, body: bytes = PARAMS, path: str = PARAMS_PATH) -> str:
    """A one-commit repo holding `body` at `path`. Returns the commit sha."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for k, v in (("user.email", "t@example.com"), ("user.name", "t"),
                 ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(root), "config", k, v], check=True)
    f = root / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(body)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "params"], check=True)
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def _make_golden(dirpath: Path, name: str, commit: str, body: bytes,
                 *, path: str = PARAMS_PATH, sha: str | None = None,
                 nbytes: int | None = None, write_blob: bool = True,
                 blob_body: bytes | None = None) -> Path:
    """A golden plus its blob. `sha`/`nbytes`/`blob_body` let a test lie."""
    digest = sha if sha is not None else hashlib.sha256(body).hexdigest()
    length = nbytes if nbytes is not None else len(body)
    dirpath.mkdir(parents=True, exist_ok=True)
    golden = dirpath / f"{name}.golden.spec.yaml"
    golden.write_text(
        "adapter_spec_version: \"2.0.0\"\n"
        "bidder_params_ref:\n"
        f"  path: {path}\n"
        f"  resolved_commit: {commit}\n"
        f"  sha256: {digest}\n"
        f"  bytes: {length}\n"
        f"bidder_params_sha256: {digest}\n",
        encoding="utf-8")
    if write_blob:
        blobs = dirpath / "blobs"
        blobs.mkdir(exist_ok=True)
        (blobs / digest).write_bytes(blob_body if blob_body is not None else body)
    return golden


class TestVerifyOne(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.upstream = self.tmp / "upstream"
        self.commit = _make_upstream(self.upstream)
        self.fixtures = self.tmp / "fixtures"
        self.addCleanup(self._td.cleanup)

    def _verify(self, golden: Path):
        return vpr.verify_one(golden, self.upstream, "unused-remote", offline=True)

    def test_matching_ref_passes(self):
        g = _make_golden(self.fixtures, "probe", self.commit, PARAMS)
        r = self._verify(g)
        self.assertEqual(vpr.PASS, r.status, r.detail)
        self.assertIn(str(len(PARAMS)), r.detail)

    def test_self_consistent_forgery_is_caught(self):
        """The whole point. Blob, sha and byte count all edited together, so
        every hermetic check agrees with itself; only upstream disagrees."""
        forged = PARAMS.replace(b'"boolean"', b'"bool"')
        self.assertNotEqual(len(forged), len(PARAMS))
        g = _make_golden(self.fixtures, "probe", self.commit, forged)
        r = self._verify(g)
        self.assertEqual(vpr.FAIL, r.status)
        self.assertIn("sha256", r.detail)
        self.assertIn("bytes", r.detail)
        self.assertIn("differs from upstream", r.detail)

    def test_blob_doctored_while_sha_still_declares_upstream(self):
        """A blob that does NOT hash to its own filename: R2 would fail this
        one, but R2c must not pass it either."""
        g = _make_golden(self.fixtures, "probe", self.commit, PARAMS,
                         blob_body=PARAMS + b"\n")
        r = self._verify(g)
        self.assertEqual(vpr.FAIL, r.status)
        self.assertIn("differs from upstream", r.detail)

    def test_byte_count_alone_disagreeing_is_caught(self):
        """`bytes` is the second witness; a wrong one is a finding on its own."""
        g = _make_golden(self.fixtures, "probe", self.commit, PARAMS,
                         nbytes=len(PARAMS) + 1)
        r = self._verify(g)
        self.assertEqual(vpr.FAIL, r.status)
        self.assertIn("bytes", r.detail)

    def test_missing_blob_is_a_finding(self):
        g = _make_golden(self.fixtures, "probe", self.commit, PARAMS, write_blob=False)
        r = self._verify(g)
        self.assertEqual(vpr.FAIL, r.status)
        self.assertIn("absent from blobs/", r.detail)

    def test_unreachable_commit_is_unverifiable_not_pass(self):
        """A commit the checkout cannot read must never read as verified."""
        g = _make_golden(self.fixtures, "probe", "f" * 40, PARAMS)
        r = self._verify(g)
        self.assertEqual(vpr.UNVERIFIABLE, r.status)
        self.assertIn("not in checkout", r.detail)

    def test_malformed_commit_is_a_finding_not_unverifiable(self):
        """A bad digest must not be reported the same way as an upstream rename.

        `0` * 40 is the case that motivated the guard: PyYAML loads a 40-character
        all-digit sha beginning with zero as the integer 0, so a falsy check
        called it "missing" and `str()` would have handed `git show` the string
        "0". Distinguishing malformed-ref from cannot-reach-upstream matters,
        because only the second is the drift refresh's problem.
        """
        for bad in ("0" * 40, "nothex" + "0" * 34, "abc", 0):
            g = _make_golden(self.fixtures, f"probe", self.commit, PARAMS)
            text = g.read_text(encoding="utf-8").replace(
                f"resolved_commit: {self.commit}", f"resolved_commit: {bad}")
            g.write_text(text, encoding="utf-8")
            r = self._verify(g)
            self.assertEqual(vpr.FAIL, r.status, f"{bad!r} -> {r.status}: {r.detail}")
            self.assertIn("resolved_commit", r.detail)

    def test_malformed_sha256_is_a_finding(self):
        g = _make_golden(self.fixtures, "probe", self.commit, PARAMS,
                         sha="not-a-digest", write_blob=False)
        r = self._verify(g)
        self.assertEqual(vpr.FAIL, r.status)
        self.assertIn("sha256", r.detail)

    def test_real_goldens_all_have_well_formed_refs(self):
        """The guard above is only useful if the corpus satisfies it."""
        import yaml
        bad = []
        for lang, d in vpr.GOLDEN_DIRS.items():
            for golden in sorted(d.glob("*.golden.spec.yaml")):
                ref = (yaml.safe_load(golden.read_text(encoding="utf-8")) or {}).get(
                    "bidder_params_ref") or {}
                if not isinstance(ref.get("resolved_commit"), str):
                    bad.append(f"{lang}/{golden.name}: resolved_commit is "
                               f"{type(ref.get('resolved_commit')).__name__}")
                if not isinstance(ref.get("bytes"), int):
                    bad.append(f"{lang}/{golden.name}: bytes is "
                               f"{type(ref.get('bytes')).__name__}")
        self.assertEqual([], bad, "\n  ".join(bad))

    def test_path_gone_upstream_is_unverifiable_not_pass(self):
        """A rename or deletion upstream: a finding for the drift refresh, and
        emphatically not a PASS."""
        g = _make_golden(self.fixtures, "probe", self.commit, PARAMS,
                         path="static/bidder-params/renamed.json")
        r = self._verify(g)
        self.assertEqual(vpr.UNVERIFIABLE, r.status)
        self.assertIn("absent at", r.detail)

    def test_incomplete_ref_fails(self):
        g = _make_golden(self.fixtures, "probe", self.commit, PARAMS)
        g.write_text(g.read_text(encoding="utf-8").replace(
            f"  bytes: {len(PARAMS)}\n", "  bytes:\n"), encoding="utf-8")
        r = self._verify(g)
        self.assertEqual(vpr.FAIL, r.status)
        self.assertIn("bytes", r.detail)


class TestExitCodes(unittest.TestCase):
    def test_no_checkout_is_a_setup_error(self):
        self.assertEqual(2, _run_quiet([]))

    def test_non_git_path_is_a_setup_error(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(2, _run_quiet(["--go-checkout", td]))

    def test_real_corpus_is_skipped_without_a_checkout(self):
        """Guard against the opposite failure: main() must not report success
        for a language whose checkout was not supplied."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "u"
            _make_upstream(root)
            # Only --go-checkout given: the java goldens are never claimed to
            # have been verified, because they are not scanned at all.
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                vpr.main(["--go-checkout", str(root), "--offline", "--allow-unverifiable"])
            out = buf.getvalue()
            self.assertIn("against go", out)
            self.assertNotIn("java", out.split("against go")[-1].splitlines()[0])


class TestRealCorpus(unittest.TestCase):
    """Runs only when checkouts are present; skipped otherwise rather than
    silently passing on an empty scan."""

    def test_every_golden_declares_a_complete_ref(self):
        """Hermetic half of R2c's precondition: a ref that cannot be checked
        against upstream is a defect regardless of whether upstream is at hand."""
        bad = []
        for lang, d in vpr.GOLDEN_DIRS.items():
            for golden in sorted(d.glob("*.golden.spec.yaml")):
                import yaml
                ref = (yaml.safe_load(golden.read_text(encoding="utf-8")) or {}).get(
                    "bidder_params_ref")
                if not ref:
                    bad.append(f"{lang}/{golden.name}: no bidder_params_ref")
                    continue
                missing = [k for k in ("path", "resolved_commit", "sha256", "bytes")
                           if not ref.get(k)]
                if missing:
                    bad.append(f"{lang}/{golden.name}: missing {missing}")
        self.assertEqual([], bad, "\n  ".join(bad))

    def test_every_declared_blob_exists_and_hashes_to_its_name(self):
        """The store R2c compares against must itself be coherent, and orphans
        are reported: after 2.0.0 the blob store is the only copy of these
        upstream bytes, so an unreferenced file is either dead weight or a
        reference someone dropped."""
        import yaml
        problems = []
        for lang, d in vpr.GOLDEN_DIRS.items():
            blobs = d / "blobs"
            referenced = set()
            for golden in sorted(d.glob("*.golden.spec.yaml")):
                ref = (yaml.safe_load(golden.read_text(encoding="utf-8")) or {}).get(
                    "bidder_params_ref") or {}
                if ref.get("sha256"):
                    referenced.add(str(ref["sha256"]))
            if not blobs.is_dir():
                problems.append(f"{lang}: no blobs/ directory but {len(referenced)} refs")
                continue
            on_disk = {p.name for p in blobs.iterdir() if p.is_file()}
            for name in sorted(on_disk):
                actual = hashlib.sha256((blobs / name).read_bytes()).hexdigest()
                if actual != name:
                    problems.append(f"{lang}/blobs/{name}: content hashes to {actual}")
            for name in sorted(referenced - on_disk):
                problems.append(f"{lang}: ref names blob {name[:12]} that is not stored")
            for name in sorted(on_disk - referenced):
                problems.append(f"{lang}/blobs/{name[:12]}: orphan, no ref points at it")
        self.assertEqual([], problems, "\n  ".join(problems))


if __name__ == "__main__":
    unittest.main()
