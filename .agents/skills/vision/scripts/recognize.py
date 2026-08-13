#!/usr/bin/env python3
"""Vision recognition for the `vision` skill.

Recognizes an image (local path, http(s) URL, or base64 data URI) with a
configurable OpenAI-compatible vision model. Defaults to Aliyun Bailian
(阿里云百炼) Qwen-VL via the DashScope compatible-mode endpoint.

Configuration precedence: environment variables > config file > defaults.

    VISION_PROVIDER  provider name                (default: dashscope)
    VISION_API_KEY   API key (required)
    VISION_ENDPOINT  OpenAI-compatible base URL   (default: https://dashscope.aliyuncs.com/compatible-mode/v1)
    VISION_MODEL     vision model name            (default: qwen3-vl-plus)

Config file (JSON, same keys): ~/.config/vision/config.json

Exit codes: 0 = recognized (text on stdout); 2 = configuration error;
3 = input error; 4 = API error.
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULTS = {
    "provider": "dashscope",
    "api_key": "",
    "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3-vl-plus",
}

ENV_KEYS = {
    "VISION_PROVIDER": "provider",
    "VISION_API_KEY": "api_key",
    "VISION_ENDPOINT": "endpoint",
    "VISION_MODEL": "model",
}

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "vision" / "config.json"

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_INPUT = 3
EXIT_API = 4


class VisionError(Exception):
    """Base class for user-facing errors."""

    exit_code = 1


class ConfigError(VisionError):
    exit_code = EXIT_CONFIG


class InputError(VisionError):
    exit_code = EXIT_INPUT


class ApiError(VisionError):
    exit_code = EXIT_API


KEY_BY_CONFIG = {value: key for key, value in ENV_KEYS.items()}


def config_guidance() -> str:
    return (
        "No API key is configured for the vision skill.\n"
        "\n"
        "Set the environment variable (recommended):\n"
        f"    export {KEY_BY_CONFIG['api_key']}=<your-key>\n"
        "\n"
        "or create a config file:\n"
        f"    {DEFAULT_CONFIG_PATH}  ->  {{\"api_key\": \"<your-key>\"}}\n"
        "\n"
        "Get a key from Aliyun Bailian (bailian.console.aliyun.com) at "
        "https://bailian.console.aliyun.com/ (API-KEY management page).\n"
        "Optional overrides:\n"
        f"    {KEY_BY_CONFIG['model']}   model name (default {DEFAULTS['model']})\n"
        f"    {KEY_BY_CONFIG['endpoint']} OpenAI-compatible base URL (default {DEFAULTS['endpoint']})\n"
        f"    {KEY_BY_CONFIG['provider']} provider name (default {DEFAULTS['provider']})"
    )


def load_config(env=None, config_path=None) -> dict:
    """Resolve config: env vars > config file > defaults."""
    env = dict(env) if env is not None else dict(os.environ)
    config_path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH

    cfg = dict(DEFAULTS)
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Cannot read config file {config_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"Config file {config_path} must contain a JSON object.")
        for key in DEFAULTS:
            if isinstance(data.get(key), str) and data[key]:
                cfg[key] = data[key]
    for var, key in ENV_KEYS.items():
        if env.get(var):
            cfg[key] = env[var]

    if not cfg["api_key"]:
        raise ConfigError(config_guidance())
    parts = urllib.parse.urlsplit(cfg["endpoint"])
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ConfigError(
            f"Invalid endpoint '{cfg['endpoint']}' — must be an http(s) URL "
            "with a host, e.g. https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    return cfg


MIME_BY_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # further checked below
    (b"BM", "image/bmp"),
)

MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _detect_mime(data: bytes, filename: str) -> str:
    for magic, mime in MIME_BY_MAGIC:
        if data.startswith(magic):
            if mime == "image/webp" and data[8:12] != b"WEBP":
                continue
            return mime
    ext = Path(filename).suffix.lower()
    if ext in MIME_BY_EXT:
        return MIME_BY_EXT[ext]
    raise InputError(
        f"Unsupported image format for '{filename}'. "
        "Supported: PNG, JPEG, GIF, WebP, BMP."
    )


def prepare_image_content(image_ref: str) -> dict:
    """Normalize any accepted image input to OpenAI vision content.

    Accepted forms (ticket 03): local file path, http(s) URL, base64 data URI.
    All three produce the identical output shape.
    """
    image_ref = image_ref.strip()
    if image_ref.startswith(("http://", "https://")):
        url = image_ref
    elif image_ref.startswith("data:"):
        url = _validate_data_uri(image_ref)
    else:
        path = Path(image_ref)
        if not path.exists():
            raise InputError(f"Image file not found: {image_ref}")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise InputError(f"Cannot read image file {image_ref}: {exc}") from exc
        mime = _detect_mime(data, path.name)
        url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    return {"type": "image_url", "image_url": {"url": url}}


_DATA_URI_RE = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/]+={0,2})$")


def _validate_data_uri(uri: str) -> str:
    """Accept only well-formed base64 image data URIs (ticket 03)."""
    match = _DATA_URI_RE.match(uri)
    if not match:
        raise InputError(
            "Invalid base64 data URI — expected the form "
            "'data:image/<type>;base64,<payload>' (e.g. data:image/png;base64,iVBOR...)."
        )
    payload = match.group(1)
    if len(payload) % 4 != 0:
        raise InputError("Invalid base64 data URI — payload length is not a multiple of 4.")
    return uri


DEFAULT_PROMPT = (
    "Describe this image in detail: transcribe all visible text verbatim and "
    "describe the objects, people, layout and context. This description will "
    "be used by another model that cannot see the image."
)

DEFAULT_TIMEOUT = 120


def _default_opener(url, headers, data):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {}
    try:
        return resp.status, json.loads(raw)
    except ValueError as exc:
        raise ApiError(f"Vision API returned a non-JSON response (HTTP {resp.status})") from exc


def call_vision(config: dict, image_content: dict, prompt: str = None, opener=None) -> str:
    """Call the configured vision model and return the recognition text."""
    if not config.get("api_key"):
        raise ConfigError(config_guidance())
    url = config["endpoint"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    image_content,
                    {"type": "text", "text": prompt or DEFAULT_PROMPT},
                ],
            }
        ],
    }
    opener = opener or _default_opener
    try:
        status, body = opener(url, headers, json.dumps(payload).encode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException) as exc:
        raise ApiError(f"Could not reach the vision API at {url}: {exc}") from exc

    if status != 200:
        message = body.get("error", {}).get("message") if isinstance(body, dict) else None
        detail = f": {message}" if message else ""
        raise ApiError(f"Vision API returned HTTP {status}{detail}")
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ApiError(f"Unexpected response from the vision API: {body!r}") from exc
    if not isinstance(text, str) or not text.strip():
        raise ApiError(
            "The vision API returned an empty recognition result — refusing to "
            "hand back empty text as if the image were recognized."
        )
    return text


USAGE = """usage: recognize.py <image> [--prompt <text>] [--json]

<image>  local file path, http(s) URL, or base64 data URI
--prompt override the recognition prompt sent to the vision model
--json   print a JSON object: {source, model, provider, text}
--help   show this help

Configure with VISION_API_KEY (see config_guidance on error), or
~/.config/vision/config.json. Optional: VISION_MODEL, VISION_ENDPOINT,
VISION_PROVIDER."""


def _usage_error() -> int:
    print(USAGE, file=sys.stderr)
    return EXIT_CONFIG


def main(argv=None, env=None, config_path=None, opener=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    image = None
    prompt = None
    as_json = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--prompt",):
            i += 1
            if i >= len(argv):
                return _usage_error()
            prompt = argv[i]
        elif arg == "--json":
            as_json = True
        elif arg in ("--help", "-h"):
            print(USAGE)
            return EXIT_OK
        elif arg.startswith("-"):
            return _usage_error()
        else:
            image = arg
        i += 1

    if not image:
        return _usage_error()

    try:
        config = load_config(env=env, config_path=config_path)
        image_content = prepare_image_content(image)
        text = call_vision(config, image_content, prompt=prompt, opener=opener)
    except VisionError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code

    if as_json:
        print(json.dumps({
            "source": image,
            "model": config["model"],
            "provider": config["provider"],
            "text": text,
        }, ensure_ascii=False))
    else:
        print(text)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
