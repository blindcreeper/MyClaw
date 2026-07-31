# MyClaw 项目面试分析报告

> 面向 AI 应用实习岗位的简历核心项目深度剖析
> 分析日期：2026-07-31 ｜ 分析范围：`D:\sxxm\Myclaw` 全量源码 + 上游 CyberClaw 对比

---

## 〇、项目一句话定位（电梯陈述）

**MyClaw 是一个基于 LangChain/LangGraph 的透明可控 AI 智能体系统：在复刻 CyberClaw 的"CLI 本地智能体内核"（ReAct 图 + SQLite 检查点 + 三层记忆 + 沙箱工具 + 懒加载技能）基础上，自主设计并实现了 FastAPI 后端服务，通过 NapCat（OneBot v11 协议）反向 WebSocket 接入 QQ，把单机 CLI Agent 升级为支持多用户、多会话隔离的云端 QQ 机器人，并配套 Vue3 实时监控管理面板。**

30 秒版本："我把一个只能在本地终端跑的 AI Agent 框架，扩展成了部署在云服务器上、能被多个 QQ 用户同时使用的智能体后端，前端还做了一个实时监控面板，可以实时看到 AI 的每一步决策和工具调用。"

---

## 一、与上游 CyberClaw 的差异（你的原创贡献边界）

面试第一关一定是"哪些是别人的、哪些是你做的"。边界必须背熟：

| 维度 | CyberClaw（上游） | MyClaw（你的增量） |
|---|---|---|
| 交互形态 | 仅本地终端 CLI（`run` / `monitor` 命令） | **新增 FastAPI 服务端**，QQ 多用户并发接入 |
| 部署形态 | 单机本地进程 | **云服务器 `0.0.0.0:9910` 单端口对外**，NapCat 反向连入，穿透 NAT |
| 会话模型 | 单一固定 thread_id（`local_geek_master`） | **SessionManager 多用户会话隔离**：私聊 `qq_{uid}`、群聊 `qq_{uid}_g{gid}` |
| 监控方式 | 本地 `tail -f` 终端面板 | **SSE 日志流 API + Vue3 Web 监控面板**（跨用户、跨会话实时聚合） |
| 消息类型 | 纯文本 | **多模态**：QQ 图片自动下载转 base64，拼 OpenAI `image_url` 消息块 |
| 前端 | 无 | **Vue3 + TS + Vite 管理面板**（Dashboard / 实时监控 / 技能管理三视图） |
| QQ 业务逻辑 | 无 | 群聊 @ 检测（CQ 码数组/文本双格式）、好友请求自动通过+欢迎语、**模拟打字的流式分片回复** |
| 复用部分 | LangGraph 图、三层记忆、技能加载、沙箱工具、审计日志、心跳 | 原样复用并适配（`create_agent_app()` 一套大脑，两种躯壳） |

**核心叙事**：上游解决的是"AI 行为透明可控"（单机视角），你解决的是"把透明可控的 Agent 变成多人可用的在线服务"（工程化视角）——从单机架构到 C/S 架构的完整升级。

---

## 二、项目亮点梳理

### 2.1 架构设计亮点

**① 一套 Agent 大脑，两种运行躯壳（内核复用架构）**
- `myclaw/core/agent.py` 的 `create_agent_app()` 同时服务 CLI（`entry/main.py`）和 QQ Server（`myclaw/server/`），共享同一个 `AsyncSqliteSaver` 检查点库，仅靠 `thread_id` 命名空间隔离（`local_geek_master` vs `qq_*`），互不污染。
- 亮点话术："新增后端时没有 fork 一套逻辑，而是把 Agent 内核抽象成可复用单元，Server 只是新的 I/O 适配层——类似 Hexagonal Architecture 里端口与适配器的思想。"

**② 反向 WebSocket 的事件驱动接入（云端部署的关键决策）**
- NapCat 作为 WS **客户端**主动连 `ws://云服务器:9910/ws/onebot` 推事件，服务端用 httpx 调 NapCat HTTP API 回发消息。
- 为什么反向？NapCat 常跑在 NAT/家庭网络后没有公网 IP，正向 Webhook 根本不可达；反向 WS 让服务端只需一个公网端口，QQ 侧零网络要求。
- 事件即发即忘：`asyncio.create_task(_dispatch(event))` 并发分发，不阻塞 WS 接收循环。

**③ 三层记忆架构（面试最有分量的 AI 工程点）**
| 层级 | 载体 | 机制 | 解决的问题 |
|---|---|---|---|
| 短期记忆 | `AgentState.messages` + SQLite checkpoint | 超 40 回合按"整回合"裁剪保留最近 10 回合 | 上下文不爆 token |
| 中期记忆 | `AgentState.summary` 滚动摘要 | 被裁回合交给 LLM 压缩成 ≤150 字摘要，随 checkpoint 持久化，注入系统 Prompt | 长对话不丢任务进展 |
| 长期记忆 | `memory/user_profile_{qq}.md` | Agent 自主调用 `save_user_profile` 维护用户画像 | 跨会话记住用户偏好 |
- 精妙处：**用 Prompt 明确分工**——摘要 Prompt 写死"只记任务进展，不记静态偏好；画像不管任务进度"，避免两类记忆互相污染。
- 裁剪按"用户回合"而非消息条数：一个回合（HumanMessage → AIMessage → tool_calls → ToolMessage）整体保留或丢弃，**绝不会截断 tool_call 对**（这是 LangChain 常见 bug 源，说明你踩过坑）。

**④ 技能系统的渐进式披露（Progressive Disclosure）**
- 扫描 `skills/` 目录时只读每个 `skill.md` 前 50 行提取 name/description 元数据注入工具列表；模型先调 `mode=help` 看说明书（截断 3000 字），确认后再 `mode=run` 执行。
- 收益：N 个技能只占 N 行元数据的 token，而非 N 份全文；技能天然热插拔（`(path, mtime)` LRU 缓存 + 60 秒扫描缓存）。
- 上游数据佐证：两阶段调用让 P0 事故率从 50% 降到 10%（可引用作为设计依据）。

**⑤ 沙箱纵深防御**
- 代码层：路径前缀校验（`startswith(base_dir)` 拦截 `../` 越权）+ 5 条 Shell 黑名单正则（拦截绝对路径、`~`、盘符跳转）+ 60s 超时熔断 + stdout/stderr 各 2000 字截断；
- Prompt 层：系统 Prompt 里写"SANDBOX PROTOCOL 最高安全指令"双层防护；
- 文件读取 10000 字截断防 token 爆炸。

### 2.2 后端工程亮点

**⑥ 多用户会话隔离与生命周期管理**（`session.py`）
- 全局共享一个编译好的 LangGraph App + 一个 SQLite 连接（省资源），靠 thread_id 隔离；
- 私聊共享上下文、群聊按"用户×群"二维隔离——同一个人在不同群里是独立的 AI 记忆；
- 懒加载（首条消息到达才建库连表）+ `cleanup_expired(1h)` 清理内存对象（历史仍在 SQLite，下次自动恢复）+ `asyncio.Lock` 保护会话表。

**⑦ 异步审计日志管道**（`logger.py` → SSE → 前端）
- 单例 `JSONLEventLogger`：内存队列缓冲 + daemon 后台线程落盘 + `atexit` 排空，日志 I/O 不阻塞 Agent 主循环；
- 按 thread_id 分文件且文件名过滤非法字符防路径注入；
- SSE 端点做增量推送：`last_positions` 字典跟踪每个文件偏移量、处理文件轮转、自动发现新文件、`X-Accel-Buffering: no` 为 Nginx 反代做准备。

**⑧ QQ 侧体验细节（最能体现"做过真实产品"的点）**
- **模拟打字分片回复**：缓冲到 50 字 / 遇换行 / 距上次发送超 1.5s 就 flush 一片，长回复像真人在打字，且用户能尽早看到开头；
- 工具调用进度提示：`🔧 正在执行: xxx...`，等待不焦虑；
- 群聊 @ 双格式检测（CQ 数组 + `[CQ:at,qq=]` 文本）、CQ 码 str/list 双兼容——都是跟真实 NapCat 数据磨出来的兼容代码；
- 全程无输出兜底发"✅ 处理完成"、异常发"⚠️ 发生错误"——永不沉默。

**⑨ `contextvars` 传递用户身份**
- 多用户并发下用 `ContextVar current_user_id` 在异步任务间传递 QQ 号，保证 `save_user_profile` 写入不串用户——这是 Python 异步并发下传递隐式上下文的标准解法。

### 2.3 前端工程亮点

**⑩ 极简依赖的自研面板**：仅 vue 3.5 + vue-router 两个运行时依赖，零 UI 框架（手写 CSS 设计令牌）、零状态库（composables + 根组件状态提升 + props 透传）、零 HTTP 库（fetch 泛型封装）。
- 话术："管理面板是低频内部工具，引入 Element Plus 的成本大于收益，所以用手写设计令牌保证视觉一致性，同时证明我不依赖脚手架。"

**⑪ SSE 选型正确**：日志监控是单向推送场景，EventSource 相比 WebSocket 零协议成本、浏览器原生自动重连；`useSSE` composable 做了环形缓冲（最多 500 条防内存膨胀）+ 批量 flush（减少响应式触发）。

**⑫ 工程闭环**：`build = vue-tsc --noEmit && vite build`（类型不过则构建失败）；路由级代码分割懒加载；Hash 路由 + FastAPI StaticFiles 托管 `dist`——前后端同源同端口，免 CORS、免 Nginx，开发环境用 Vite proxy 抹平差异；MonitorView 的智能自动滚动（上翻暂停跟随、回底 40px 恢复、浮出"回到底部"气泡）。

---

## 三、面试可谈点（按话题组织，每个都给出"故事线"）

### 话题 A：技术选型理由

| 选型 | 理由（可展开讲） |
|---|---|
| LangGraph 而非裸写循环 | 需要**状态持久化与人类可审计**：checkpointer 自动把每次状态迁移快照存 SQLite，重启恢复对话；`tools_condition`/`ToolNode` 预置 ReAct 循环，比手写 while 循环少造轮子且图结构可视化 |
| OneBot v11 + NapCat 而非 QQ 官方开放平台 | 官方 botpy 需要企业/个人开发者审核且能力受限（被动消息、无主动私聊）；NapCat 基于 NTQQ，能力完整（收发消息、好友管理、群管理），OneBot 是社区标准协议，生态成熟 |
| 反向 WS 而非 Webhook | NapCat 可能无公网 IP（NAT 后），反向连接只需服务端一个端口；且 WS 长连接天然低延迟 |
| SQLite 而非 Redis/Postgres | 单服务嵌入式部署零依赖；LangGraph 官方 `AsyncSqliteSaver` 开箱即用；57MB/488 checkpoint 实测无瓶颈；面试可主动谈"如果 QPS 上来，我会迁移到 Postgres checkpointer，接口不变" |
| JSONL 而非 ELK | 审计日志追加写、按会话分文件，tail/SSE 直读即可，无需引入重型日志栈；结构化 JSON 后续可无缝导入任何分析系统 |
| SSE 而非 WebSocket | 监控是单向推送；EventSource 自动重连、可穿 HTTP 代理、实现 30 行 vs 300 行 |
| Vue3 而非 React | 团队/个人熟悉度 + 面板规模小，Composition API + composables 足够；`vue-tsc` 构建期类型门禁 |
| OpenAI 兼容协议统一多厂商 | `provider.py` 工厂把阿里/智谱/腾讯/DeepSeek 都归一到 `ChatOpenAI`，只换 base_url 和 key——一个适配器吃掉 7 家厂商 |

### 话题 B：核心模块设计（可画架构图讲）

```
QQ 用户 ──NTQQ── NapCat ──反向WS(OneBot v11)──▶ FastAPI /ws/onebot
                                                    │ ws_handler: 并发分发
                                                    ▼
                                            SessionManager（thread_id 隔离）
                                                    ▼
                              LangGraph ReAct 图（agent ⇄ tools 双节点）
                                 │        │         │
                       上下文裁剪+摘要   12内置工具   懒加载技能(help/run)
                                 │        │         │
                          SQLite checkpoint    沙箱(office/)
                                                    │
            审计旁路：JSONL logger ──▶ SSE /api/monitor/stream ──▶ Vue3 面板
```

讲的时候强调三条独立线索：**主链路（消息进→决策→回复出）**、**记忆链路（checkpoint + 摘要 + 画像）**、**审计链路（日志 → SSE → 面板）**，三条链路解耦，审计不影响主链路性能。

### 话题 C：数据流处理

- 入站：WS 文本帧 → JSON 解析 → Pydantic 模型校验 → CQ 码提取（文本+图片）→ 内部 `QQMessage` 防腐层（屏蔽 OneBot 协议细节，未来换协议不改业务）
- 多模态：图片 URL → httpx 下载 → base64 data URL → OpenAI `image_url` 块
- 出站：`app.astream(stream_mode="updates")` 流式消费图状态 → 分片缓冲（50字/换行/1.5s）→ httpx POST NapCat HTTP API
- 审计：每次 LLM 输入/工具调用/工具结果/AI 回复异步落 JSONL

### 话题 D：性能优化（已做的 + 可谈的演进）

已做：异步日志（队列+后台线程）、即发即忘事件分发、技能元数据懒加载 + 双缓存、日志环形缓冲 + 批量渲染、前端路由懒加载、共享单例 App/DB 连接。
可谈演进：多用户并发下同 thread 串行化（每会话一把锁）、LLM 调用加超时与重试（tenacity）、checkpoint 库定期归档、摘要压缩改异步、WS 端点加鉴权、水平扩展时用 Redis 做会话亲和。

### 话题 E：部署架构

- 单端口 `0.0.0.0:9910` 同时承载：静态前端（StaticFiles）、REST API、SSE、OneBot WS——云服务器极简部署；
- `python -m myclaw.server --port 9910` 一条命令起服务，lifespan 统一管理初始化/资源释放；
- 预留 `X-Accel-Buffering: no` 表明考虑过 Nginx 反代；CORS 目前全开（自承开发态，部署需收紧——主动说显得诚实）。

---

## 四、预判面试官提问（附应答策略）

### 4.1 项目真实性与个人贡献类（必问）

**Q1：这个项目有多少是你自己写的？**
> 上游 CyberClaw 提供了 CLI 智能体内核（LangGraph 图、记忆、沙箱、技能），我复刻并吃透了这部分；**`myclaw/server/` 全部 9 个文件（FastAPI 应用、OneBot WS 处理器、SessionManager、鉴权、SSE 监控路由）和 `web-admin/` 全部 14 个前端文件是我独立设计实现的**。可以现场指出任意文件讲实现细节。

**Q2：为什么不做官方 QQ 机器人而选 NapCat？**
> 官方开放平台对被动消息/主动消息限制大、需要资质审核；NapCat+OneBot 是社区事实标准，能力完整。同时我清楚这是灰色方案，所以架构上把协议细节隔离在 `ws_handler` 和 `QQMessage` 防腐层后面——如果未来迁官方平台，只换适配层，Agent 内核零改动。（把缺点变成架构亮点）

**Q3：有没有真实用户用过？**
> 有，数据库里有 6 个真实 thread（含 2 个群聊会话），用户画像文件里记录了真实用户的称呼偏好（如"早早睡觉"），审计日志有真实的 tool_call 记录。可以展示日志样例。

### 4.2 AI/LLM 技术类

**Q4：上下文窗口怎么处理？token 爆了怎么办？**
> 三层机制：①按"用户回合"整体裁剪（40 回合触发、保留 10 回合），保证 tool_call 对不被截断；②被裁部分让 LLM 压缩成 ≤150 字滚动摘要注入系统 Prompt；③工具输出全部截断（文件 1 万字、shell 输出 2 千字）。为什么按回合不按条数？因为 AIMessage 的 tool_calls 和后续 ToolMessage 是绑定的，从中间截断会导致 API 报错——这是实际踩过的坑。

**Q5：摘要是怎么做摘要的？会不会越摘要越偏？**
> 用同一个 LLM，Prompt 明确分工"只记任务进展，不记静态偏好，150 字以内"，静态偏好归长期画像管——双脑分工防止互相污染。漂移问题确实存在，所以摘要随 checkpoint 持久化、可审计，且 150 字硬上限约束信息量。改进方向是关键事实结构化提取而非自由文本。

**Q6：Function Calling 怎么实现的？模型不调工具/乱调工具怎么办？**
> LangChain `bind_tools` 生成 tool schema 随请求发给模型，LangGraph 的 `tools_condition` 判断 AIMessage 是否含 tool_calls 决定走向 tools 节点还是结束。防乱调靠：①工具 docstring 写清使用场景和"Prompt 级风控协议"（如定时任务时间歧义必须追问上下午、模糊删除必须先列清单确认）；②技能强制 help/run 两阶段，先看说明书再执行——上游实测 P0 事故率 50%→10%。

**Q7：多轮对话状态存在哪？重启会丢吗？**
> LangGraph checkpointer（AsyncSqliteSaver），每次状态迁移完整快照进 SQLite，重启后按 thread_id 恢复全部上下文和摘要。这也是选 LangGraph 而不是裸调 API 的核心原因。

**Q8：你的"长期记忆"为什么用 Markdown 而不是向量数据库/RAG？**
> 用户画像是**少量高价值、需要人可读可编辑**的数据，Markdown 整篇注入 Prompt 比向量检索更准、可解释、可审计（符合项目"透明可控"理念）；RAG 适合大规模知识库检索。如果要做知识库问答，我会在技能层加一个向量检索技能而不是替换画像机制——不同问题用不同工具。

### 4.3 后端架构类

**Q9：多用户并发怎么处理？会不会串会话？**
> 三道隔离：①thread_id 命名空间（`qq_{uid}` / `qq_{uid}_g{gid}`）在 checkpointer 层隔离状态；②SessionManager 用 asyncio.Lock 保护会话表；③用户身份用 `contextvars.ContextVar` 在异步调用链传递，写画像不会串用户。**诚实补充**：当前同一用户连发两条会并发驱动同一 thread，存在竞态，改进方案是每 thread 一把 asyncio.Lock 串行化——我知道这个边界。

**Q10：WebSocket 断线怎么办？**
> 入向 WS 由 NapCat 客户端负责重连（OneBot 反向 WS 标准行为，服务端 accept 循环永续）；出向用 HTTP 无状态调用天然无连接问题；前端 SSE 由浏览器 EventSource 原生自动重连。服务端 WS 端点有 try/except 包裹，单连接异常不影响其他连接。

**Q11：为什么审计日志要用异步队列？直接写文件不行吗？**
> 日志写在 Agent 主循环的关键路径上（每次 LLM 调用前后），同步磁盘 I/O 会直接抬高对话延迟；队列+后台 daemon 线程把 I/O 挪出关键路径，`atexit` 保证退出前排空不丢日志。这是"审计链路不影响主链路"的设计原则。

**Q12：SSE 和 WebSocket 怎么选？如果监控要支持"远程叫停 AI"呢？**
> 当前是单向推送场景，SSE 最优。如果需要双向控制（叫停、人工审批工具执行——上游"透明可控"理念的自然延伸），就该换 WebSocket 或在 SSE 之外加 REST 控制端点；vite proxy 里我已经预留了 `/ws` 代理。

### 4.4 安全类（这个项目自带安全话题，大概率被问）

**Q13：让 AI 执行 shell 命令，你怎么保证安全？**
> 纵深防御四层：①沙箱目录限定（路径前缀校验，物理上出不了 `office/`）；②Shell 黑名单正则拦截 `../`、绝对路径、`~`、盘符跳转；③60s 超时熔断 + 输出截断；④系统 Prompt 写明安全红线。**主动坦承局限**：黑名单理论上可被绕过（变量拼接、编码混淆），生产级方案应该是白名单 + 容器隔离（Docker/gVisor）+ 高危操作人工审批——这也是"透明可控"架构里审计日志存在的意义：即使被绕过，所有行为可追溯。

**Q14：你的系统有哪些已知安全缺陷？**（压力题，诚实+改进方案是满分答法）
> 我自己 review 出来的：①`/ws/onebot` 端点无鉴权，任何人连上可注入伪造 QQ 事件——应加 token 校验；②监控 SSE 无鉴权且含完整聊天内容——EventSource 不能带自定义头，方案是 query token 或 session cookie；③管理 Token 有硬编码默认值；④`.env` 明文密钥不该入库；⑤`calculator` 用了 eval（虽是空 builtins 的阉割版，生产应换 `ast.literal_eval` 或 numexpr）。实习项目我优先把架构跑通，这些我都列入了加固清单。

**Q15：Prompt Injection 怎么防？QQ 用户让 AI"忽略之前的指令"怎么办？**
> 现有缓解：系统 Prompt 安全红线声明 + 沙箱物理隔离 + 工具 docstring 风控协议。坦承这是行业未完全解决的问题，纵深防御的思路是假设注入总会成功，靠沙箱边界和审计兜底；可谈的进阶方向是输入侧注入检测、工具调用二次确认（人类在环）。

### 4.5 Bug 与复盘类（展示 Code Review 能力，建议主动讲）

**Q16：项目中遇到过最难的 bug？/ 你自己发现过什么问题？**
> 主动讲这三个，含金量递增：
> 1. **心跳字段名 bug**：`heartbeat.py` 读 `t["time"]` 但写入方用 `target_time`，KeyError 被 `except: pass` 吞掉，定时任务永远不触发——教训：裸异常吞没是最危险的反模式，且跨模块的 dict schema 应该用 TypedDict/Pydantic 约束；
> 2. **Server 模式心跳缺失**：`pacemaker_loop` 只在 CLI 入口启动，QQ 模式下定时任务不触发——教训：两个入口共享内核但生命周期管理不一致，应该提到 lifespan 统一装配；
> 3. **前端暂停功能失效**：`useSSE` 的 1 秒兜底 flush 没检查 paused 状态——教训：setInterval 兜底逻辑必须参与状态判断。
> 收尾话术："这些是我复盘时自己发现的，也都清楚修法——我觉得能讲清楚自己系统的缺陷，比假装它完美更有价值。"（这句话非常加分）

### 4.6 场景设计类（考察演进思维）

**Q17：如果用户量涨到 1000 个 QQ 群，架构要怎么改？**
> 瓶颈分析：单机单事件循环 + SQLite 写入竞争 + 全量消息内存分发。演进路径：①会话状态迁 Postgres checkpointer（LangGraph 官方支持，接口不变）；②WS 接入层与 Agent 工作层分离，中间加消息队列（Redis Streams/NATS），Agent worker 水平扩多实例；③会话亲和路由（thread_id 哈希）；④LLM 调用加并发限流和令牌桶；⑤审计日志改批量投递到 ClickHouse/Loki。

**Q18：如果要支持微信/飞书/Discord，怎么改？**
> 架构上已预留：`QQMessage` 内部标准消息就是防腐层，新增平台只需写一个适配器（平台事件 → 标准消息 + 标准回复 → 平台 API），SessionManager 的 thread 命名加平台前缀即可。这正是把协议细节隔离在 `ws_handler` 的回报。

**Q19：如果让你加一个人工审批高危操作的功能，怎么做？**
> LangGraph 原生支持 `interrupt`：在 tools 节点前设中断点，高危工具（shell 执行、文件写）触发中断 → 通过审计 SSE 推送到管理面板 → 面板加审批按钮调 REST 端点 → 携带批准结果 resume 图执行。管理面板正好已有实时推送通道，改动面可控。（这题展示你对 LangGraph 高级特性的了解）

**Q20：Agent 的耗时大头在哪？怎么优化响应速度？**
> 大头是 LLM 往返次数（ReAct 每轮一次调用，工具链 N 轮）。优化：①分片回复已让用户尽早看到内容（感知延迟优化）；②skill help/run 两阶段本身减少无效工具调用；③可谈方向：流式输出 LLM token（当前是节点级流式）、简单意图走小模型分类直答、工具结果缓存（天气等幂等查询）。

---

## 五、简历描述建议（可直接抄改）

**MyClaw — 云端多用户 AI 智能体系统（Python / LangGraph / FastAPI / Vue3）**
- 在开源项目 CyberClaw 的 CLI 智能体内核基础上，**独立设计并实现 FastAPI 后端**，基于 NapCat（OneBot v11）反向 WebSocket 接入 QQ，将单机 Agent 升级为支持多用户并发的云端机器人服务
- 设计**三层记忆架构**（按回合裁剪 + LLM 滚动摘要 + Markdown 长期画像），实现跨会话个性化且上下文不溢出
- 实现**多租户会话隔离**：thread_id 命名空间 + asyncio 并发控制 + contextvars 用户身份传递，私聊/群聊记忆互不串扰
- 构建**全链路审计系统**：异步 JSONL 日志管道（队列+后台线程）→ SSE 实时推送 → 自研 Vue3+TS 监控面板（环形缓冲/智能滚动/懒加载），AI 每次决策与工具调用实时可见
- 工程细节：技能插件懒加载（help/run 两阶段渐进披露）、沙箱纵深防御（路径校验+命令黑名单+超时熔断）、QQ 侧模拟打字流式分片回复

---

## 六、面试前自查清单

- [ ] 能 30 秒讲清"复刻了什么、新增了后端什么"（背熟第一章表格）
- [ ] 能手画第二章话题 B 的架构图（主链路/记忆链路/审计链路三线）
- [ ] 能现场打开 `ws_handler.py` 讲分片回复逻辑、打开 `session.py` 讲隔离策略
- [ ] 准备好三个"我自己发现的 bug"故事（4.5 节 Q16）
- [ ] 跑通一次演示：`python -m myclaw.server` 起服务 → QQ 发消息 → 面板看实时日志
- [ ] 想清楚被问"为什么不用 XX"时的选型回答（话题 A 表格）

---

*报告基于 2026-07-31 对 `D:\sxxm\Myclaw` 全量源码的静态分析生成。*
