# AI Gateway Skeleton

这套骨架直接按你已经拍板的路线落地：

```text
site-gateway -> one-api / LiteLLM
one-api      -> 主面板 + 统一入口
LiteLLM      -> Vertex / Gemini 执行层
```

## 最短落地步骤

1. 复制环境变量文件。

```bash
cp .env.example .env
```

2. 准备运行时配置。

```bash
cp config/gateway.example.json config/gateway.json
cp config/vertex-pool.example.json config/vertex-pool.json
python3 scripts/build_litellm_config.py \
  --input config/vertex-pool.json \
  --output config/litellm.generated.yaml
```

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
2. 复制模板：

```bash
cp scripts/deploy-production.env.example scripts/deploy-production.env
cp .env.example .env
cp config/gateway.example.json config/gateway.json
cp config/vertex-pool.example.json config/vertex-pool.json
```

3. 先在服务器本地预演：

```bash
DRY_RUN=1 ALLOW_DIRTY=1 bash scripts/deploy-production.sh
```

4. 宝塔 webhook / 钩子执行命令：

```bash
bash /www/wwwroot/API-work/scripts/deploy-production.sh
```

5. GitHub webhook 只监听 `main` 的 `push`，指向宝塔 webhook 地址。

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
