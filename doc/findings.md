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

## 2026-04-04 多站点生图站收口
1. 对外发给业务站的 key 不应该是“全局万能 key”，而应该是每站点独立 `site_token`。
2. 一个 `site_token` 能否使用全部模型，不取决于 token 本身，而取决于 `config/gateway.json` 里该站点的 `allowed_models`。
3. 站点不传 `model` 时，`site-gateway` 会自动回落到该站点的 `default_chat_model` 或 `default_image_model`。
4. 对生图站来说，接入层只需要保留两类能力：
   - `分析` -> `/v1/chat/completions`
   - `生图` -> `/v1/images/generations`
5. 业务站里继续保留 `Gemini API Key / Vertex JSON / 本地 Vertex backend` 会造成多入口并存，后续 7-8 个站点无法安全复制，必须收口成唯一上游 `api-work`。
6. `image.usfan.net` 当前 Gemini 常量里模型名仍是 `models/gemini-*`，但 `api-work` / `site-gateway` 使用的是 `gemini-*`。模型命名不统一是当前迁移里的硬阻塞，必须先统一映射，不能直接替换请求出口。
7. `image.usfan.net` 当前配置面板是“多厂商卡片 + Gemini 专属配置弹窗”结构；如果本轮目标是所有生图站统一走 `api-work`，这个多厂商 UI 也应该一起收掉，改成单入口配置。

## 2026-04-04 线上 8080 / token 真相
1. `api-work.usfan.net:8080` 当前不是仓库里的新网关行为：`GET /healthz` 返回 `200`，但 `OPTIONS /v1/chat/completions` 返回 `501 Unsupported method ('OPTIONS')`。
2. 当前线上 `8080` 至少还没切到实现了 `do_OPTIONS` 的这版 `site-gateway`，所以浏览器预检在正式入口上仍然过不去。
3. 真实 `site_token` 的真值文件就是 `config/gateway.json`，不是前端、不是 `.env`。
4. `Authorization: Bearer <token>` 进来后，服务会把 `<token>` 直接拿去做 `self.sites[site_token]` 精确匹配；没配进 `sites[]` 就会报 `unknown site token`。
5. 本地真实配置 `config/gateway.json` 目前只有 `site-demo-a` 和 `site-demo-b`，没有用户给的 `sk-bCP...`。
6. 站点 token 识别通过后，还会继续校验 `Origin` 是否属于该站点的 `allowed_origins`，所以 token 和 origin 必须同时绑定 `https://image.usfan.net`。
7. 仓库给出的标准生产入口是服务器 `/www/wwwroot/API-work` 运行 `bash scripts/deploy-production.sh`，本地直接修代码并不能自动改线上。
8. 当前终端无法 SSH 登录 `root@api-work.usfan.net` 或 `ifengz@api-work.usfan.net`，都停在密码认证，说明线上部署和真实 token 落地现在被权限卡住。

## 2026-04-05 宝塔线上排障新增发现
1. 服务器仓库当前提交 `78b0b1f`，落后于 `origin/main` 的 `713ed6e`。
2. 服务器工作区是脏的，但脏改动集中在 `tests/*` 删除和未跟踪 `vertex/`；`site-gateway` 关键源码文件本身不脏。
3. 直接 `docker compose up -d --build site-gateway` 会被 Docker Hub 网络超时卡住，失败点是解析 `python:3.12-slim` 元数据。
4. 服务器本地已有 `api-work-site-gateway:latest` 旧镜像，但没有独立的 `python:3.12-slim` 基础镜像缓存。
5. 以旧镜像为基础镜像做本地 hotfix 构建是可行的，`site-gateway` 容器已能重新拉起。
6. 新网关容器真正起不来的根因不是代码，而是服务器本地 `config/gateway.json` 仍是旧结构；新代码启动后直接报：`ConfigError: missing site 'demo-a' allowed_origins`。
7. 这说明第 1 步和第 2 步在现场是串起来的：先切新代码，再把 `config/gateway.json` 升级成新 schema，并把用户给的 `sk-...` 写进 `sites[].site_token`，服务才可能真正恢复。
8. 经过宝塔线上修复后，公网 `http://api-work.usfan.net:8080/healthz` 已恢复 `200`，`OPTIONS /v1/chat/completions` 已恢复 `204`，说明浏览器准入层已打通。
9. 用户给的 `sk-bCP...` 现在已经能命中 `image-usfan` 站点；容器内 `load_gateway_config('/app/config/gateway.json').get_site(token)` 返回 `image-usfan`。
10. 公网 `POST` 第一次仍失败，不是 token 问题，而是调用没带 `X-Client-Trace-Id`；这和一期合同一致，缺合法 UUIDv7 trace 会返回 `400 BAD_REQUEST`。
11. 按一期合同补上合法 trace 后，公网 `POST /v1/chat/completions` 已真实返回 `200`。
12. 公网 `POST /v1/images/generations` 也已真实返回 `200`，但要么不传 `model` 走默认生图模型，要么显式传白名单里的 `gemini-2.5-flash-image`；传 `gemini-2.5-flash-image-preview` 会被正确拒绝成 `403 MODEL_NOT_ALLOWED`。

## 2026-04-05 审计记录方案的第一性原理
1. 现在“没记录”不是丢单，而是记账层放错了地方：生图默认走 `site-gateway -> litellm`，没经过 `One-API` 面板统计链路。
2. 真正能同时看见“站点 token、请求类型、请求模型、上游去向、返回状态、trace id”的唯一位置，是 `site-gateway`。
3. 记账如果继续依赖 `One-API`，就得改路由；这会改变现有生产链路，不是最小改动。
4. 记账如果放在业务站前端，会丢失上游真实状态，也不可信。
5. 所以最小且正确的落点只能是：`site-gateway` 自己落一份独立审计。

## 2026-04-05 最小改动结论
1. 审计与转发必须物理隔离，新建 `src/site_gateway/audit.py`，不把记录逻辑继续塞进 `server.py`。
2. 存储优先选 `SQLite`，不是因为“高级”，而是它已经是系统内建能力，既比纯文本稳，又不需要再引入外部服务。
3. 审计表只记必要字段：`created_at`、`trace_id`、`site_name`、`request_kind`、`request_model`、`upstream_name`、`upstream_model`、`status_code`、`duration_ms`、`error_code`。
4. 禁止把 `Authorization`、prompt、base64 图片、上游原始响应体写进审计表；这些要么敏感，要么没必要。
5. 写审计必须是“请求结束即落一条”，不管成功失败都要记；否则最需要排障的时候反而没有记录。
6. 查询先做最小能力：命令行读取脚本或只读接口二选一；不先做大面板。

## 2026-04-05 新增统计需求收口
1. “每分钟多少请求、总请求多少、哪个模型打了多少次、哪个 token 打了多少次”都不该单独再造一份账，这些都应该从同一张原始审计表聚合出来。
2. 真正的源数据应该是不可变的“单次请求事件”；分钟统计、模型统计、站点统计都只是查询视图或汇总结果。
3. “谁请求了多少”这句话现在有歧义：
   - 如果“谁”指 `site_token` 或站点名，现有链路能准确记录。
   - 如果“谁”指业务站最终用户，当前协议里没有稳定用户标识，不能瞎猜，也不能拿 IP 冒充用户。
4. “用了多少 token”也有硬边界：
   - `chat` 类请求通常可以从上游响应里的 `usage` 提取。
   - `images` 类请求当前代码链路没有任何 `usage` 合同，除非上游真实返回，否则只能准确记录“请求次数 / 图片张数”，不能伪造 token 消耗。
5. 所以最小正确方案是两层：
   - 第一层：先把所有请求事件原样记全。
   - 第二层：对能精确聚合的维度出报表；拿不到真值的维度明确留空，不做假统计。

## 2026-04-05 并发问题的第一性原理
1. `vertex/` 目录里新增很多 JSON，只会增加可分流的 deployment 数量，不会自动增加 LiteLLM 的 worker 数量。
2. 入口层 `site-gateway` 已经能并发接请求；用户体感“像串行”时，先看执行层 worker，再看单模型 `rpm`，不是先怀疑前端。
3. 当前最短修补路径不是改模型路由，也不是重做负载均衡策略，而是先把 LiteLLM 的 `--num_workers` 从 `1` 提到 `4`。
4. `4` 只是先把执行层从单工变成多工；它不会绕过每个 deployment 自己的 `rpm` 限制，所以这是“并发开关”，不是“无限吞吐”。

## 2026-04-05 默认模型顺序链的第一性原理
1. 站点 key 只能决定“命中哪个站点配置”，不能天然代表“固定走某个 Gemini 新模型”。
2. 当前系统原本只有“显式 `model` 优先，否则回落到单个默认模型”这一级规则；`allowed_models` 的排列顺序本身不带优先级语义。
3. 如果要按固定顺序试多个模型，必须把顺序本身写成配置真值，不能继续依赖前端习惯或 LiteLLM 内部默认行为。
4. 跨模型回退和尝试日志必须落在同一层；否则会出现 `site-gateway` 说模型 A 成功、实际上是 LiteLLM 在内部把请求切到了模型 B 的假日志。
5. 所以这轮正确收口是：`site-gateway` 负责 chat/image 默认候选链、顺序回退、尝试日志和审计；LiteLLM 只负责这些模型真的可用和同模型别名池负载分发。

## 2026-04-05 Gemini 多模态 chat 兼容新发现
1. 用户已用同一 `site_token` 和同一 `/v1/chat/completions` 证明：纯文字 `chat` 返回 `200`，而 `text + image_url` 返回 `503`；锅不在前端 prompt，不在页面字段数量，而在 `api-work` 后端多模态上游链。
2. Vertex 官方 OpenAI 兼容口支持 `messages[].content[].image_url.url = data:image/...` 这类输入；因此“前端把图塞进 `image_url`”本身不构成硬错误。
3. 当前前端固定带 `image_url.detail = "high"`；这类细节字段并不是 Vertex 这条兼容口的稳定合同，应在网关层清洗掉，不能原样赌上游全都认。
4. 所以本轮最小正确修法不是改 prompt，也不是回滚前端，而是：`site-gateway` 在 Gemini 多模态 `chat` 转发前清洗 `image_url.detail`，并把输入图数量打印进尝试日志，先把兼容层和排障真相补齐。

## 2026-04-07 线上 chat 仍 403 的新增根因
1. 线上 `8080` 活着，不代表 `chat` 真能用；公网真测仍然是 `403/UPSTREAM_UNAVAILABLE`，说明坏点在 `site-gateway -> litellm -> Vertex` 这条执行链，不在入口存活。
2. `config/gateway.json`、`config/vertex-pool.json`、`config/litellm.generated.yaml` 都被 `.gitignore` 排除，服务器 `git pull` 不会自动更新这三份运行时真值。
3. `scripts/deploy-production.sh` 当前会按服务器本地 `vertex/` 目录重新生成池配置；如果不显式给项目白名单，坏项目会在每次部署时再次被卷回运行池。
4. 宝塔现场已经证明：把 `ninth-generator-479604-s6` 排除出池后，运行时配置和容器日志仍可能失配；这说明“人工现场临时改文件”不够稳，必须把筛选条件变成受 Git 管的部署输入。
5. 当前 One-API 路径也不能接这个锅：线上真测表明 `one-api` 对这批 Gemini chat 模型缺 `model ratio / adaptor`，所以 Gemini chat 不能再靠 `multimodal_chat_upstream=one_api` 兜底。
6. 本轮正确收口是两件事：
   - Gemini chat（含多模态）默认都只走 `litellm`
   - Vertex 项目白名单进入仓库，并由部署脚本默认读取，避免下次上线再把坏项目卷回来
