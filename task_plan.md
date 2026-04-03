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
