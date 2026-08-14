---
description: 配置 vision skill 的 API key / 模型 / 端点(问答式)
argument-hint: ""
---

# vision skill 配置向导

用户想配置 vision skill 的 API key / 模型 / 端点等。按下面步骤以问答方式完成:

1. **定位 setup.py**:依次查找
   `<当前项目>/.agents/skills/vision/scripts/setup.py`、
   `<当前项目>/.claude/skills/vision/scripts/setup.py`、
   `<当前项目>/skills/vision/scripts/setup.py`;
   都找不到就问用户 skill 装在哪个目录。

2. **逐项询问用户**(先运行 `python "<setup.py 路径>" --show` 把当前值打码展示给用户,
   回车表示保留当前值):
   - provider(默认 `dashscope`)
   - api_key(必填;首次配置时提醒去 https://bailian.console.aliyun.com/
     API-KEY 管理页获取)
   - endpoint(默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`)
   - model(默认 `qwen3-vl-plus`)

3. **询问写入位置**并说明风险:
   - 用户级(推荐):`~/.config/vision/config.json`,只影响当前用户,key 不进 git
   - 项目级:`.vision.config.json`,会进 git——⚠️ 公开仓库会泄露 API key,
     选项目级前必须确认仓库是私有的

4. **写入**(替换为实际值,不要在命令里出现未打码的 key 泄露到对话之外的地方):

   ```bash
   python "<setup.py 绝对路径>" --set api_key=<key> [--set model=<model>] [--set endpoint=<endpoint>] [--set provider=<provider>] --target <user|project>
   ```

5. **收尾**:把脚本输出转达给用户(api_key 已打码);提醒验证方式:
   `python "<skill>/scripts/recognize.py" <图片路径或URL>`。
   全程不要在对话中复述完整 api_key。
