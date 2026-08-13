"""Tests for the vision skill recognition script (stdlib unittest)."""

import base64
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "vision" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import recognize  # noqa: E402

# Isolate tests from the ambient environment: disable automatic project-config
# discovery (CWD may sit inside a repo that has a real .vision.config.json with
# a live key). Project-config behavior is tested explicitly via
# project_config_path= in ProjectConfigSlice.
_original_find_project_config = recognize._find_project_config
recognize._find_project_config = lambda start=None: None  # noqa: E402

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# S1 — config resolution: env > config file > defaults
# ---------------------------------------------------------------------------


class ConfigSlice(unittest.TestCase):
    def test_defaults_used_when_only_key_configured(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = recognize.load_config(
                env={"VISION_API_KEY": "sk-test"},
                config_path=Path(td) / "nope.json",
            )
        self.assertEqual(cfg["provider"], "dashscope")
        self.assertEqual(cfg["endpoint"], "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertEqual(cfg["model"], "qwen3-vl-plus")
        self.assertEqual(cfg["api_key"], "sk-test")

    def test_config_file_supplies_key_and_model(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_text(json.dumps({"api_key": "sk-file", "model": "qwen2.5-vl-72b-instruct"}))
            cfg = recognize.load_config(env={}, config_path=p)
        self.assertEqual(cfg["api_key"], "sk-file")
        self.assertEqual(cfg["model"], "qwen2.5-vl-72b-instruct")
        self.assertEqual(cfg["endpoint"], "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def test_env_overrides_config_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_text(json.dumps({"api_key": "sk-file", "model": "from-file"}))
            cfg = recognize.load_config(
                env={"VISION_API_KEY": "sk-env", "VISION_MODEL": "from-env"},
                config_path=p,
            )
        self.assertEqual(cfg["api_key"], "sk-env")
        self.assertEqual(cfg["model"], "from-env")

    def test_missing_key_raises_config_error_with_guidance(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(recognize.ConfigError) as ctx:
                recognize.load_config(env={}, config_path=Path(td) / "nope.json")
        msg = str(ctx.exception)
        self.assertIn("VISION_API_KEY", msg)
        self.assertIn("config.json", msg)
        self.assertIn("bailian", msg.lower())

    def test_invalid_json_in_config_file_raises_config_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_text("{not json")
            with self.assertRaises(recognize.ConfigError):
                recognize.load_config(env={"VISION_API_KEY": "sk"}, config_path=p)

    def test_non_utf8_config_file_raises_config_error_not_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_bytes('{"api_key": "\u767e\u70bc"}'.encode("gbk"))
            with self.assertRaises(recognize.ConfigError) as ctx:
                recognize.load_config(env={}, config_path=p)
        self.assertIn("Cannot read user config file", str(ctx.exception))

    def test_invalid_endpoint_raises_config_error(self):
        with tempfile.TemporaryDirectory() as td:
            for bad in ("not-a-url", "http://", "ftp://example.com/x"):
                with self.assertRaises(recognize.ConfigError):
                    recognize.load_config(
                        env={"VISION_API_KEY": "sk", "VISION_ENDPOINT": bad},
                        config_path=Path(td) / "nope.json",
                    )

    def test_unknown_config_file_keys_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_text(json.dumps({"api_key": "sk", "extra": "ignored"}))
            cfg = recognize.load_config(env={}, config_path=p)
        self.assertNotIn("extra", cfg)


# ---------------------------------------------------------------------------
# S6 — project-level config: env > project .vision.config.json > user config > defaults
# ---------------------------------------------------------------------------


class ProjectConfigSlice(unittest.TestCase):
    def test_project_config_found_walking_up_from_subdirectory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / recognize.PROJECT_CONFIG_NAME).write_text(json.dumps({"model": "m"}))
            deep = root / "sub" / "deep"
            deep.mkdir(parents=True)
            found = _original_find_project_config(start=deep)
        self.assertEqual(found, root / recognize.PROJECT_CONFIG_NAME)

    def test_no_project_config_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(recognize._find_project_config(start=Path(td)))

    def test_project_config_merged_with_user_config(self):
        with tempfile.TemporaryDirectory() as td:
            user = Path(td) / "user.json"
            user.write_text(json.dumps({"api_key": "sk-user"}))
            proj = Path(td) / "proj.json"
            proj.write_text(json.dumps({"model": "proj-model"}))
            cfg = recognize.load_config(env={}, config_path=user, project_config_path=proj)
        self.assertEqual(cfg["api_key"], "sk-user")
        self.assertEqual(cfg["model"], "proj-model")

    def test_project_config_overrides_user_config(self):
        with tempfile.TemporaryDirectory() as td:
            user = Path(td) / "user.json"
            user.write_text(json.dumps({"model": "user-model", "api_key": "sk"}))
            proj = Path(td) / "proj.json"
            proj.write_text(json.dumps({"model": "proj-model"}))
            cfg = recognize.load_config(env={}, config_path=user, project_config_path=proj)
        self.assertEqual(cfg["model"], "proj-model")

    def test_env_overrides_project_config(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "proj.json"
            proj.write_text(json.dumps({"model": "proj-model", "api_key": "sk-proj"}))
            cfg = recognize.load_config(
                env={"VISION_MODEL": "env-model", "VISION_API_KEY": "sk-env"},
                config_path=Path(td) / "nope.json",
                project_config_path=proj,
            )
        self.assertEqual(cfg["model"], "env-model")
        self.assertEqual(cfg["api_key"], "sk-env")

    def test_missing_project_config_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            user = Path(td) / "user.json"
            user.write_text(json.dumps({"api_key": "sk", "model": "user-model"}))
            cfg = recognize.load_config(
                env={},
                config_path=user,
                project_config_path=Path(td) / "missing.json",
            )
        self.assertEqual(cfg["model"], "user-model")

    def test_invalid_project_config_raises_config_error(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "proj.json"
            proj.write_text("{broken")
            with self.assertRaises(recognize.ConfigError):
                recognize.load_config(
                    env={"VISION_API_KEY": "sk"},
                    config_path=Path(td) / "nope.json",
                    project_config_path=proj,
                )


# ---------------------------------------------------------------------------
# S2 — input forms: local path / http(s) URL / base64 data URI
# ---------------------------------------------------------------------------


class InputSlice(unittest.TestCase):
    def test_http_url_passes_through(self):
        content = recognize.prepare_image_content("https://example.com/a.png")
        self.assertEqual(
            content, {"type": "image_url", "image_url": {"url": "https://example.com/a.png"}}
        )

    def test_data_uri_passes_through(self):
        uri = "data:image/png;base64," + base64.b64encode(PNG_1PX).decode()
        content = recognize.prepare_image_content(uri)
        self.assertEqual(content["image_url"]["url"], uri)

    def test_png_file_becomes_png_data_uri(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "shot.png"
            p.write_bytes(PNG_1PX)
            content = recognize.prepare_image_content(str(p))
        url = content["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"), url)
        self.assertEqual(base64.b64decode(url.split(",", 1)[1]), PNG_1PX)

    def test_jpeg_detected_by_magic_bytes_without_extension(self):
        jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 16
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "noext"
            p.write_bytes(jpeg)
            content = recognize.prepare_image_content(str(p))
        self.assertTrue(content["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_webp_detected_by_magic_bytes(self):
        webp = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 8
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pic.webp"
            p.write_bytes(webp)
            content = recognize.prepare_image_content(str(p))
        self.assertTrue(content["image_url"]["url"].startswith("data:image/webp;base64,"))

    def test_missing_file_raises_input_error(self):
        with self.assertRaises(recognize.InputError) as ctx:
            recognize.prepare_image_content("C:/definitely/not/here.png")
        self.assertIn("not/here.png", str(ctx.exception))

    def test_unknown_format_raises_input_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "blob.bin"
            p.write_bytes(b"\x00\x01\x02\x03" * 4)
            with self.assertRaises(recognize.InputError):
                recognize.prepare_image_content(str(p))

    def test_non_image_data_uri_rejected(self):
        with self.assertRaises(recognize.InputError) as ctx:
            recognize.prepare_image_content("data:text/plain;base64,aGVsbG8=")
        self.assertIn("data:image/", str(ctx.exception))

    def test_truncated_base64_data_uri_rejected(self):
        with self.assertRaises(recognize.InputError):
            recognize.prepare_image_content("data:image/png;base64,AAAAA")

    def test_empty_payload_data_uri_rejected(self):
        with self.assertRaises(recognize.InputError):
            recognize.prepare_image_content("data:image/png;base64,")

    def test_unreadable_path_is_input_error_not_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(recognize.InputError) as ctx:
                recognize.prepare_image_content(td)  # a directory, not a file
        self.assertIn("Cannot read", str(ctx.exception))

    def test_padded_data_uri_accepted(self):
        uri = "data:image/png;base64," + base64.b64encode(b"ab").decode()
        self.assertEqual(uri.endswith("="), True)  # genuinely padded payload
        self.assertEqual(
            recognize.prepare_image_content(uri)["image_url"]["url"], uri
        )


# ---------------------------------------------------------------------------
# S3 — API call: request shape, response parsing, error mapping
# ---------------------------------------------------------------------------

CFG = {
    "provider": "dashscope",
    "api_key": "sk-test",
    "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3-vl-plus",
}

IMG = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}

OK_BODY = {"choices": [{"message": {"content": "A red stop sign."}}]}


class FakeOpener:
    """Records the request and returns a canned (status, json) response."""

    def __init__(self, status=200, body=None, exc=None):
        self.status = status
        self.body = body if body is not None else OK_BODY
        self.exc = exc
        self.calls = []

    def __call__(self, url, headers, data):
        self.calls.append((url, headers, data))
        if self.exc is not None:
            raise self.exc
        return self.status, self.body


class ApiSlice(unittest.TestCase):
    def test_request_targets_chat_completions_with_auth_and_payload(self):
        opener = FakeOpener()
        recognize.call_vision(CFG, IMG, prompt="What is this?", opener=opener)
        url, headers, data = opener.calls[0]
        self.assertEqual(url, "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer sk-test")
        self.assertEqual(headers["Content-Type"], "application/json")
        payload = json.loads(data)
        self.assertEqual(payload["model"], "qwen3-vl-plus")
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][0]["content"][0], IMG)
        self.assertEqual(payload["messages"][0]["content"][1]["type"], "text")

    def test_default_prompt_asks_for_detailed_description(self):
        opener = FakeOpener()
        recognize.call_vision(CFG, IMG, opener=opener)
        text = json.loads(opener.calls[0][2])["messages"][0]["content"][1]["text"]
        self.assertIn("detail", text.lower())

    def test_custom_endpoint_used(self):
        cfg = dict(CFG, endpoint="https://my-proxy.example.com/v1/")
        opener = FakeOpener()
        recognize.call_vision(cfg, IMG, opener=opener)
        self.assertEqual(opener.calls[0][0], "https://my-proxy.example.com/v1/chat/completions")

    def test_returns_recognition_text(self):
        opener = FakeOpener()
        self.assertEqual(recognize.call_vision(CFG, IMG, opener=opener), "A red stop sign.")

    def test_http_error_surfaces_provider_message(self):
        body = {"error": {"message": "Invalid API key provided"}}
        opener = FakeOpener(status=401, body=body)
        with self.assertRaises(recognize.ApiError) as ctx:
            recognize.call_vision(CFG, IMG, opener=opener)
        self.assertIn("Invalid API key", str(ctx.exception))
        self.assertIn("401", str(ctx.exception))

    def test_network_error_maps_to_api_error(self):
        opener = FakeOpener(exc=urllib.error.URLError("connection refused"))
        with self.assertRaises(recognize.ApiError) as ctx:
            recognize.call_vision(CFG, IMG, opener=opener)
        self.assertIn("connection refused", str(ctx.exception))

    def test_interrupted_body_maps_to_api_error(self):
        opener = FakeOpener(exc=http.client.IncompleteRead(b"partial"))
        with self.assertRaises(recognize.ApiError):
            recognize.call_vision(CFG, IMG, opener=opener)

    def test_empty_choices_raises_api_error(self):
        opener = FakeOpener(body={"choices": []})
        with self.assertRaises(recognize.ApiError):
            recognize.call_vision(CFG, IMG, opener=opener)

    def test_missing_key_in_config_raises_config_error(self):
        with self.assertRaises(recognize.ConfigError):
            recognize.call_vision(dict(CFG, api_key=""), IMG, opener=FakeOpener())

    def test_empty_content_rejected(self):
        for bad in (None, "", "   "):
            opener = FakeOpener(body={"choices": [{"message": {"content": bad}}]})
            with self.assertRaises(recognize.ApiError) as ctx:
                recognize.call_vision(CFG, IMG, opener=opener)
            self.assertIn("empty recognition result", str(ctx.exception))


# ---------------------------------------------------------------------------
# S4 — CLI: exit codes, stdout/stderr, --json output
# ---------------------------------------------------------------------------


def run_cli(argv, env=None, config_path=None, opener=None):
    """Run recognize.main capturing stdout/stderr; returns (code, out, err)."""
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = recognize.main(argv, env=env, config_path=config_path, opener=opener)
    return code, out.getvalue(), err.getvalue()


class CliSlice(unittest.TestCase):
    def test_success_prints_recognition_text_and_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "shot.png"
            p.write_bytes(PNG_1PX)
            code, out, err = run_cli(
                [str(p)],
                env={"VISION_API_KEY": "sk-test"},
                config_path=Path(td) / "nope.json",
                opener=FakeOpener(),
            )
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "A red stop sign.")
        self.assertEqual(err, "")

    def test_custom_prompt_passed_to_api(self):
        opener = FakeOpener()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "shot.png"
            p.write_bytes(PNG_1PX)
            run_cli(
                [str(p), "--prompt", "What color is it?"],
                env={"VISION_API_KEY": "sk-test"},
                config_path=Path(td) / "nope.json",
                opener=opener,
            )
        payload = json.loads(opener.calls[0][2])
        self.assertEqual(payload["messages"][0]["content"][1]["text"], "What color is it?")

    def test_missing_key_prints_guidance_and_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            code, out, err = run_cli(
                ["whatever.png"], env={}, config_path=Path(td) / "nope.json"
            )
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("VISION_API_KEY", err)
        self.assertIn("bailian", err.lower())

    def test_missing_file_exit_3(self):
        code, out, err = run_cli(
            ["C:/nope/missing.png"],
            env={"VISION_API_KEY": "sk-test"},
            config_path=Path("C:/nope/config.json"),
        )
        self.assertEqual(code, 3)
        self.assertIn("missing.png", err)

    def test_api_error_exit_4_with_provider_message(self):
        opener = FakeOpener(status=401, body={"error": {"message": "Invalid API key"}})
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "shot.png"
            p.write_bytes(PNG_1PX)
            code, out, err = run_cli(
                [str(p)],
                env={"VISION_API_KEY": "sk-wrong"},
                config_path=Path(td) / "nope.json",
                opener=opener,
            )
        self.assertEqual(code, 4)
        self.assertEqual(out, "")
        self.assertIn("401", err)
        self.assertIn("Invalid API key", err)

    def test_json_output_contains_source_model_provider_text(self):
        opener = FakeOpener()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "shot.png"
            p.write_bytes(PNG_1PX)
            code, out, err = run_cli(
                [str(p), "--json"],
                env={"VISION_API_KEY": "sk-test"},
                config_path=Path(td) / "nope.json",
                opener=opener,
            )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["text"], "A red stop sign.")
        self.assertEqual(data["model"], "qwen3-vl-plus")
        self.assertEqual(data["provider"], "dashscope")
        self.assertEqual(data["source"], str(p))

    def test_no_arguments_prints_usage_exit_2(self):
        code, out, err = run_cli([], env={"VISION_API_KEY": "sk-test"})
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())


# ---------------------------------------------------------------------------
# S5 — E2E: real HTTP round-trip against a local mock vision server
# ---------------------------------------------------------------------------


class MockVisionHandler(BaseHTTPRequestHandler):
    seen = {}  # class-level: last request captured across handler instances

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).seen = {
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "body": body,
        }
        if body.get("model") == "garbage-response":
            self.send_response(200)
            data = b"this is not json"
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if body.get("model") != "qwen3-vl-plus":
            self.send_response(400)
            payload = {"error": {"message": f"unknown model {body.get('model')}"}}
        else:
            self.send_response(200)
            payload = {
                "choices": [
                    {"message": {"content": "E2E: a screenshot of a dashboard"}}
                ]
            }
        data = json.dumps(payload).encode("utf-8")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class E2ESlice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockVisionHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.endpoint = f"http://127.0.0.1:{cls.server.server_address[1]}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_local_png_end_to_end(self):
        MockVisionHandler.seen = {}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "shot.png"
            p.write_bytes(PNG_1PX)
            code, out, err = run_cli(
                [str(p)],
                env={"VISION_API_KEY": "sk-e2e", "VISION_ENDPOINT": self.endpoint},
                config_path=Path(td) / "nope.json",
            )
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), "E2E: a screenshot of a dashboard")

        seen = MockVisionHandler.seen
        self.assertEqual(seen["path"], "/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer sk-e2e")
        content = seen["body"]["messages"][0]["content"]
        self.assertEqual(content[0]["image_url"]["url"].split(",")[0], "data:image/png;base64")
        self.assertEqual(
            base64.b64decode(content[0]["image_url"]["url"].split(",", 1)[1]), PNG_1PX
        )

    def test_data_uri_and_url_forms_end_to_end(self):
        uri = "data:image/png;base64," + base64.b64encode(PNG_1PX).decode()
        code, out, err = run_cli(
            [uri],
            env={"VISION_API_KEY": "sk-e2e", "VISION_ENDPOINT": self.endpoint},
            config_path=Path("C:/nope/config.json"),
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), "E2E: a screenshot of a dashboard")
        self.assertEqual(
            MockVisionHandler.seen["body"]["messages"][0]["content"][0]["image_url"]["url"],
            uri,
        )

        code, out, err = run_cli(
            ["https://example.com/pic.png"],
            env={"VISION_API_KEY": "sk-e2e", "VISION_ENDPOINT": self.endpoint},
            config_path=Path("C:/nope/config.json"),
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(
            MockVisionHandler.seen["body"]["messages"][0]["content"][0]["image_url"]["url"],
            "https://example.com/pic.png",
        )

    def test_api_error_surfaces_end_to_end(self):
        code, out, err = run_cli(
            ["https://example.com/pic.png"],
            env={
                "VISION_API_KEY": "sk-e2e",
                "VISION_ENDPOINT": self.endpoint,
                "VISION_MODEL": "bogus-model",
            },
            config_path=Path("C:/nope/config.json"),
        )
        self.assertEqual(code, 4)
        self.assertIn("unknown model", err)

    def test_non_json_200_body_is_clean_api_error_not_traceback(self):
        code, out, err = run_cli(
            ["https://example.com/pic.png"],
            env={
                "VISION_API_KEY": "sk-e2e",
                "VISION_ENDPOINT": self.endpoint,
                "VISION_MODEL": "garbage-response",
            },
            config_path=Path("C:/nope/config.json"),
        )
        self.assertEqual(code, 4)
        self.assertIn("non-JSON", err)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
