# 生图项目双入口接入实施说明

## 1. 这份文档解决什么问题

给任意一个生图项目落一套统一入口：

1. `Api-work Key`
2. `三方Key`

目标不是把所有厂商都做成独立入口，而是把前端收口成两条路：

- 走自己的网关，就填 `Api-work Key`
- 走别人的中转站，就填 `三方Key`

这份文档可以直接给别的项目照着改。

## 2. 先记住两个名词

### 2.1 `Api-work Key`

这不是上游厂商 key，它在 `api-work` 里对应的是站点级 `site_token`。

前端只知道这一把钥匙，后端自己决定它最后走哪种真实来源：

- `Vertex JSON`
- `AI Studio key`
- 后续别的内部上游

### 2.2 `三方Key`

这是一条外部账号配置，不归 `api-work` 托管。最小字段只有：

- `Base URL`
- `API Key`
- `Model`

一句大白话：

- `Api-work Key` = 用你自己的门
- `三方Key` = 把别人家的门牌号、钥匙、默认模型记成一张卡片

## 3. `api-work` 这次已经做了什么

本仓库已经补了最小改造，让同一个公开模型名可以按站点走不同上游：

1. `site-gateway` 新增站点级 `model_route_overrides`
2. 示例配置新增 `ai_studio` upstream
3. 示例站点 `site-demo-ai-studio` 可以让：
   - `gemini-2.5-flash` 走 `AI Studio`
   - `imagen-3.0-generate-002` 走 `AI Studio`
4. 原来的 `site_token` 契约不变，前端不用接触 `Vertex JSON`

对应改动文件：

- [src/site_gateway/config.py](/Users/ifengz/CodingCase/API-work/src/site_gateway/config.py)
- [src/site_gateway/policy.py](/Users/ifengz/CodingCase/API-work/src/site_gateway/policy.py)
- [config/gateway.example.json](/Users/ifengz/CodingCase/API-work/config/gateway.example.json)
- [tests/test_site_gateway.py](/Users/ifengz/CodingCase/API-work/tests/test_site_gateway.py)

## 4. 生图项目页面应该长什么样

页面只保留两个入口按钮：

1. `Api-work Key`
2. `三方Key`

不要再摆品牌入口，不要再让用户先学技术栈。

### 4.1 `Api-work Key` 页面

只放一个输入框：

- 标签：`Api-work Key`
- 按钮：`保存并启用`

不要显示这些东西：

- Vertex JSON 上传
- AI Studio key 输入
- provider 下拉
- 模型下拉

### 4.2 `三方Key` 页面

用“账号卡片”做，不用“大表单堆很多 key”。

一张卡片只代表一条配置：

- 名称
- Base URL
- API Key
- Model

同一家如果有两把 key，就让用户保存成两张卡片。用户只做三件事：

1. 新增一张
2. 切换当前使用
3. 编辑这一张

## 5. 数据结构怎么设计才最简单

核心原则只有一句：

`一条配置 = 一个 provider 实例 + 一把 key + 一个默认 model`

建议在生图项目里只维护两类 profile。

### 5.1 `Api-work` profile

```json
{
  "id": "site-main",
  "type": "api_work",
  "label": "主站 Api-work",
  "siteToken": "sk-xxxxx"
}
```

### 5.2 `三方Key` profile

```json
{
  "id": "packy-gemini-a",
  "type": "openai_compatible",
  "label": "Packy Gemini A",
  "baseUrl": "https://www.packyapi.com",
  "apiKey": "sk-xxxxx",
  "model": "gemini-2.5-flash-image",
  "transportMode": "direct",
  "options": {
    "basePathStyle": "auto",
    "customHeaders": {}
  }
}
```

页面状态只需要：

```json
{
  "activeProfileId": "site-main",
  "profiles": []
}
```

## 6. 请求链路怎么分

### 6.1 走 `Api-work Key`

前端固定打你自己的网关：

- `POST /v1/chat/completions`
- `POST /v1/images/generations`

请求头固定：

- `Authorization: Bearer <site_token>`
- `X-Client-Trace-Id: <uuid>`

前端不上传 `Vertex JSON`，也不传真实上游 key。

### 6.2 走 `三方Key`

前端或薄中继按当前卡片去请求外部 OpenAI Compatible / New API 站点。

默认规则：

1. `baseUrl` 去掉结尾 `/`
2. 如果 `baseUrl` 已经以 `/v1` 结尾，就直接拼接口路径
3. 如果没带 `/v1`，默认补 `/v1`
4. 真遇到路径特殊的站，再放进高级设置

不要为了几个特殊站把首页做复杂。

## 7. 兼容更多 `New API` 站点，要靠什么做

不是靠“再加一个入口”，而是靠 `openai_compatible` 这一类 profile 做兼容。

双入口一期默认只需要两种 profile：

1. `api_work`
2. `openai_compatible`

如果后面还有“项目自己直连独立 Vertex broker”的需求，再额外加第三种：

3. `vertex_broker`

这里的 `openai_compatible` 不是说所有站完全一样，而是说先按同一能力模型接：

- base URL
- bearer key
- chat path
- image path
- model
- 可选 header

遇到差异时，只在这一类 profile 上补高级项，不新增品牌入口。

## 8. 什么时候该直连，什么时候该走薄中继

### 8.1 可以直连

满足下面 4 条就可以让浏览器直连：

1. `OPTIONS` 预检能过
2. 允许 `Authorization`
3. 允许 `Content-Type`
4. 不拦浏览器 `Origin`

### 8.2 不该直连

下面任意一条命中，就应该切成“同一个三方Key入口，后端薄中继执行”：

1. 外站 CORS 不放行
2. 需要自定义 header 太多
3. 要隐藏 key，不想暴露到浏览器
4. 要做你自己的幂等、审计、限流

重点是：
对用户来说还是“同一个三方Key入口”，不要因为执行方式不同就多长一个配置入口。

## 9. 并发、切换、中断，这三件事怎么避免出事故

### 9.1 切换配置不能影响正在生成的任务

任务一旦发出，就要把当时的 profile 快照下来：

- profile id
- base URL
- model
- request id

后面用户再切到别的卡片，也只能影响下一次请求。

### 9.2 前端取消不等于上游真的取消

这句话必须写进实现和文案里。

如果供应商没有取消协议，用户点“停止”时，你只能做到：

1. 当前页面停止等待
2. 当前请求标记为本地已取消
3. 提示“上游可能仍在处理”

不要假装真的停掉了外部生成。

### 9.3 防止重复提交

至少做三件事：

1. 生成按钮发出后立即进入 loading
2. 给每次任务生成本地 `client_request_id`
3. 相同素材和相同 profile 的短时间重复提交要明确提示

如果后端能配幂等键，就继续往上加；没有就别装作已经解决。

## 10. 其他生图项目应该怎么改

按这个顺序改，最稳。

### 第 1 步：先抽一个统一的 profile store

目标：把旧的厂商散配置收成一个地方。

至少拆成两个文件：

1. `providerProfiles.ts`
2. `providerProfileStore.ts`

只在这里管理：

- profile 列表
- 当前激活 profile
- 新增/删除/切换

### 第 2 步：把设置页收口成两个入口

目标：页面不再出现品牌卡片。

只保留：

1. `Api-work Key`
2. `三方Key`

高级项收折叠，不抢主界面。

### 第 3 步：抽一个统一请求客户端

建议文件名：

- `apiWorkClient.ts`
- `providerClient.ts`

内部判断：

- 当前 profile 是 `api_work` -> 打你自己的网关
- 当前 profile 是 `openai_compatible` -> 按卡片去请求

业务页面不要自己判断 provider。

### 第 4 步：把任务态独立出来

建议文件名：

- `generationTaskStore.ts`

只管理：

- request id
- running / cancelled / failed / done
- 发起时的 profile snapshot

不要把运行态塞回设置页状态。

### 第 5 步：清掉旧入口依赖

必须去掉这些旧逻辑：

1. Gemini API Key 门禁
2. Vertex JSON 前端上传
3. 厂商独立配置弹窗
4. 页面里散落的 provider 判断

不清干净，后面一定串线。

## 11. 错误提示怎么做人话

只做三类提示就够：

1. `配置不完整`
2. `当前服务不可用`
3. `当前页面已停止等待，上游可能仍在处理`

不要把这些东西吐给用户：

- Python 堆栈
- 上游原始报错体
- key
- JSON
- header

## 12. `api-work` 侧推荐配置方式

如果你要给自己的项目发 `Api-work Key`，后端建议按下面两类来源管理：

### 12.1 Vertex 路线

- `site_token` 继续发给前端
- `Vertex JSON` 留在后端
- 通过 `LiteLLM` 或 broker 承接

### 12.2 AI Studio 路线

- `site_token` 继续发给前端
- `AI_STUDIO_API_KEY` 放环境变量
- 通过 `ai_studio` upstream 承接

如果两个站点都想暴露同一个公开模型名，但后端来源不同，就用站点级 `model_route_overrides`。

## 13. 验收清单

### 13.1 页面验收

1. 设置页只剩两个入口
2. `Api-work Key` 页面只剩一个输入框
3. `三方Key` 页面是卡片列表，不是堆 key 大表单
4. 同一家多把 key 能保存成多张卡片
5. 当前只显示一张激活卡片

### 13.2 链路验收

1. 只填 `Api-work Key` 能分析
2. 只填 `Api-work Key` 能生图
3. 只填 `三方Key` 能分析或生图
4. 切换配置不影响正在进行中的任务
5. 停止等待后，页面状态正确，不假装上游一定已取消

### 13.3 `api-work` 本仓验证

```bash
python3 -m unittest /Users/ifengz/CodingCase/API-work/tests/test_site_gateway.py
python3 -m unittest /Users/ifengz/CodingCase/API-work/tests/test_site_gateway_contract.py
python3 /Users/ifengz/CodingCase/API-work/scripts/check_project.py
git diff --check
```

## 14. 最后收口

以后别再给生图项目加 `1XM`、`Packy`、`EchoFlow` 这种品牌入口了。

产品层只保两条：

1. `Api-work Key`
2. `三方Key`

技术差异全部收进 profile 类型和高级设置里，用户只需要记住“我现在用自己的门，还是用别人的门”。
