# 01 — Vision skill 骨架：配置 + 阿里云百炼 Qwen-VL 视觉识别

**What to build:** 创建 `vision` skill（SKILL.md，英文正文，frontmatter 同时满足 Reasonix 与 Claude Code 的 skill 发现规则），这是后续所有票的基础。skill 支持配置"识别图像的 AI 模型"：provider / API key / 模型名 / 端点均可配置，环境变量优先、配置文件兜底，默认指向阿里云百炼 OpenAI 兼容端点（`https://dashscope.aliyuncs.com/compatible-mode/v1`）与 Qwen-VL 系列视觉模型（模型名可覆盖）。核心行为：用户给出本地图片路径，skill 调用已配置的视觉模型完成识别，把识别文本返回对话；未配置时给出清晰的引导式说明（如何设置 key），而不是晦涩报错。

**Blocked by:** None — can start immediately

**Status:** ready-for-human

- [x] 配置百炼 API key 后，给定本地图片路径，能返回识别文本
- [x] 未配置时给出清晰引导（设置哪些环境变量、如何获取 key），不产生晦涩错误
- [x] 模型名与端点可覆盖（默认 Qwen-VL / 百炼兼容端点，可换成其他 OpenAI 兼容模型）
- [x] 配置同时支持环境变量与配置文件两种来源，环境变量优先
- [x] SKILL.md frontmatter 能被 Reasonix 和 Claude Code 双方识别为可调用 skill

## Comments

2025-08-13 — 已实现（见 `.agents/skills/vision/`）：

- `scripts/recognize.py`：stdlib-only，配置解析（env > `~/.config/vision/config.json` > 默认值）、
  三种输入形式、OpenAI 兼容 chat/completions 调用、清晰错误与退出码（0/2/3/4）。
- `SKILL.md`（英文正文，frontmatter 含 name+description，双方可识别）+ `agents/openai.yaml`。
- 测试：`tests/test_recognize.py` 32 项（单元 + 本地 mock HTTP 服务器 E2E，`python -m unittest discover -s tests`）。

待人工验收：配置真实百炼 API key 后跑一次本地图片识别（E2E 目前用 mock 服务器验证全链路，
脚本本身不依赖外网即可测试）。
