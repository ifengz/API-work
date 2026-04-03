# Findings - AI Gateway 当前结论

## 当前已知约束
1. `Vertex` 是硬要求，不能降级。
2. 需要同时兼容：
   - `Gemini`
   - `ChatGPT`
   - `Claude`
   - `MiniMax`
   - `GLM`
   - `Qwen`
   - `DeepSeek`
   - `Moonshot`
3. 需要同时满足：
   - 负载均衡
   - 失败自动重试
   - fallback
   - `/images`
   - 面板
   - 用户、令牌、渠道管理
   - token / 额度消耗查看
   - 多站点规则
4. 当前范围只做 AI Gateway，本轮不展开业务系统接入。

## 本次判断原则
1. 只保留一个主面板。
2. 不让两层同时抢同一类调度职责。
3. `Vertex / Gemini` 单独交给执行层。
4. 多站点规则单独抽成轻定制层，不写死在渠道名里。

## 当前结论
1. `one-api` 适合做主面板、统一入口、用户/令牌/渠道/额度管理。
2. `LiteLLM` 适合只承接 `Vertex / Gemini` 执行层。
3. 负载均衡、自动重试、fallback 的职责要分层，不要让两层同时接管同一条链路。
4. `/images` 可以保留在网关能力矩阵里，但最终以实际渠道能力为准。
5. 多站点规则需要补一层 `site_token -> group/channel/model policy` 映射。

## 2026-04-04 新收口
1. `One-API` 原生 `VertexAI` 渠道一条渠道只能吃一份 JSON，不能在同一条渠道里塞多份服务账号。
2. 如果用户要“前端批量导入多个 Vertex JSON”，当前最短路径不是改 `One-API` 原生前端，而是补一个批量导入工具去调用 `One-API` 管理 API。
3. `vertex/` 目录里的 JSON 按 `project_id + client_email` 去重后共有 `28` 条有效服务账号，可直接用于批量建渠道。
4. 真实线上样本测试已经证明：当前服务器上的 `One-API v0.6.11-preview.7` 能创建 `VertexAI` 渠道，但在测试连通时返回 `adaptor not found`，所以后端 Vertex adaptor 当前不可用。
