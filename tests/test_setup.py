"""Tests for the vision skill setup wizard (stdlib unittest)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "vision" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import recognize  # noqa: E402
import setup  # noqa: E402

# Isolate from the ambient environment: no project config discovery, and a
# deterministic user config path for every test.
_original_find_project_config = recognize._find_project_config
recognize._find_project_config = lambda start=None: None  # noqa: E402


class MaskSlice(unittest.TestCase):
    def test_masks_long_key(self):
        self.assertEqual(setup.mask_key("sk-1234567890abcdef"), "sk-***cdef")

    def test_short_key_fully_masked(self):
        self.assertEqual(setup.mask_key("abcdef"), "***")

    def test_empty_key(self):
        self.assertEqual(setup.mask_key(""), "(not set)")


class ResolveSlice(unittest.TestCase):
    def test_defaults_when_nothing_configured(self):
        with tempfile.TemporaryDirectory() as td:
            resolved = setup.resolve_each(env={}, config_path=Path(td) / "nope.json")
        self.assertEqual(resolved["api_key"], ("", "default"))
        self.assertEqual(resolved["model"], ("qwen3-vl-plus", "default"))

    def test_user_file_supplies_key(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_text(json.dumps({"api_key": "sk-user", "model": "m1"}))
            resolved = setup.resolve_each(env={}, config_path=p)
        self.assertEqual(resolved["api_key"], ("sk-user", "user"))
        self.assertEqual(resolved["model"], ("m1", "user"))

    def test_env_beats_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_text(json.dumps({"api_key": "sk-user"}))
            resolved = setup.resolve_each(env={"VISION_API_KEY": "sk-env"}, config_path=p)
        self.assertEqual(resolved["api_key"], ("sk-env", "env"))

    def test_project_missing_key_falls_back_to_user(self):
        # Matches recognize.load_config: project config lacking a key must not
        # shadow the user config value for that key.
        with tempfile.TemporaryDirectory() as td:
            user_cfg = Path(td) / "user.json"
            user_cfg.write_text(json.dumps({"api_key": "sk-user-key"}))
            project_cfg = Path(td) / "proj.json"
            project_cfg.write_text(json.dumps({"model": "m-shared"}))
            resolved = setup.resolve_each(env={}, config_path=user_cfg,
                                          project_config_path=project_cfg)
        self.assertEqual(resolved["api_key"], ("sk-user-key", "user"))
        self.assertEqual(resolved["model"], ("m-shared", "project"))


class WriteConfigSlice(unittest.TestCase):
    def test_creates_parents_and_writes(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "sub" / ".vision.config.json"
            written = setup.write_config(target, {"api_key": "sk-1", "model": "m2"})
            self.assertEqual(written["api_key"], "sk-1")
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["model"], "m2")

    def test_preserves_unknown_keys(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.json"
            p.write_text(json.dumps({"future_key": 42, "api_key": "sk-old"}))
            setup.write_config(p, {"api_key": "sk-new"})
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["api_key"], "sk-new")
            self.assertEqual(data["future_key"], 42)

    def test_ignores_keys_outside_config_set(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.json"
            setup.write_config(p, {"api_key": "sk-1", "nonsense": "x"})
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertNotIn("nonsense", data)

    def test_corrupt_existing_file_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.json"
            p.write_text("{not json")
            with self.assertRaises(setup.SetupError):
                setup.write_config(p, {"api_key": "sk-1"})


class MainSlice(unittest.TestCase):
    def test_set_writes_project_config_in_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            rc = setup.main(["--set", "api_key=sk-abc123", "--set", "model=m9", "--target", "project"],
                            env={}, cwd=td)
            p = Path(td) / ".vision.config.json"
            self.assertEqual(rc, 0)
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["api_key"], "sk-abc123")
            self.assertEqual(data["model"], "m9")

    def test_set_default_target_is_user(self):
        with tempfile.TemporaryDirectory() as td:
            user_cfg = Path(td) / "user.json"
            rc = setup.main(["--set", "api_key=sk-abc123"], env={}, cwd=td, config_path=user_cfg)
            self.assertEqual(rc, 0)
            data = json.loads(user_cfg.read_text(encoding="utf-8"))
            self.assertEqual(data["api_key"], "sk-abc123")
            self.assertFalse((Path(td) / ".vision.config.json").exists())

    def test_set_output_masks_api_key(self):
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as td:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                setup.main(["--set", "api_key=sk-1234567890abcdef", "--target", "user"],
                           env={}, cwd=td, config_path=Path(td) / "u.json")
        out = buf.getvalue()
        self.assertIn("sk-***cdef", out)
        self.assertNotIn("sk-1234567890abcdef", out)

    def test_set_rejects_unknown_key(self):
        rc = setup.main(["--set", "bogus=1"], env={}, cwd=Path("."))
        self.assertEqual(rc, 3)

    def test_show_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            rc = setup.main(["--show"], env={}, cwd=td, config_path=Path(td) / "nope.json")
            self.assertEqual(rc, 0)
            self.assertFalse((Path(td) / ".vision.config.json").exists())


class GitignoreSlice(unittest.TestCase):
    def test_project_write_creates_gitignore_entry(self):
        with tempfile.TemporaryDirectory() as td:
            rc = setup.main(["--set", "api_key=sk-abc123", "--target", "project"],
                            env={}, cwd=td)
            self.assertEqual(rc, 0)
            gitignore = Path(td) / ".gitignore"
            self.assertTrue(gitignore.exists())
            self.assertIn("vision.config.json", gitignore.read_text(encoding="utf-8"))
            self.assertIn(".vision.config.json", gitignore.read_text(encoding="utf-8"))

    def test_gitignore_entry_not_duplicated(self):
        with tempfile.TemporaryDirectory() as td:
            setup.main(["--set", "api_key=sk-1", "--target", "project"], env={}, cwd=td)
            setup.main(["--set", "api_key=sk-2", "--target", "project"], env={}, cwd=td)
            text = (Path(td) / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(text.count("vision.config.json"), 1)

    def test_gitignore_existing_coverage_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / ".gitignore").write_text("*.vision.config.json\n", encoding="utf-8")
            setup.main(["--set", "api_key=sk-1", "--target", "project"], env={}, cwd=td)
            text = (Path(td) / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(text.count("vision.config.json"), 1)  # untouched

    def test_user_write_does_not_touch_gitignore(self):
        with tempfile.TemporaryDirectory() as td:
            rc = setup.main(["--set", "api_key=sk-abc123"], env={}, cwd=td,
                            config_path=Path(td) / "user.json")
            self.assertEqual(rc, 0)
            self.assertFalse((Path(td) / ".gitignore").exists())

    def test_unwritable_gitignore_raises(self):
        with tempfile.TemporaryDirectory() as td:
            gitignore = Path(td) / ".gitignore"
            gitignore.write_text("", encoding="utf-8")
            gitignore.chmod(0o444)  # read-only
            try:
                with self.assertRaises(setup.SetupError):
                    setup.ensure_gitignore(Path(td) / ".vision.config.json")
            finally:
                gitignore.chmod(0o644)


if __name__ == "__main__":
    unittest.main()
