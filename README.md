# vision skill — 图片识别（Qwen-VL / 任意 OpenAI 兼容视觉模型）

`vision` skill 让**没有视觉能力的主模型**（如 DeepSeek）也能处理图片任务：
用户给一张图（本地路径 / URL / 粘贴的 base64 data URI）+ 一句任务，skill 调用
已配置的视觉模型完成识别，再把识别文本按标准格式交接给主模型继续处理。

识别模型默认为阿里云百炼（DashScope）OpenAI 兼容端点的 Qwen-VL 系列，
provider / API key / 模型名 / 端点均可配置，也支持换成任意 OpenAI 兼容
视觉模型（OpenAI、vLLM、本地代理等）。

## 安装与注册

### 方式一：复制即安装（最简单，官方文档标准方式）

skill 就是一个含 `SKILL.md` 的目录，复制到 skills 目录即完成安装：

```bash
# 1. 获取仓库（任选其一）
git clone https://github.com/YingpingChe-Monitor/vision-skill.git
# 或下载 zip 解压：https://github.com/YingpingChe-Monitor/vision-skill/archive/refs/heads/main.zip

cd vision-skill

# 2. 复制即安装（任选一个目标位置）
cp -r skills/vision ~/.claude/skills/vision                  # Claude Code 用户级（全局）
cp -r skills/vision <你的项目>/.claude/skills/vision         # Claude Code 项目级
cp -r skills/vision <你的项目>/.agents/skills/vision         # Reasonix 项目级
```

### 方式二：GitHub 一键安装

本仓库是标准「仓库即 marketplace」结构（`skills/vision/` + `.claude-plugin/marketplace.json`），
已发布到 https://github.com/YingpingChe-Monitor/vision-skill ：

```
# Claude Code（先 add 仓库为 marketplace，再装插件）
/plugin marketplace add YingpingChe-Monitor/vision-skill
/plugin install vision@vision-skills

# 任意 agent（skills.sh 自动识别 Claude Code/Codex 等 70+ 种并装到正确路径）
npx skills add YingpingChe-Monitor/vision-skill
```

### 本仓库内的注册

| Agent | 位置 |
| ----- | ---- |
| Reasonix | `.agents/skills/vision/`（本项目 skills 根目录） |
| Claude Code | `.claude/skills/vision/`（项目级 skills 目录） |
| Reasonix 命令 | `.reasonix/commands/vision-setup.md`（本地注册，不进 git） |
| Claude Code 命令 | `.claude/commands/vision-setup.md` |

> 规范副本在 `skills/vision/`；修改后需同步到两个注册位
> （`.agents/skills/vision/` 与 `.claude/skills/vision/`，`cp` 即可）。

手动装到其他项目 / 全局：

```bash
# Claude Code 全局
cp -r .claude/skills/vision ~/.claude/skills/vision
```

### 更新已安装的技能

远程仓库更新后（新功能 / bug 修复），按安装方式对应更新：

**skills.sh 方式**（在安装了 skill 的项目目录下运行）：

```bash
npx skills update vision       # 只更新 vision（推荐）
npx skills update              # 更新该项目全部 skills
npx skills update vision -g    # 全局安装的用 -g（用户级）
```

**Claude Code `/plugin` 方式**（在 Claude Code 会话中）：

```
/plugin marketplace update     # 拉取远程最新 marketplace
/plugin update                 # 更新已安装插件（或在 /plugin 菜单选择）
```

Claude Code 本身有后台自动更新，插件会定期自动拉新；直接重新执行
`/plugin install vision@vision-skills` 也能强制覆盖为最新版。

**更新后确认**：

1. 新功能是否到位：`ls <skill目录>/scripts/` 应能看到 `recognize.py` 与
   `setup.py`（配置向导、自动 `.gitignore` 保护均在其中）；
2. 若之前手动注册过 `/vision-setup` 命令文件，重新复制一次——
   旧副本不会随更新自动覆盖：

   ```bash
   # Claude Code 用户级（所有项目）
   cp <skill目录>/commands/vision-setup.md ~/.claude/commands/vision-setup.md
   # Reasonix 用户级（所有项目）
   cp <skill目录>/commands/vision-setup.md ~/.reasonix/commands/vision-setup.md
   ```

   （项目级分别复制到 `<项目>/.claude/commands/` 与 `<项目>/.reasonix/commands/`。）

## 配置

优先级：**环境变量 > 项目配置文件 > 用户配置文件 > 默认值**。

| 配置项 | 环境变量 | 配置文件 key | 默认值 |
| ------ | -------- | ------------ | ------ |
| API key（必填） | `VISION_API_KEY` | `api_key` | — |
| 模型 | `VISION_MODEL` | `model` | `qwen3-vl-plus` |
| 端点 | `VISION_ENDPOINT` | `endpoint` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 提供方 | `VISION_PROVIDER` | `provider` | `dashscope` |

- **项目配置文件**（推荐，团队共享）：从当前目录向上查找最近的 `.vision.config.json`，放进仓库根目录即可
- **用户配置文件**：`~/.config/vision/config.json`

```json
{ "api_key": "sk-...", "model": "qwen3-vl-plus" }
```

获取 key：阿里云百炼控制台 https://bailian.console.aliyun.com/ → API-KEY 管理。
未配置时脚本会打印完整的设置引导（退出码 2），不会报晦涩错误。

```bash
# 示例：环境变量方式（PowerShell: $env:VISION_API_KEY="sk-..."）
export VISION_API_KEY="sk-..."
```

### 交互式配置向导（`/vision-setup`）

不想手写配置文件？运行配置向导，通过问答完成全部配置
（provider / API key / endpoint / model，并选择写入用户级还是项目级，
API key 全程打码显示）：

```bash
python skills/vision/scripts/setup.py
```

agent 场景（无需交互）：先逐项询问用户，再一次性写入——

```bash
python skills/vision/scripts/setup.py --set api_key=sk-... --set model=qwen3-vl-plus --target user
```

- `--target user`（默认）写入 `~/.config/vision/config.json`，key 不进 git
- `--target project` 写入项目 `.vision.config.json`，并**自动把该文件加进项目的
  `.gitignore`**（防止 key 被提交泄露）；仍建议只在私有仓库使用
- `--show` 查看当前生效配置（key 打码）

**命令注册**（Reasonix）：命令文件随 skill 一起安装，在
`<skill>/commands/vision-setup.md`。它**不会自动注册**——复制到
`~/.reasonix/commands/`（所有项目生效，推荐）或 `<项目>/.reasonix/commands/`
（仅该项目），然后**重启 reasonix 会话**（命令列表在启动时加载）。本仓库内的
`.reasonix/commands/vision-setup.md` 同理（该目录不进 git，仅本地生效）。
Claude Code 用户用 `.claude/commands/vision-setup.md`（随仓库分发，自动注册）。

## 装完怎么用（普通用户）

装好这个 skill 之后，**你不需要学任何新操作**。就算你的 agent 用的是
DeepSeek 这类**没有视觉识别能力**的大模型（看不了图片），你依然可以像
平时一样，直接把图片丢给它、加上一句任务：

> **你**：帮我看下这张图里有什么 → （发图片 `C:\Work\Man day.png`）
>
> **agent**：好的，我调用视觉模型识别一下…
>
> **agent**：这张图是一张 Cibes 客户的人天分配表，共 6 行报表
> （库存进出汇总 7 天、FIFO 现行价明细 5 天、COGS 10 天、COGM 10 天…），
> 合计约 40 人天。需要我整理成表格或翻译成中文吗？

**背后发生了什么（agent 自动完成，你无感知）**：

1. **识别** — agent 自动调用本 skill，用配置好的视觉模型（默认 qwen3-vl-plus）识别图片；
2. **交接** — 识别到的文字信息按标准格式交给主模型；
3. **回答** — 没有视觉的主模型（如 DeepSeek）基于识别结果整理、回答你的问题。

**给图的三种方式，效果完全一致**：

| 方式 | 例子 |
| ---- | ---- |
| 本地图片路径 | `C:\Work\Man day.png` |
| 网络图片 URL | `https://example.com/pic.png` |
| 粘贴的 base64 data URI | `data:image/png;base64,iVBORw0KGgo...`（从剪贴板粘贴） |

## 命令行直接使用（进阶）

想绕过 agent、直接调脚本时：

```bash
# 1. 本地图片
python skills/vision/scripts/recognize.py C:\pics\shot.png

# 2. 网络图片 URL
python skills/vision/scripts/recognize.py https://example.com/pic.png

# 3. 剪贴板粘贴的 base64 data URI
python skills/vision/scripts/recognize.py "data:image/png;base64,iVBORw0KGgo..."

# 4. 指定任务 + 结构化输出（用于交接给主模型）
python skills/vision/scripts/recognize.py C:\pics\shot.png --prompt "提取图中的订单号" --json
```

三种输入走同一条识别流程，输出格式完全一致。退出码：`0` 成功 · `2` 配置或用法错误 ·
`3` 输入错误 · `4` API 错误。

### 交接给主模型（完整工作流，给开发者）

1. 主模型调用 vision skill 识别图片；
2. 识别文本以标准块注入对话：

```
[vision-result source="C:\pics\shot.png" model="qwen3-vl-plus" provider="dashscope"]
<识别文本（逐字来自视觉模型）>
[/vision-result]
```

3. 主模型只依据块内文本完成总结/回答；识别失败时如实转达错误，
   **禁止基于空结果编造图片内容**（详见 `SKILL.md` 的 Handoff protocol）。

## 验证

```bash
python -m unittest discover -s tests          # 63 项单元 + 本地 mock 服务器 E2E
python skills/vision/scripts/recognize.py --help
```

E2E 测试内置一个本地 mock 视觉服务（`tests/test_recognize.py`），不依赖外网。
配置真实 key 后的端到端验收（两个 agent 实测）见
`.scratch/vision-skill/issues/`。
