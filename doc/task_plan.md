# Task Plan - AI Gateway 实施编排

## 目标
把 AI Gateway 的主路线收口成可直接执行的实施计划，只围绕下面这套组合推进：

```text
one-api = 主面板 + 统一入口
LiteLLM = Vertex / Gemini 执行层
```

## 已确认范围
1. 必接：
   - `Vertex`
   - `Gemini`
   - `ChatGPT`
   - `Claude`
   - `MiniMax`
   - `GLM`
   - `Qwen`
   - `DeepSeek`
   - `Moonshot`
2. 必要能力：
   - 负载均衡
   - 失败自动重试
   - fallback
   - `/images`
   - 面板
   - 用户管理
   - 令牌管理
   - 渠道管理
   - token / 额度消耗查看
   - 多站点规则
3. 当前不做：
   - 历史扩展项
   - 业务系统接入

## 多代理执行编组

| 角色 | 职责 | 只碰什么 | 顺序 |
| --- | --- | --- | --- |
| Worker 1 | 收口计划和约束 | `task_plan.md`、`lessons.md` | 第 1 步 |
| Worker 2 | 收口研究结论和进度 | `findings.md`、`progress.md` | 第 1 步 |
| Worker 3 | 收口主方案文档 | `API_GATEWAY_DECISION.md` | 第 1 步 |
| 监工 | 只读检查边界、顺序、一致性 | 不写文件 | 第 2 步 |
| Global Reviewer | 复查全局进度和缺口 | 不写或只给审查意见 | 第 3 步 |

## GSD 执行任务

<task type="auto">
  <name>文档范围收口</name>
  <files>task_plan.md, findings.md, progress.md, API_GATEWAY_DECISION.md, lessons.md</files>
  <action>删除旧范围里与历史扩展项、业务系统接入有关的内容，只保留 AI Gateway 当前主线</action>
  <verify>全部核心文档只围绕 AI Gateway 主线，且角色编组明确</verify>
  <done>主线范围稳定，不会越做越偏</done>
</task>

<task type="auto">
  <name>控制层实施拆解</name>
  <files>API_GATEWAY_DECISION.md</files>
  <action>明确 one-api 负责的面板、用户、令牌、渠道、额度和统一入口职责</action>
  <verify>文档能直接回答 one-api 在第一阶段到底做什么</verify>
  <done>控制层职责清楚</done>
</task>

<task type="auto">
  <name>执行层实施拆解</name>
  <files>API_GATEWAY_DECISION.md</files>
  <action>明确 LiteLLM 只承接 Vertex / Gemini，并承接对应的重试、fallback、负载均衡能力</action>
  <verify>文档能直接回答 LiteLLM 为什么存在、只做什么、不做什么</verify>
  <done>执行层职责清楚</done>
</task>

<task type="auto">
  <name>多站点规则拆解</name>
  <files>API_GATEWAY_DECISION.md, findings.md</files>
  <action>把多站点规则收口为单独的轻定制层：`site_token -> group/channel/model policy`</action>
  <verify>文档里对多站点规则有单独定义，不和渠道名、模型名硬绑死</verify>
  <done>多站点策略边界清楚</done>
</task>

<task type="checkpoint">
  <name>全局复核</name>
  <files>task_plan.md, findings.md, progress.md, API_GATEWAY_DECISION.md</files>
  <action>检查主结论、能力映射、阶段顺序、角色分工是否一致</action>
  <verify>不存在范围冲突、阶段倒置或职责重叠</verify>
  <done>文档可直接进入实施</done>
</task>

## 阶段状态
- [x] 阶段 1: 路线拍板
- [x] 阶段 2: 范围收口
- [x] 阶段 3: 控制层实施拆解
- [x] 阶段 4: 执行层实施拆解
- [x] 阶段 5: 多站点规则拆解
- [x] 阶段 6: 全局复核

## 2026-04-04 临时收口

| 目标 | 文件 | 动作 | 验证 | 完成标准 |
| --- | --- | --- | --- | --- |
| Vertex 主执行回切 LiteLLM | `scripts/build_litellm_config.py` | 支持 deployment 直接写 `project_id / location`，不再强依赖 `PRIMARY / SECONDARY env` | `tests/test_build_litellm_config.py` 通过 | 多项目多 JSON 能直接生成 LiteLLM YAML |
| 批量吃 `vertex/` 目录 | `scripts/build_vertex_pool_from_dir.py` | 扫描、去重、复制 JSON、生成 `config/vertex-pool.json` | `tests/test_vertex_pool_builder.py` 通过 | 用户只给目录就能生成池配置 |
| 默认模型切到用户指定清单 | `config/*.json`, `README.md` | 把 Gemini 3/3.1/2.5/2.0 清单写成默认导入模型 | 自检 + 文档核对 | 新生成配置默认就是这批模型 |

## 2026-04-04 多站点生图站统一改造计划

| 目标 | 文件 | 动作 | 验证 | 完成标准 |
| --- | --- | --- | --- | --- |
| 对外鉴权统一 | `config/gateway.json`, `README.md` | 统一按站点发 `site_token`，不再给业务站点暴露 Vertex / Gemini 原生密钥 | 站点 token 可单独解析并命中站点策略 | 外部只认 `api-work` 地址和站点 token |
| 站点能力统一 | `config/gateway.json` | 每个生图站只开放两类能力：`分析`、`生图`；模型白名单单独配置 | `site-gateway /v1/resolve` 能正确返回默认分析 / 默认生图模型 | 每个站点都能独立限制模型范围 |
| 客户端接入统一 | 外部业务站代码库 | 删除 Gemini API Key、Vertex JSON、本地 Vertex backend 入口，只保留 `apiWorkBaseUrl + siteToken + analysisModel + imageModel` | 前端不再出现原始 Gemini / Vertex 配置入口 | 所有站点接入面一致 |
| 多站点迁移模板化 | `README.md`, 站点改造计划文档 | 固化一套可复制到 7-8 个站点的迁移模板、验收清单、回滚条件 | 任取一个新站点都能按同一模板执行 | 后续站点不需要重新设计方案 |

## 2026-04-04 image.usfan.net 样板站改造计划

| 阶段 | 文件 | 动作 | 验证 | 完成标准 |
| --- | --- | --- | --- | --- |
| 1. 配置模型命名统一 | `/Users/ifengz/CodingCase/image.usfan.net/src/constants/geminiModels.ts`, `/Users/ifengz/CodingCase/image.usfan.net/src/utils/providerSelector.ts` | 把前端模型名从 `models/gemini-*` 统一成 `gemini-*`，与 `api-work` 白名单一致 | 分析/生图模型值与 `gateway.json` 允许值逐项一致 | 模型名不再需要运行时猜测或转换 |
| 2. 配置结构收口 | `/Users/ifengz/CodingCase/image.usfan.net/src/types/providers.ts`, `/Users/ifengz/CodingCase/image.usfan.net/src/providers/index.ts` | 删掉 Gemini 原生 key、Vertex transport、Vertex credentials、Vertex location，只保留 `siteToken / analysisModel / imageModel` | localStorage 不再出现 `gemini_api_key`、`gemini_image_transport`、`gemini_vertex_*` | 网站配置只剩 `api-work` 相关字段 |
| 3. 配置 UI 收口 | `/Users/ifengz/CodingCase/image.usfan.net/src/components/GeminiConfigDialog.tsx`, `/Users/ifengz/CodingCase/image.usfan.net/src/components/Panels/ConfigModal.tsx` | 去掉多厂商卡片和 Gemini 专属直连配置，改成单入口“API Work 配置”；只保留 1 个 key 输入框，模型下拉放高级设置折叠区 | 页面不再出现厂商卡片、Vertex JSON 上传、本地 backend 提示 | 用户默认只需要填 1 个 key |
| 4. 请求出口统一 | `/Users/ifengz/CodingCase/image.usfan.net/src/utils/api.ts` | 分析固定走 `api-work /v1/chat/completions`，生图固定走 `api-work /v1/images/generations`；请求头统一 `Authorization: Bearer <siteToken>` | 浏览器网络面板里不再出现 Google / Vertex 直连请求 | 唯一上游变成 `api-work` |
| 5. 状态逻辑去旧化 | `/Users/ifengz/CodingCase/image.usfan.net/src/hooks/useAppState.ts`, `/Users/ifengz/CodingCase/image.usfan.net/src/utils/providerUtils.ts` | 删除对 `imageTransport`、`vertexCredentialsMeta`、本地 key manager 的依赖，只保留 `siteToken` 是否存在判断 | 页面不再提示用户配置 Gemini 原始密钥 | 运行时逻辑只依赖 `api-work` |
| 6. 旧链路下线 | `/Users/ifengz/CodingCase/image.usfan.net/src/providers/gemini.ts`, `/Users/ifengz/CodingCase/image.usfan.net/src/utils/geminiVertexApi.ts`, `/Users/ifengz/CodingCase/image.usfan.net/api/proxy.ts`, `/Users/ifengz/CodingCase/image.usfan.net/server/index.mjs` | 先断引用，再确认删除或归档旧 Gemini/Vertex 直连链路 | 全局搜索确认无引用 | 后续 7-8 个站点可直接复制新模板 |
| 7. 样板站验收 | 样板站运行环境 | 验默认分析、指定分析、默认生图、指定生图四次调用都通过 `api-work` | 四次请求全部成功，且命中站点 token 白名单 | 可沉淀成多站点模板 |

## 统一 UI 决策

| 项目 | 决定 |
| --- | --- |
| 原 Gemini/Vertex key 配置 | 全删 |
| 厂商选择 | 不保留 |
| API Work key 输入框 | 保留，且默认唯一必填 |
| 分析模型下拉 | 保留，但放高级设置 |
| 生图模型下拉 | 保留，但放高级设置 |
| 默认行为 | 用户只填 key，不选模型也能直接跑 |

## 2026-04-04 线上 8080 修复执行单

<task type="checkpoint">
  <name>锁定线上旧网关症状</name>
  <files>README.md, scripts/deploy-production.sh, docker-compose.yml, src/site_gateway/server.py</files>
  <action>确认 api-work.usfan.net:8080 当前健康检查可用，但 OPTIONS 仍返回 501，说明线上还没切到当前仓库这版 site-gateway</action>
  <verify>curl GET /healthz 返回 200；curl OPTIONS /v1/chat/completions 返回 501</verify>
  <done>明确问题在部署面，不再误判成前端问题</done>
</task>

<task type="auto">
  <name>锁定 site_token 真值文件</name>
  <files>config/gateway.json, src/site_gateway/config.py, src/site_gateway/server.py</files>
  <action>确认真实 token 必须写入 config/gateway.json 的 sites[].site_token，并绑定 image.usfan.net 到 allowed_origins</action>
  <verify>本地 config/gateway.json 不含用户给的 sk token；代码按 self.sites[site_token] 精确匹配</verify>
  <done>明确第 2 步只能改服务器本地 config/gateway.json</done>
</task>

<task type="checkpoint">
  <name>确认当前阻塞</name>
  <files>README.md, scripts/deploy-production.env.example</files>
  <action>确认标准生产入口是服务器 /www/wwwroot/API-work 上执行 deploy-production.sh；当前终端无法 SSH 进入 api-work.usfan.net，因此不能直接完成线上部署和 token 落地</action>
  <verify>ssh root@api-work.usfan.net 与 ssh api-work.usfan.net 都返回 Permission denied (password)</verify>
  <done>停止猜测式部署，等待用户提供可登录入口或自行在服务器执行命令</done>
</task>

## 2026-04-05 线上 8080 打通结果

<task type="checkpoint">
  <name>公网浏览器准入恢复</name>
  <files>src/site_gateway/server.py, config/gateway.json</files>
  <action>把线上 `site-gateway` 切到支持 `OPTIONS` 的新代码，并把服务器 `gateway.json` 升级到新 schema</action>
  <verify>`GET /healthz` 返回 `200`；`OPTIONS /v1/chat/completions` 返回 `204`，且允许 `Authorization, Content-Type, X-Client-Trace-Id`</verify>
  <done>`8080` 已恢复浏览器正式入口</done>
</task>

<task type="checkpoint">
  <name>站点 token 落地</name>
  <files>config/gateway.json</files>
  <action>把用户给的 `sk-bCP...` 配成站点 `image-usfan`，并绑定 `https://image.usfan.net`</action>
  <verify>容器内 `load_gateway_config('/app/config/gateway.json').get_site(token)` 返回 `image-usfan`</verify>
  <done>共享站点 key 已被线上网关识别</done>
</task>

<task type="checkpoint">
  <name>chat/image 外部验收</name>
  <files>IMAGE_USFAN_API_WORK_REFACTOR_REVIEW.md, config/gateway.json</files>
  <action>按一期公网合同复验 `chat` 和 `image`；正式 `POST` 必须带合法 UUIDv7 `X-Client-Trace-Id`，image 模型名必须命中白名单或走默认模型</action>
  <verify>`POST /v1/chat/completions` 返回 `200`；`POST /v1/images/generations` 在默认模型和 `gemini-2.5-flash-image` 两种情况下都返回 `200`</verify>
  <done>其他项目已可按合同接入 `api-work.usfan.net:8080`</done>
</task>

## 2026-04-05 审计记录最小改动执行单

<task type="checkpoint">
  <name>锁定唯一记账落点</name>
  <files>src/site_gateway/server.py, src/site_gateway/upstream.py, config/gateway.json</files>
  <action>确认审计必须落在 `site-gateway`，不能再依赖 `One-API` 面板补记，也不改变 `gemini-*` 现有上游路由</action>
  <verify>方案文档明确写清“记录层”和“转发层”分离；`gemini-2.5-flash-image` 仍保持 `litellm` 路由</verify>
  <done>不再把“记账”误解成“改路由”</done>
</task>

<task type="auto">
  <name>新增独立审计模块</name>
  <files>src/site_gateway/audit.py, src/site_gateway/server.py</files>
  <action>新增独立 `audit.py`，封装 SQLite 初始化、插入、查询；`server.py` 只负责调用，不内嵌 SQL 细节</action>
  <verify>审计能力有单独文件；`server.py` 不新增一坨数据库细节和嵌套分支</verify>
  <done>审计与转发物理隔离</done>
</task>

<task type="auto">
  <name>补齐请求完成即落账</name>
  <files>src/site_gateway/server.py, src/site_gateway/upstream.py</files>
  <action>在请求收口点统一记录成功和失败两类结果，最少包含 `trace_id / site / kind / model / upstream / status / duration_ms / error_code`</action>
  <verify>成功请求落一条；`TOKEN_INVALID`、`MODEL_NOT_ALLOWED`、`UPSTREAM_UNAVAILABLE` 等失败也各落一条</verify>
  <done>排障和对账都有真记录</done>
</task>

<task type="auto">
  <name>补持久化与查询入口</name>
  <files>docker-compose.yml, .env.example, scripts/read_audit.py</files>
  <action>给 `site-gateway` 增加独立数据目录和审计库路径配置，并补一个最小读取脚本，支持按日期或站点筛选</action>
  <verify>容器重启后记录不丢；命令行可读最近 N 条或指定站点记录</verify>
  <done>审计能留存，也能被查到</done>
</task>

<task type="auto">
  <name>补分钟级与维度汇总</name>
  <files>src/site_gateway/audit.py, scripts/read_audit.py</files>
  <action>以原始请求事件表为真值，补每分钟请求数、站点请求数、站点 token 请求数、模型请求数、成功失败数等聚合查询；总量也由同一张表直接统计</action>
  <verify>命令行可输出“最近 60 分钟每分钟请求数”和“按站点/令牌/模型汇总”的结果，且总数与原始事件数一致</verify>
  <done>分钟级和累计统计都能稳定复算</done>
</task>

<task type="checkpoint">
  <name>锁定用户身份与 token 用量边界</name>
  <files>src/site_gateway/server.py, src/site_gateway/upstream.py, doc/findings.md</files>
  <action>只把现有链路里真的有的数据纳入统计：`site_token` 级“谁”可直接做；最终用户级“谁”必须等待调用方补稳定身份字段；`chat usage` 可尝试解析，`image token usage` 没合同就不做假值</action>
  <verify>方案文档明确写出哪些字段立即可做，哪些字段等待新协议</verify>
  <done>统计口径不再含糊</done>
</task>

<task type="tdd">
  <name>用测试锁住审计合同</name>
  <files>tests/test_site_gateway_audit.py, tests/test_site_gateway_contract.py</files>
  <action>先补失败用例，再实现；重点锁成功写入、失败写入、敏感字段不入库、重启后可读</action>
  <verify>`python3 -m unittest discover -s tests` 通过，且新增测试覆盖成功/失败两条主线</verify>
  <done>后续再改网关也不容易把审计搞丢</done>
</task>

<task type="checkpoint">
  <name>等待用户确认实现</name>
  <files>doc/task_issue.md, doc/findings.md, doc/task_plan.md</files>
  <action>本轮只输出第一性原理结论和执行安排，不直接改运行代码；待用户明确回复 `Yes` 后进入实现</action>
  <verify>文档已收口，代码未改动</verify>
  <done>避免未经授权直接做架构变更</done>
</task>
