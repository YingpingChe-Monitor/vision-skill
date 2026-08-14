#!/usr/bin/env python3
"""Setup wizard for the `vision` skill (stdlib only, no dependencies).

Writes API key / model / endpoint / provider to the project config file
(nearest .vision.config.json walking up from CWD) or the user config file
(~/.config/vision/config.json). Same keys and precedence as recognize.py:
environment variables > project config > user config > defaults.

Usage:
    python setup.py                                  interactive wizard
    python setup.py --show                           show effective config (key masked)
    python setup.py --set <key>=<value> [--set ...] [--target project|user]
                                                     write config non-interactively
    python setup.py --target <project|user>          interactive, preselect target

Keys: provider, api_key, endpoint, model.

Exit codes: 0 ok · 2 config error · 3 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import recognize

CONFIG_KEYS = ("provider", "api_key", "endpoint", "model")

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_USAGE = 3

KEY_GET_URL = "https://bailian.console.aliyun.com/ (API-KEY management page)"


class SetupError(Exception):
    exit_code = EXIT_CONFIG


def mask_key(key: str) -> str:
    """Mask an API key for display: 'sk-1234567890abcdef' -> 'sk-***cdef'."""
    if not key:
        return "(not set)"
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}***{key[-4:]}"


def _safe_read(path: Path) -> dict:
    """Read a config file; return {} if missing or corrupt (show-mode tolerant)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_each(env=None, config_path=None, project_config_path=None) -> dict:
    """Resolve each key to (value, source); source is env|project|user|default.

    Matches recognize.load_config semantics: for every key, the first non-empty
    value wins in order env > project > user > default. A project config that
    lacks a key falls back to the user config for that key.
    """
    env = dict(env) if env is not None else dict(os.environ)
    config_path = Path(config_path) if config_path is not None else recognize.DEFAULT_CONFIG_PATH
    if project_config_path is None:
        project_config_path = recognize._find_project_config()
    if isinstance(project_config_path, str):
        project_config_path = Path(project_config_path)

    project_data = (_safe_read(project_config_path)
                    if project_config_path is not None and project_config_path.exists() else {})
    user_data = _safe_read(config_path) if config_path.exists() else {}

    resolved = {}
    for key in CONFIG_KEYS:
        value = recognize.DEFAULTS[key]
        source = "default"
        env_var = recognize.KEY_BY_CONFIG.get(key)
        if env_var and env.get(env_var):
            value = env[env_var]
            source = "env"
        else:
            for data, src in ((project_data, "project"), (user_data, "user")):
                candidate = data.get(key)
                if isinstance(candidate, str) and candidate:
                    value = candidate
                    source = src
                    break
        resolved[key] = (value, source)
    return resolved


def write_config(path: Path, updates: dict) -> dict:
    """Merge `updates` (only CONFIG_KEYS) into the file at `path`.

    Preserves unknown keys already present in the file. Returns the full dict
    that was written. Raises SetupError when an existing file is unreadable.
    """
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SetupError(f"Cannot read existing config file {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SetupError(f"Config file {path} must contain a JSON object.")
    data.update({k: v for k, v in updates.items() if k in CONFIG_KEYS})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)  # keep the API key user-private (no-op-ish on Windows)
    except OSError:
        pass
    os.replace(tmp, path)  # atomic on both POSIX and Windows
    return data


def target_path(target: str, cwd: Path, config_path=None) -> Path:
    if target == "user":
        return Path(config_path) if config_path is not None else recognize.DEFAULT_CONFIG_PATH
    return recognize._find_project_config(cwd) or (cwd / recognize.PROJECT_CONFIG_NAME)


GITIGNORE_COMMENT = "# vision skill: never commit the API key (auto-added by setup.py)"


def ensure_gitignore(config_path: Path) -> Path | None:
    """Make sure the directory of a project config file ignores it in git.

    Appends an entry for `config_path.name` to `<dir>/.gitignore` (creating the
    file when missing) unless it is already covered. Returns the gitignore path,
    or None when the config is not project-level. Raises SetupError when the
    gitignore cannot be read or written.
    """
    gitignore = config_path.parent / ".gitignore"
    try:
        text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    except OSError as exc:
        raise SetupError(f"Cannot read {gitignore}: {exc}") from exc
    if any("vision.config.json" in line for line in text.splitlines()):
        return gitignore
    addition = f"{GITIGNORE_COMMENT}\n{config_path.name}\n"
    if text:
        if not text.endswith("\n"):
            text += "\n"
        addition = "\n" + addition
    try:
        gitignore.write_text(text + addition, encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"Cannot update {gitignore}: {exc}") from exc
    return gitignore


def describe_target(target: str, cwd: Path) -> str:
    if target == "user":
        return f"user config  {recognize.DEFAULT_CONFIG_PATH}  (this user only; key stays out of git)"
    return (
        f"project config  {target_path('project', cwd)}  "
        "(shared with the repo - ! a public repo would leak the API key)"
    )


def _ask(prompt: str, current: str, required: bool = False, mask: bool = False) -> str:
    suffix = f" (current: {mask_key(current) if mask else current})" if current else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw:
            return raw
        if current:
            return current
        if not required:
            return ""
        print(f"  This field is required (get a key from {KEY_GET_URL}). Ctrl+C aborts.")


def _ask_target(cwd: Path, preset: str | None) -> str:
    if preset in ("project", "user"):
        return preset
    print("\nWhere should the configuration be saved?")
    print(f"  u = user config     {recognize.DEFAULT_CONFIG_PATH}")
    print(f"  p = project config  {recognize._find_project_config(cwd) or (cwd / recognize.PROJECT_CONFIG_NAME)}")
    print("      (project config is committed to the repo - only pick it for a private repo)")
    while True:
        choice = input("Save to [u]ser / [p]roject (default: user): ").strip().lower()
        if choice in ("", "u", "user"):
            return "user"
        if choice in ("p", "project"):
            return "project"
        print("  Enter 'u' or 'p'.")


def interactive(cwd: Path, env: dict, preset_target: str | None) -> int:
    current = {key: resolve_each(env=env)[key][0] for key in CONFIG_KEYS}

    print("vision skill setup wizard - Enter keeps the current value shown in parentheses.")
    print("(Get a key from Aliyun Bailian: " + KEY_GET_URL + ")\n")

    provider = _ask("Provider", current["provider"])
    api_key = _ask("API key", current["api_key"], required=not current["api_key"], mask=True)
    endpoint = _ask("Endpoint", current["endpoint"])
    model = _ask("Model", current["model"])

    target = _ask_target(cwd, preset_target)
    path = target_path(target, cwd)

    updates = {k: v for k, v in (("provider", provider), ("api_key", api_key),
                                 ("endpoint", endpoint), ("model", model)) if v}
    print(f"\nWill write to {path}:")
    for key, value in updates.items():
        shown = mask_key(value) if key == "api_key" else value
        print(f"  {key:<10} {shown}")
    confirm = input("Write? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted - nothing was written.")
        return EXIT_OK

    if target == "project":
        ensure_gitignore(path)  # keep the API key out of git even on public repos
    write_config(path, updates)
    print(f"\nSaved to {path}.")
    _print_next_steps(path)
    return EXIT_OK


def _print_next_steps(path: Path) -> None:
    script = Path(__file__).resolve()
    print("Next steps:")
    print(f"  - Verify: python \"{script.parent / 'recognize.py'}\" <image-path-or-url>")
    print(f"  - Reset:  delete {path}, or re-run this wizard and enter a new value")
    print("  - Env override (highest priority): export VISION_API_KEY=... "
          "(and optionally VISION_MODEL / VISION_ENDPOINT / VISION_PROVIDER)")


def show(effective: dict, cwd: Path) -> int:
    print("Effective configuration (environment > project > user > defaults):")
    for key in CONFIG_KEYS:
        value, source = effective[key]
        shown = mask_key(value) if key == "api_key" else value
        print(f"  {key:<10} {shown}   ({source})")
    print("\nFiles:")
    print(f"  project:  {recognize._find_project_config(cwd) or '(none found)'}")
    print(f"  user:     {recognize.DEFAULT_CONFIG_PATH}  "
          f"({'exists' if recognize.DEFAULT_CONFIG_PATH.exists() else 'not found'})")
    return EXIT_OK


def main(argv=None, env=None, cwd=None, config_path=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    env = dict(env) if env is not None else dict(os.environ)
    cwd = Path(cwd) if cwd is not None else Path.cwd()

    parser = argparse.ArgumentParser(
        prog="setup.py",
        description="Configure the vision skill (API key / model / endpoint / provider).",
    )
    parser.add_argument("--show", action="store_true",
                        help="print the effective configuration (API key masked) and exit")
    parser.add_argument("--set", action="append", metavar="KEY=VALUE", default=[],
                        help=f"set a config key ({', '.join(CONFIG_KEYS)}); repeatable")
    parser.add_argument("--target", choices=("project", "user"), default=None,
                        help="write to project (.vision.config.json) or user config; default: user")
    args = parser.parse_args(argv)

    try:
        if args.set:
            updates = {}
            for item in args.set:
                if "=" not in item:
                    print(f"error: --set expects KEY=VALUE, got '{item}'", file=sys.stderr)
                    return EXIT_USAGE
                key, value = item.split("=", 1)
                if key not in CONFIG_KEYS:
                    print(f"error: unknown config key '{key}' "
                          f"(expected one of: {', '.join(CONFIG_KEYS)})", file=sys.stderr)
                    return EXIT_USAGE
                updates[key] = value
            target = args.target or "user"
            if target == "project":
                print("note: writing to the project config - the API key is kept out of "
                      "git via .gitignore, but only do this for a private repo.")
            path = target_path(target, cwd, config_path=config_path)
            if target == "project":
                ensure_gitignore(path)  # keep the API key out of git even on public repos
            write_config(path, updates)
            print(f"Saved to {path}:")
            for key, value in updates.items():
                shown = mask_key(value) if key == "api_key" else value
                print(f"  {key:<10} {shown}")
            _print_next_steps(path)
            return EXIT_OK
        if args.show:
            return show(resolve_each(env=env, config_path=config_path), cwd)
        if args.target:
            return interactive(cwd, env, preset_target=args.target)
        return interactive(cwd, env, preset_target=None)
    except SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\nAborted by user.")
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
