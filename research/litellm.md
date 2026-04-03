# LiteLLM 研究笔记

## 定位
`LiteLLM` 是统一执行层，不是最适合直接给运营同学当主后台的面板系统。它最强的是：
- 统一调用 100+ LLM
- `VertexAI`
- 路由 / fallback / retry / load balancing
- virtual keys
- spend tracking
- AI Gateway

## 能解决的点

| 需求 | 结论 | 说明 |
| --- | --- | --- |
| `Vertex` | 强支持 | README 和 provider 列表明确有 `Google - Vertex AI (vertex_ai)` |
| `Gemini` | 支持 | README 和 provider 列表明确有 `Google AI Studio - Gemini` |
| `ChatGPT / Claude` | 支持 | README 明确支持 OpenAI、Anthropic |
| `DeepSeek` | 支持 | provider 列表明确有 `Deepseek` |
| `Qwen` | 可接 | provider 里有 `dashscope`，这条就是阿里云模型入口 |
| `GLM / MiniMax / Mimo` | 视厂商接口 | 可以通过 `custom` / `custom_openai` 接 OpenAI 兼容上游，但不是每个都在 README 一级名单里直写 |
| 负载均衡 | 强支持 | README 明写 Router、load balancing |
| 失败自动重试 | 强支持 | README 明写 retry / fallback logic |
| fallback | 强支持 | README 明写 routing / fallback |
| `/images` | 支持 | README 的 supported endpoints 明写 `/images`，provider 表也标出多家支持 |
| 虚拟 key | 支持 | README 明写 virtual keys |
| token / 成本消耗 | 支持 | README 明写 spend management per project/user |
| 后台面板 | 有，但不是你的最佳主面板 | README 明写 admin dashboard UI，但它更偏平台团队和运维视角 |

## 对你最关键的点

### 1. Vertex 是它的强项，不是顺手带的
README 直接把 `VertexAI` 放在“100+ LLMs”支持列表里，provider 表里也有：
- `Google - Vertex AI (vertex_ai)`
- `Google AI Studio - Gemini (gemini)`

而且 `vertex_ai` 在表里明确支持：
- `/chat/completions`
- `/messages`
- `/responses`
- `/embeddings`
- `/image/generations`

### 2. 执行层能力比 one-api/new-api 更硬
README 明写的执行层能力包括：
- AI Gateway
- virtual keys
- spend management per project/user
- Router with retry/fallback logic
- application-level load balancing

这正好命中你要的：
- 负载均衡
- 失败自动重试
- fallback
- `/images`

## 明显缺口

| 缺口 | 影响 |
| --- | --- |
| 不适合直接当你唯一面板 | 用户、渠道、国内运营习惯、细粒度后台流程不如 one-api 贴你的场景 |
| 多份 Vertex JSON 池网页化管理不是现成卖点 | 你想要的“多 JSON 文件池管理”还得自己补 |
| 某些企业级管理特性分层较多 | 不适合直接替代 one-api 这种中文网关后台 |

## 结论
`LiteLLM` 很适合做你的**Vertex / Gemini 专用执行层**，不适合独自承担全部“面板 + 渠道 + 用户 + 业务规则”。

## 来源
- https://github.com/BerriAI/litellm
- https://docs.litellm.ai/docs/providers
- https://docs.litellm.ai/docs/simple_proxy
