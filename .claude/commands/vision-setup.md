---
description: Configure the vision skill (API key / model / endpoint) through questions
---

# vision skill setup wizard

The user wants to configure the vision skill (API key / model / endpoint / provider).
Complete the configuration through a question-and-answer flow:

1. **Locate setup.py**: try in order
   `<project>/.agents/skills/vision/scripts/setup.py`,
   `<project>/.claude/skills/vision/scripts/setup.py`,
   `<project>/skills/vision/scripts/setup.py`;
   if none exist, ask the user where the skill is installed.

2. **Ask the user each question** (first run `python "<setup.py path>" --show`
   so the user sees current values with the key masked; Enter keeps the current
   value):
   - provider (default `dashscope`)
   - api_key (required; on first setup point to
     https://bailian.console.aliyun.com/ API-KEY management page)
   - endpoint (default `https://dashscope.aliyuncs.com/compatible-mode/v1`)
   - model (default `qwen3-vl-plus`)

3. **Ask where to save** and state the risk:
   - user-level (recommended): `~/.config/vision/config.json`, this user only,
     key stays out of git
   - project-level: `.vision.config.json`, committed to the repo — a public
     repo would leak the API key; only choose it for a private repo

4. **Write** (substitute real values):

   ```bash
   python "<setup.py absolute path>" --set api_key=<key> [--set model=<model>] [--set endpoint=<endpoint>] [--set provider=<provider>] --target <user|project>
   ```

5. **Wrap up**: relay the script output (the key is masked); suggest verifying
   with `python "<skill>/scripts/recognize.py" <image-path-or-url>`.
   Never repeat the full API key in the conversation.
