# Task Issue

| 日期 | 任务 | 状态 | 备注 |
| --- | --- | --- | --- |
| 2026-04-05 | 为 `site-gateway` 设计并编排“生图/分析请求审计记录与分钟级汇总”最小改动方案 | 已实现，待验收 | 代码与测试已落地；等待你确认“谁”是否还要细到最终用户后，再决定是否补新请求头契约 |
| 2026-04-05 | 把 LiteLLM 默认 worker 从 `1` 提到 `4`，让现有多 deployment 能真正并发处理 | 已实现，待验收 | 只改运行并发开关，不碰模型路由、不碰审计逻辑；本地 `30 tests OK`，结构自检与 diff 检查已通过 |
| 2026-04-05 | 重启远端 `litellm` 让 `4` 个 worker 生效 | 阻塞 | 本机会话没有 `docker`；SSH 直连 `root@38.246.250.228` 卡在密码认证；当前浏览器执行器 `browser-use/browserbase/chrome-devtools/playwright` 全部 `Transport closed` |
| 2026-04-05 | 为 `site-gateway` 增加 chat/image 有序模型队列、顺序回退与尝试日志 | 已实现，待验收 | 用户指定 chat 5 个模型、生图 3 个模型按顺序尝试；显式模型优先、回退链入审计并打印日志；本地 `36 tests OK`、结构自检和 diff 检查已通过 |
| 2026-04-05 | 核实 Vertex Gemini 生图是否支持参考图随 API 传入，以及当前 `site-gateway` 链路是否真的带过去 | 进行中 | 先核官方合同，再核本仓库 `/v1/images/generations` 转发真值；不做猜测，不先改代码 |
| 2026-04-05 | 为生图链路补“参考图原样上传”能力，并保持原 prompt 与参考图内容不被改写 | 进行中 | 先补失败测试，再只改最小转发层；若还要改默认模型顺序，等用户给出精确顺序后再单独落地 |
| 2026-04-05 | 修复 `api-work` Gemini 多模态 chat 带图分析上游兼容问题，并补输入图日志 | 已实现，待验收 | 已按官方兼容口约束清洗 `image_url.detail`，并补“输入图数量进日志”的合同测试；本地 `38 tests OK`、结构自检和 diff 检查已通过 |
| 2026-04-06 | 推送当前 `api-work` 修复并重启宝塔线上 `site-gateway` | 已实现，待验收 | 已用宝塔终端把服务器本地改动先备份到 `/root/api-work-backup-20260405-173949/`，再 `git stash push -u` 保存为 `stash@{0}: pre-deploy-backup-20260405-173949`；随后已 `git pull --ff-only origin main`、`docker compose up -d --build site-gateway`，本地 `curl -i http://127.0.0.1:8080/healthz` 返回 `HTTP/1.1 200 OK` 与 `{\"status\":\"ok\"}` |
| 2026-04-06 | 线上验证并打通 Gemini 带图分析链路 | 已实现，待验收 | 已先用公网固定入口 `http://api-work.usfan.net:8080/v1/chat/completions` 对 `site-demo-a` 发 `text + image_url + detail:high` 真请求，当前线上仍返回 `503 UPSTREAM_UNAVAILABLE`，坐实故障点在后端多模态 chat 链路；随后已补“Gemini 带图 chat 走显式 `multimodal_chat_upstream=one_api`”的配置与代码，并通过 `python3 -m unittest discover -s tests`（`40 tests OK`）、`python3 scripts/check_project.py`、`git diff --check`，待推送并上线复测。 |
