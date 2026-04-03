# one-api 研究笔记

## 定位
`one-api` 是一个把多家模型统一成 OpenAI 风格入口的网关，强项是中文场景、渠道管理、令牌管理、用户配额、后台面板。

## 能解决的点

| 需求 | 结论 | 说明 |
| --- | --- | --- |
| `Gemini / ChatGPT / Claude / MiniMax / GLM / Moonshot / Qwen / DeepSeek` | 支持 | README 明确列出这些模型或厂商 |
| `Vertex` | 支持 | README 本身没把 Vertex 写成一级卖点，但发布记录里明确提到 `Vertex AI` |
| 负载均衡 | 支持 | README 明写支持通过负载均衡访问多个渠道 |
| 失败自动重试 | 支持 | README 明写支持失败自动重试 |
| `/images` | 支持 | README 明写支持绘图接口 |
| 面板 | 支持 | 自带完整 Web 面板 |
| 用户管理 | 支持 | README 明写支持多种用户登录注册方式和用户管理 |
| 令牌管理 | 支持 | README 明写支持令牌管理 |
| 渠道管理 | 支持 | README 明写支持渠道管理、批量创建渠道 |
| token / 额度消耗查看 | 支持 | README 明写支持查看额度明细 |
| 多站点规则 | 可做 | 可以用分组、模型限制、管理 API 去扩，但不是现成“站点配置中心” |
| 宝塔部署 | 支持 | README 明写宝塔应用商店一键部署 |

## 对你最关键的硬点

### 1. 多模型覆盖非常全
README 直接列出了这些模型或厂商：
- OpenAI / Azure OpenAI
- Anthropic Claude
- Google PaLM2 / Gemini
- 通义千问
- 智谱 ChatGLM
- Moonshot
- MiniMax
- DeepSeek
- 火山引擎豆包
- 百度文心
- 腾讯混元
- 零一万物
- StepFun

这点很重要，因为你不是只要 `Vertex`，你还要一堆国内模型 key 一起管。

### 2. Vertex 有明确公开证据
这轮查到的公开证据里：
- `one-api` README 已经明确支持 `Google PaLM2/Gemini`
- `one-api` 发布记录里明确提到：
  - `v0.6.8`：`claude and gemini in vertex ai`、`vertexai support proxy url`
  - `v0.6.9`：`Vertex AI gemini-1.5-pro-002 / gemini-1.5-flash-002`

这说明它不是“理论上也许能接”，而是仓库公开记录里确实加过这条能力。

### 3. 可以把 LiteLLM 接在后面
README 明写：
- 支持“其他 OpenAI API 格式下游渠道”
- 支持管理 API 扩展

这意味着你可以把 `LiteLLM` 暴露成 OpenAI 兼容上游，再由 `one-api` 把它当渠道接入。

## 明显缺口

| 缺口 | 影响 |
| --- | --- |
| 没看到现成“多份 Vertex JSON 凭证池网页化管理” | 你要的 `Vertex JSON 池` 还得自己补 |
| “多站点规则”不是现成一级对象 | 需要你自己定义 `site / app / tenant` 这层映射 |
| Vertex 虽有公开证据，但不是整个项目最核心卖点 | 如果 Vertex 是绝对核心执行核，最好还是让更专门的执行层承担 |

## 结论
`one-api` 很适合做你的**主面板 / 主控制层**。  
如果只选一个项目来承担“面板、用户、令牌、渠道、额度、国内模型兼容”，它比 `new-api` 和 `LiteLLM` 更贴你的场景。

## 来源
- https://github.com/songquanpeng/one-api
- https://github.com/songquanpeng/one-api/releases
