# new-api 研究笔记

## 定位
`new-api` 是在 `one-api` 基础上继续演化出来的新一代网关，强项是更现代的 UI、数据仪表盘、计费能力、文档更整齐。

## 能解决的点

| 需求 | 结论 | 说明 |
| --- | --- | --- |
| 面板 | 支持 | README 明写现代 UI |
| 用户 / 权限 / token 分组 | 支持 | README 明写 token grouping、model restrictions、user management |
| 渠道管理 | 支持 | 文档有完整 channel management |
| 负载均衡 | 支持 | README 明写 channel weighted random |
| 失败自动重试 | 支持 | README 明写 automatic retry on failure |
| `/images` | 支持 | README 明写 image interface |
| 统计与仪表盘 | 支持 | README 明写 data dashboard |
| 宝塔部署 | 支持 | README 明写 BaoTa 一键安装 |
| 自定义完整调用地址 | 支持 | README 明写 `Custom` supports complete call address |
| 计费 / key 用量查询 | 支持 | README 明写 pay-per-use、key quota query usage |

## 优点

| 点 | 说明 |
| --- | --- |
| UI 更现代 | 对运营侧和管理侧更友好 |
| 文档更系统 | 官方文档、管理 API、安装说明更规整 |
| 和 one-api 数据兼容 | README 明写 fully compatible with the original One API database |
| 自定义上游更灵活 | `Custom` 通道可填完整调用地址，理论上也能接 `LiteLLM` |

## 关键问题

| 问题 | 结论 |
| --- | --- |
| 公开资料里对 `Vertex` 的说明够不够硬 | 不够 |
| 为什么 | 这轮查到的 README 和官方文档里，`Gemini`、`Google Gemini` 说得清楚，但没看到像 `one-api` 发布记录那样对 `Vertex AI` 的明确强调 |
| 结果 | 如果你是“100% 要 Vertex”，`new-api` 不适合做唯一押注 |

## 结论
`new-api` 是一个很强的候选，但**不适合当你这次唯一拍板方案**。  
不是因为它差，而是因为你这次的硬约束是 `Vertex`，而这轮公开证据里，`new-api` 对 `Vertex` 的说明不如 `one-api + LiteLLM` 这条组合硬。

## 来源
- https://github.com/QuantumNous/new-api
- https://docs.newapi.pro/en/docs
