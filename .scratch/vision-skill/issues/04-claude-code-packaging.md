# 04 — Claude Code 端到端验证与安装说明

**What to build:** 双 agent 打包收尾：把 skill 注册进 Claude Code（`.claude/skills/` 或全局 skills 目录）与 Reasonix（skills 根目录），补齐 `agents/openai.yaml` 接口元数据（如该仓库惯例需要），并编写 README/示例，覆盖配置步骤与典型用法（给图 → 识别 → 主模型后续处理）。验收以两个 agent 实测跑通为准。

**Blocked by:** 01 — Vision skill 骨架：配置 + 阿里云百炼 Qwen-VL 视觉识别；02 — 识别结果交接给主模型（如 DeepSeek）继续处理

**Status:** ready-for-human

- [ ] 在 Claude Code 中调用该 skill 跑通"给图 → 识别 → 后续处理"完整流程
- [x] 在 Reasonix 中调用同一 skill 跑通同样流程（本对话即 Reasonix + DeepSeek 主模型：识别 Man day.png 成功）
- [x] 安装/注册说明与示例文档覆盖配置步骤和典型用法

## Comments

2025-08-13 — 已实现：

- Reasonix 注册：`.agents/skills/vision/`（SKILL.md + scripts/recognize.py + agents/openai.yaml）。
- Claude Code 注册：`.claude/skills/vision/`（项目级，SKILL.md + scripts/recognize.py）。
- `README.md`：配置步骤（env/配置文件/获取 key）、三种输入用法、交接工作流示例、验证方法。
- 规范副本为 `skills/vision/`，README 注明同步方式。

2025-08-13 — 发布完成：仓库已推送
https://github.com/YingpingChe-Monitor/vision-skill（`skills/vision/` 标准结构 +
`.claude-plugin/marketplace.json`），用户侧一键安装：
`/plugin marketplace add YingpingChe-Monitor/vision-skill` +
`/plugin install vision@vision-skills`，或 `npx skills add YingpingChe-Monitor/vision-skill`。

2025-08-13 — 验收：Reasonix 侧跑通（本对话以 DeepSeek 为主模型，调用 vision
skill 识别真实图片 Man day.png 并完成交接总结）。仅剩 Claude Code 端一键安装
实测（需在 Claude Code 会话中执行 /plugin 命令）。
