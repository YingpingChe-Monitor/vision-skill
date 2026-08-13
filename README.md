# vision skill — 图片识别（Qwen-VL / 任意 OpenAI 兼容视觉模型）

`vision` skill 让**没有视觉能力的主模型**（如 DeepSeek）也能处理图片任务：
用户给一张图（本地路径 / URL / 粘贴的 base64 data URI）+ 一句任务，skill 调用
已配置的视觉模型完成识别，再把识别文本按标准格式交接给主模型继续处理。

识别模型默认为阿里云百炼（DashScope）OpenAI 兼容端点的 Qwen-VL 系列，
provider / API key / 模型名 / 端点均可配置，也支持换成任意 OpenAI 兼容
视觉模型（OpenAI、vLLM、本地代理等）。

## 安装与注册

本仓库内已注册两份（内容一致）：

| Agent | 位置 |
| ----- | ---- |
| Reasonix | `.agents/skills/vision/`（本项目 skills 根目录） |
| Claude Code | `.claude/skills/vision/`（项目级 skills 目录） |

> 规范副本在 `.agents/skills/vision/`；修改后需同步到
> `.claude/skills/vision/`（`cp` 两份文件即可）。

要装到其他项目 / 全局：

```bash
# Claude Code 全局
cp -r .claude/skills/vision ~/.claude/skills/vision
```

## 配置

优先级：**环境变量 > 配置文件 > 默认值**。

| 配置项 | 环境变量 | 配置文件 key | 默认值 |
| ------ | -------- | ------------ | ------ |
| API key（必填） | `VISION_API_KEY` | `api_key` | — |
| 模型 | `VISION_MODEL` | `model` | `qwen-vl-max` |
| 端点 | `VISION_ENDPOINT` | `endpoint` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 提供方 | `VISION_PROVIDER` | `provider` | `dashscope` |

配置文件：`~/.config/vision/config.json`

```json
{ "api_key": "sk-...", "model": "qwen-vl-max" }
```

获取 key：阿里云百炼控制台 https://bailian.console.aliyun.com/ → API-KEY 管理。
未配置时脚本会打印完整的设置引导（退出码 2），不会报晦涩错误。

```bash
# 示例：环境变量方式（PowerShell: $env:VISION_API_KEY="sk-..."）
export VISION_API_KEY="sk-..."
```

## 典型用法

```bash
# 1. 本地图片
python .agents/skills/vision/scripts/recognize.py C:\pics\shot.png

# 2. 网络图片 URL
python .agents/skills/vision/scripts/recognize.py https://example.com/pic.png

# 3. 剪贴板粘贴的 base64 data URI
python .agents/skills/vision/scripts/recognize.py "data:image/png;base64,iVBORw0KGgo..."

# 4. 指定任务 + 结构化输出（用于交接给主模型）
python .agents/skills/vision/scripts/recognize.py C:\pics\shot.png --prompt "提取图中的订单号" --json
```

三种输入走同一条识别流程，输出格式完全一致。退出码：`0` 成功 · `2` 配置或用法错误 ·
`3` 输入错误 · `4` API 错误。

### 交接给主模型（完整工作流）

用户：给图 + 「识别并总结这张图」。

1. 主模型调用 vision skill 识别图片；
2. 识别文本以标准块注入对话：

```
[vision-result source="C:\pics\shot.png" model="qwen-vl-max" provider="dashscope"]
<识别文本（逐字来自视觉模型）>
[/vision-result]
```

3. 主模型只依据块内文本完成总结/回答；识别失败时如实转达错误，
   **禁止基于空结果编造图片内容**（详见 `SKILL.md` 的 Handoff protocol）。

## 验证

```bash
python -m unittest discover -s tests          # 32 项单元 + 本地 mock 服务器 E2E
python .agents/skills/vision/scripts/recognize.py --help
```

E2E 测试内置一个本地 mock 视觉服务（`tests/test_recognize.py`），不依赖外网。
配置真实 key 后的端到端验收（两个 agent 实测）见
`.scratch/vision-skill/issues/`。
