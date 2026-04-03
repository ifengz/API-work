# Progress Log

## 2026-04-03

### 15:48
- 初始化 `task_plan.md / findings.md / progress.md`
- 锁定主问题：AI Gateway 选型、职责边界、主推荐路线

### 15:49 - 16:10
- 核实 `one-api`、`new-api`、`LiteLLM` 的公开能力
- 输出研究文档和主结论文档
- 初步确认主路线：`one-api` 做主面板，`LiteLLM` 承接 `Vertex / Gemini`

### 16:48
- 用户收口最终范围：只做 AI Gateway，不展开历史扩展项和业务系统接入
- 新增执行编组：多 worker 并行收口文档，另设监工检查边界，再做全局 reviewer 复查进度
- 补建 `lessons.md`，把后续推进规则固定下来

### 17:28
- 新增 `site-gateway` 纯 Python 标准库服务，支持 `/healthz`、`/v1/resolve`、`/v1/chat/completions`、`/v1/images/generations`
- 新增部署骨架：`Dockerfile`、`docker-compose.yml`、`.env.example`、`README.md`
- 新增示例配置和生成脚本：`config/gateway.example.json`、`config/vertex-pool.example.json`、`config/litellm.example.yaml`、`scripts/build_litellm_config.py`
- 生成运行时配置：`config/gateway.json`、`config/vertex-pool.json`、`config/litellm.generated.yaml`
- 完成离线验证：
  - `python3 scripts/check_project.py`
  - `python3 -m unittest discover -s tests`
  - `python3 scripts/build_litellm_config.py --input config/vertex-pool.json --output config/litellm.generated.yaml`
  - `python3 -m compileall src scripts`
- 当前环境没有 `docker` 命令，Docker 实机启动无法在这里验证

## 2026-04-04

### 01:00 - 02:00
- 核实 `One-API` 渠道接口：
  - 创建渠道：`POST /api/channel/`
  - 测试渠道：`GET /api/channel/test/:id?model=...`
  - 登录：`POST /api/user/login`
- 扫描本仓库 `vertex/` 目录，确认共有 `56` 份 JSON，按 `project_id + client_email` 去重后是 `28` 条有效服务账号
- 新增 `scripts/import_vertex_channels.py`，支持：
  - 按 `project_id + client_email` 去重
  - 指定默认 Vertex 模型清单
  - 批量创建 `VertexAI` 渠道
  - 创建后自动跑连通测试
- 新增 `tests/test_vertex_import.py`
- 用真实线上 `One-API` 跑样本导入：
  - 已成功创建 `vertex-nodal-rex-492217-r2-01` 渠道
  - 测试 `gemini-2.5-flash` 时返回 `adaptor not found`
  - 说明当前线上 `One-API v0.6.11-preview.7` 的后端 Vertex adaptor 没真正可用，不能继续盲目批量导
