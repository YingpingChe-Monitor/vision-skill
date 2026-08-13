# 03 — 图片输入形式：URL 与剪贴板粘贴

**What to build:** 扩展图片输入来源：除本地文件路径外，支持 http(s) 网络图片 URL，以及剪贴板粘贴的 base64 data URI。三种输入形式统一走同一条识别流程，输出格式一致。

**Blocked by:** 01 — Vision skill 骨架：配置 + 阿里云百炼 Qwen-VL 视觉识别

**Status:** ready-for-human

- [x] 给定网络图片 URL 能完成识别
- [x] 给定粘贴的 base64 data URI 能完成识别
- [x] 本地路径、URL、base64 三种输入输出格式一致，用户无感知差异

## Comments

2025-08-13 — 已实现（`scripts/recognize.py` 的 `prepare_image_content`）：

- 自动识别三种输入：`http(s)://` → URL 直传；`data:` → data URI 直传；其余按本地文件读取
  （magic bytes 检测 PNG/JPEG/GIF/WebP/BMP，生成 base64 data URI）。
- 三者走同一识别流程、同一输出；E2E 测试（本地 mock 服务器）逐一验证并通过。

待人工验收：真实网络图片 URL（须公网可达）与真实 key 的线上识别。
