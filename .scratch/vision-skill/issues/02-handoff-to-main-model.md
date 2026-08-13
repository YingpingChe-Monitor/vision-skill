# 02 — 识别结果交接给主模型（如 DeepSeek）继续处理

**What to build:** 固化"给图 → 视觉模型识别 → 交接 → 主模型继续"的完整工作流。当主 agent 模型本身没有视觉能力（如 DeepSeek）时，收到图片任务先用 vision skill 的视觉模型识别，再把识别文本以标准格式注入对话，并附指示语让主模型基于识别结果完成后续任务（如"识别这张图并写总结"）。用户全程只需要给一张图和一句任务，主模型不直接看图。

**Blocked by:** 01 — Vision skill 骨架：配置 + 阿里云百炼 Qwen-VL 视觉识别

**Status:** ready-for-human

- [ ] 用 DeepSeek 作主模型：给图 + "识别并总结"，最终输出基于识别文本的正确总结
- [x] 交接块的格式稳定、来源清晰，不与主模型自身输出混淆
- [x] 识别失败时向主模型传递明确的错误信息，禁止主模型基于空结果编造内容

## Comments

2025-08-13 — 已实现（`SKILL.md` 的 Handoff protocol 一节）：

- 标准交接块 `[vision-result source=... model=... provider=...] ... [/vision-result]`，
  元数据来自脚本 `--json` 输出（source/model/provider/text），与主模型自身输出天然区分。
- 失败路径：脚本退出码 2/3/4 + 明确错误文本；SKILL.md 明令禁止基于空结果编造内容。

待人工验收：以 DeepSeek 作主模型跑「给图 + 识别并总结」（需真实 API key）。
