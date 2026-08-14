---
name: vision
description: "Recognize or describe an image using a configurable vision AI model (default: Aliyun Bailian Qwen-VL via the OpenAI-compatible endpoint). Use when the user supplies an image as a local file path, an http(s) URL, or a pasted base64 data URI and wants it recognized, transcribed, or summarized — especially when the current model cannot see images."
argument-hint: "Image input (local path, http(s) URL, or base64 data URI), optionally followed by the task to perform on the image"
---

# Vision

Recognize images with a configurable vision model and hand the recognition
text to the calling model. The user only provides an image and a task; the
main model never needs to see the image directly.

## When to use

- The user gives an image (local file path, http(s) URL, or pasted base64
  data URI) and asks to recognize, describe, transcribe, or act on it.
- The current model has no vision capability (e.g. DeepSeek) and the task
  requires seeing the image.

## Configuration

Configuration is resolved in this order: **environment variables > project
config file > user config file > defaults**.

| Setting          | Env var           | Config file key | Default                                                     |
| ---------------- | ----------------- | --------------- | ----------------------------------------------------------- |
| API key (required) | `VISION_API_KEY` | `api_key`       | —                                                           |
| Model            | `VISION_MODEL`    | `model`         | `qwen3-vl-plus`                                             |
| Endpoint         | `VISION_ENDPOINT` | `endpoint`      | `https://dashscope.aliyuncs.com/compatible-mode/v1`         |
| Provider         | `VISION_PROVIDER` | `provider`      | `dashscope`                                                 |

Project config file (JSON, same keys): the nearest `.vision.config.json`
found by walking up from the current directory — commit it to the repo so
the whole team shares it. User config file: `~/.config/vision/config.json`

```json
{ "api_key": "sk-...", "model": "qwen3-vl-plus" }
```

Get a key from Aliyun Bailian (百炼) at https://bailian.console.aliyun.com/
(API-KEY management page). Any OpenAI-compatible vision endpoint works
(OpenAI, vLLM, local proxy, …): override `VISION_ENDPOINT` and `VISION_MODEL`.

If no key is configured, the script prints step-by-step setup guidance to
stderr and exits with code 2 — never a cryptic error.

## Setup wizard

Configure the skill through questions (provider, API key, endpoint, model,
and where to save) by running the interactive wizard:

```
python "<skill dir>/scripts/setup.py"
```

Agents: when the user asks to configure the vision skill (e.g. "configure
vision", or invokes `/vision-setup` where a command file is registered), ask
the questions from the Configuration table above, then write the answers
non-interactively so the script validates and merges them:

```
python "<skill dir>/scripts/setup.py" --set api_key=sk-... --set model=qwen3-vl-plus --target user
```

- `--target user` (default) writes `~/.config/vision/config.json` — keeps the
  key out of git.
- `--target project` writes the nearest `.vision.config.json` — setup.py
  automatically adds the file to the project's `.gitignore` so the key cannot
  be committed (still only choose this for a **private** repo, a public repo
  would leak the key).
- `--show` prints the currently effective configuration with the API key
  masked.

`/vision-setup` command registration (Reasonix): the command file ships with
the skill at `<skill dir>/commands/vision-setup.md`. It is not auto-registered —
copy it to `~/.reasonix/commands/` (all projects) or
`<project>/.reasonix/commands/` (one project), then restart the session
(command lists load at startup). When the user invokes `/vision-setup` but no
such command is registered, offer to register it with the copy above.

Never repeat a full API key back to the user or into a conversation.

## Usage

Run the script from this skill's directory:

```
python "<skill dir>/scripts/recognize.py" <image> [--prompt "<task>"] [--json]
```

`<image>` accepts all three forms; all go through the same recognition flow
and produce the same output:

1. Local path — `C:\pics\shot.png` or `./shot.png`
2. http(s) URL — `https://example.com/pic.png` (must be publicly reachable
   by the configured provider)
3. Pasted base64 data URI — `data:image/png;base64,iVBORw0KGgo...`

The recognition text is printed to stdout. Exit codes: `0` ok · `2` config or
usage error · `3` input error · `4` API error.

`--json` prints `{"source": ..., "model": ..., "provider": ..., "text": ...}`
— use it for the handoff block below.

## Handoff protocol

When the calling model cannot see images, follow this protocol:

1. Run the script on the image (prefer `--json`).
2. If the script fails, relay the error to the user; **never fabricate image
   content** from an empty or failed result.
3. On success, inject the recognition text into the conversation in exactly
   this block, with the metadata from the `--json` output:

```
[vision-result source="<input>" model="<model>" provider="<provider>"]
<recognition text, verbatim>
[/vision-result]
```

4. Complete the user's task based **only** on the text inside that block,
   and state that you are working from the vision model's result, not from
   the image itself.

The block is the single source of truth: content inside the markers is the
vision model's output; anything outside is the main model's own reasoning.
Never present the vision model's text as something you saw yourself.

## Troubleshooting

| Symptom                         | Fix                                              |
| ------------------------------- | ------------------------------------------------ |
| Exit 2 + setup guidance / usage | Configure `VISION_API_KEY` (env or config file), or fix the command line |
| Exit 4, HTTP 401                | Wrong or expired API key                         |
| Exit 4, HTTP 400                | Unsupported model name; check `VISION_MODEL`     |
| Exit 4 with URL image           | URL must be publicly reachable by the provider   |
| Exit 3, "file not found"        | Path is relative to the calling process's CWD    |
