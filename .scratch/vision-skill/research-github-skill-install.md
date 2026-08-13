# 2025 年 GitHub 上 Agent Skills 安装方式惯例调研

> 调研日期：2025-10 之后（Skills 于 2025-10-16 由 Anthropic 正式发布）。所有结论均来自 primary sources（官方仓库 README、官方文档、官方网站），原文逐一核实；`code.claude.com` 官方文档页面因网络无法直接抓取，其要点以官方仓库 README 中的链接与交叉印证为准。

## 一、四种主流安装方式

**1. Claude Code Plugin Marketplace（最主流）**
在 Claude Code 会话里把 GitHub 仓库注册为 plugin marketplace，再一键安装插件（插件内含 skills）：
```
/plugin marketplace add <owner>/<repo>
/plugin install <plugin-name>@<marketplace-name>
```
- anthropics/skills 官方 README 即以此教学（`/plugin marketplace add anthropics/skills` → 浏览并安装 `anthropic-agent-skills` 插件，或 `/plugin install document-skills@anthropic-agent-skills`）：https://github.com/anthropics/skills
- obra/superpowers README（`/plugin marketplace add obra/superpowers-marketplace` + `/plugin install superpowers@superpowers-marketplace`，也可从官方 marketplace 直接装）：https://github.com/obra/superpowers
- 社区列表 awesome-claude-skills 亦以此为首选，并支持 `/plugin add /path/to/skill-dir` 本地安装：https://github.com/travisvn/awesome-claude-skills

**2. 直接复制目录（官方文档标准）**
skill 就是一个含 `SKILL.md`（YAML frontmatter：`name` + `description`）的目录，复制到 `~/.claude/skills/<name>/`（用户级）或 `.claude/skills/<name>/`（项目级）即完成安装。Claude Code 官方 Skills 文档（https://code.claude.com/docs/en/skills）与 skills.sh CLI 官方仓库 README 中的安装路径表（`.claude/skills/`、`~/.claude/skills/`）一致：https://github.com/vercel-labs/skills

**3. skills.sh CLI（`npx skills add`）**
skills.sh 是 Vercel 维护的 Agent Skills 目录网站（排行榜、官方区、安全审计）+ 配套 CLI（开源仓库 vercel-labs/skills）。`npx skills add <owner>/<repo>` 一条命令自动检测本机 agent（支持 70+ 种，含 Claude Code）并装到项目级 `.claude/skills/` 或全局 `~/.claude/skills/`（`-g`），可选 symlink/copy、按 skill 筛选：https://skills.sh 、https://github.com/vercel-labs/skills
- mattpocock/skills README 对非 Claude Code agent（Codex 等）即推荐 `npx skills@latest add mattpocock/skills`，同时该仓库已上架官方 marketplace（`/plugin install mattpocock-skills`）：https://github.com/mattpocock/skills

**4. 官方 marketplace（claude-plugins-official）**
上架 Anthropic 官方 marketplace 后用户可直接 `/plugin install <name>`（如 obra 的 `superpowers@claude-plugins-official`、mattpocock 的 `mattpocock-skills`），无需先 add 仓库——最省事但需官方审核，非所有仓库可得。

**未查到可靠来源**：skills 的商业付费 marketplace 机制（官方 FAQ 仅称"未来计划"）；无 `install.sh` 约定——未在任何 primary source 见到统一约定。

## 二、推荐组合（发布到 GitHub 的标准 skill 仓库）

**仓库应预置**：
1. 标准结构：`skills/<name>/SKILL.md` + 可选 `scripts/`、`resources/`（frontmatter 必须有 `name`/`description`）；
2. `.claude-plugin/marketplace.json`（声明 plugin 及其 skill 列表，供 `/plugin marketplace add` 与 skills.sh 发现）；
3. README 顶部放 skills.sh badge 并写明两条安装命令（`/plugin marketplace add` + `npx skills add`）。

**用户侧最省事的一键安装**：
```
# 路径 A：Claude Code 用户
/plugin marketplace add <owner>/<repo>
/plugin install <plugin>@<repo>

# 路径 B：任意 agent（含 Claude Code）
npx skills add <owner>/<repo>
```

**核心结论**：2025 年的惯例是"仓库即 marketplace"——任何 GitHub 仓库只要含 `skills/` 标准目录（或 `.claude-plugin/marketplace.json`），就同时被 Claude Code `/plugin` 命令和 skills.sh CLI 原生支持，无需额外构建；`install.sh` 非必要。
