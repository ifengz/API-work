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
