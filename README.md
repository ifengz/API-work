# AI Gateway Skeleton

这套骨架现在按这条线落地：

```text
site-gateway -> one-api / LiteLLM / AI Studio
one-api      -> 主面板 + 统一入口
LiteLLM      -> Vertex 主执行层
AI Studio    -> Gemini Developer API key 执行层
```

## 最短落地步骤

1. 复制环境变量文件。

```bash
cp .env.example .env
```

2. 用 `vertex/` 目录生成运行时 Vertex 配置。

```bash
cp config/gateway.example.json config/gateway.json
python3 scripts/build_vertex_pool_from_dir.py \
  --vertex-dir vertex \
  --output-config config/vertex-pool.json \
  --output-credentials-dir credentials/imported
python3 scripts/build_litellm_config.py \
  --input config/vertex-pool.json \
  --output config/litellm.generated.yaml
```

这一步会做 3 件事：

- 扫描 `vertex/` 目录里的所有服务账号 JSON
- 按 `project_id + client_email` 去重
- 复制有效 JSON 到 `credentials/imported/`，并生成 `config/vertex-pool.json`

3. 做本地自检。

```bash
python3 scripts/check_project.py
python3 -m unittest discover -s tests
```

4. 有 Docker 的机器上启动。

```bash
docker compose up --build
```

## 宝塔 webhook 部署

1. 服务器克隆仓库到固定目录，比如 `/www/wwwroot/API-work`。
2. 复制模板，确保服务器上的 `vertex/` 目录已经放好服务账号 JSON：

```bash
cp scripts/deploy-production.env.example scripts/deploy-production.env
cp .env.example .env
cp config/gateway.example.json config/gateway.json
```

正式部署脚本会自动扫描 `vertex/`，生成 `config/vertex-pool.json` 和 `config/litellm.generated.yaml`。

3. 先在服务器本地预演：

```bash
DRY_RUN=1 ALLOW_DIRTY=1 bash scripts/deploy-production.sh
```

4. 宝塔 webhook / 钩子执行命令：

```bash
bash /www/wwwroot/API-work/scripts/deploy-production.sh
```

5. GitHub webhook 只监听 `main` 的 `push`，指向宝塔 webhook 地址。

## 当前访问入口

| 服务 | 默认外部入口 |
| --- | --- |
| one-api 面板 | `http://api-work.usfan.net:5000` |
| site-gateway 健康检查 | `http://api-work.usfan.net:8080/healthz` |
| LiteLLM | `http://api-work.usfan.net:4000` |

## Api-work Key 后端来源

`Api-work Key` 继续是站点级 `site_token`，前端不直接碰真实上游凭证。

后端现在建议支持两类来源：

- `Vertex JSON`：继续通过 `LiteLLM` 承接
- `AI Studio key`：可直接配置为 `ai_studio` 上游，或后续并入 `LiteLLM`

如果两个站点都暴露同一个公开模型名，但后端来源不同，可以在站点配置里用 `model_route_overrides` 做站点级路由覆盖。这样：

- `site-demo-a` 可以让 `gemini-2.5-flash` 走 `Vertex JSON`
- `site-demo-ai-studio` 可以让 `gemini-2.5-flash` 走 `AI Studio key`

前端拿到的仍然只是各自的 `Api-work Key`。

`allowed_origins` 除了精确 origin，也支持受控后缀，例如 `https://*.usfan.net`。这里仍然不是全开 CORS，网关会继续校验真实请求 `Origin`，并只回显具体来源，不返回裸 `*`。

## Vertex 批量导入

如果你决定把 `Vertex` 主执行放回 `LiteLLM`，这套项目现在推荐直接用 `vertex/` 目录生成池配置，不再走 `One-API` 面板逐条建 `VertexAI` 渠道。

默认模型清单已经固定为：

- `gemini-3-flash-preview`
- `gemini-3.1-pro-preview`
- `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`
- `gemini-3.1-flash-lite-preview`
- `gemini-2.5-flash-image`
- `gemini-2.5-pro`
- `gemini-pro-latest`
- `gemini-flash-latest`
- `gemini-flash-lite-latest`
- `gemini-2.5-flash`
- `gemini-2.5-flash-lite`
- `gemini-2.0-flash`
- `gemini-2.0-flash-lite`

生成脚本会按 `project_id + client_email` 去重，也就是：

- 同一服务账号导出的重复 JSON 只保留一份
- 同一项目下不同服务账号会各生成一条 LiteLLM deployment
- 默认 `Region` 用 `global`

先看计划会吃到哪些 JSON：

```bash
python3 scripts/build_vertex_pool_from_dir.py \
  --vertex-dir vertex \
  --output-config config/vertex-pool.json \
  --output-credentials-dir credentials/imported \
  --max-per-project 2
```

再生成 LiteLLM YAML：

```bash
python3 scripts/build_litellm_config.py \
  --input config/vertex-pool.json \
  --output config/litellm.generated.yaml
```

如果你只想先吃指定项目：

```bash
python3 scripts/build_vertex_pool_from_dir.py \
  --vertex-dir vertex \
  --projects nodal-rex-492217-r2,newwoo1 \
  --output-config config/vertex-pool.json \
  --output-credentials-dir credentials/imported
```

## 目录

| 路径 | 作用 |
| --- | --- |
| `src/site_gateway/` | 站点规则服务，按 `site_token + model` 决定走 `one-api` 还是 `LiteLLM` |
| `tests/` | 规则和上游请求构造测试 |
| `config/gateway.example.json` | 站点规则、模型路由、上游地址示例 |
| `config/vertex-pool.example.json` | Vertex 凭证池元数据示例 |
| `config/litellm.example.yaml` | LiteLLM 执行层示例配置 |
| `scripts/build_litellm_config.py` | 从 Vertex 凭证池 JSON 生成 LiteLLM YAML |
| `scripts/check_project.py` | 自检关键文件、JSON、YAML 关键段落 |
| `docker-compose.yml` | `site-gateway + one-api + LiteLLM` 编排 |

## 这套骨架做了什么

| 能力 | 位置 |
| --- | --- |
| 多站点规则 | `site-gateway` |
| `Vertex / Gemini` 分层 | `site-gateway + LiteLLM` |
| 其他模型直连 | `site-gateway + one-api` |
| 失败自动重试 / fallback / 负载均衡 | LiteLLM 配置示例 |
| 面板、用户、令牌、渠道、额度 | `one-api` |
| `/images` | `site-gateway` 转发到 `LiteLLM` 或 `one-api` |

## 当前边界

这次只做 AI Gateway 本体，不把其他业务系统混进来。
