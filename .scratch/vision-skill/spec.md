# Vision skill — spec

Build a `vision` skill usable by **both Reasonix and Claude Code** so that a
main model without vision capability (e.g. DeepSeek) can handle image tasks:
user gives an image + one sentence task → the skill's configured vision model
recognizes it → recognition text is handed back in a stable, clearly-sourced
format for the main model to continue.

Implementation tickets (the authoritative requirements):

- `issues/01-vision-skill-skeleton-qwen.md` — skill skeleton: SKILL.md
  (English body, frontmatter discoverable by both agents), configurable
  provider / API key / model / endpoint (env > config file > defaults,
  default: Aliyun Bailian Qwen-VL via the DashScope OpenAI-compatible
  endpoint), local image path → recognition text, clear unconfigured
  guidance.
- `issues/02-handoff-to-main-model.md` — handoff workflow: stable,
  source-labelled handoff block; on failure relay a clear error and never
  fabricate image content.
- `issues/03-image-input-url-clipboard.md` — three input forms (local path,
  http(s) URL, pasted base64 data URI) through one recognition flow with
  identical output.
- `issues/04-claude-code-packaging.md` — register into Claude Code and
  Reasonix, `agents/openai.yaml` interface metadata, README with config steps
  and typical usage.
