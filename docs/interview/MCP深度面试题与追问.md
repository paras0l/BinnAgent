# MCP 深度面试题、参考回答与压力追问

> 目标：基于近期 MCP 官方规范和常见面试追问，建立从协议基础、生命周期、Tools / Resources / Prompts、Transport、授权、安全、工程治理到 BinnAgent 实践的完整回答体系。
>
> 时间基线：2026-07-14。官方站点此时仍将 `2025-11-25` 标为最新稳定规范；`2026-07-28` 是 Release Candidate，包含破坏性变化，尚不能当作稳定规范介绍。

## 1. 面试官真正想判断什么

如果候选人简历上写 MCP，我主要判断：

1. 是否能用一句话准确说明 MCP 解决了什么问题。
2. 是否能区分 Host、Client、Server、Model 和 Tool Runtime。
3. 是否理解 MCP 与 Function Calling、REST、RAG、插件的边界。
4. 是否知道 JSON-RPC、初始化、版本协商和 capability negotiation。
5. 是否分得清 Tools、Resources、Prompts、Elicitation 和 Tasks。
6. 是否理解 stdio 与 Streamable HTTP 的运行和安全差异。
7. 是否真正考虑 OAuth audience、token passthrough、SSRF、DNS rebinding、session hijacking 和 prompt injection。
8. 是否知道协议兼容不等于业务可信，远端 schema 和描述也属于不可信供应链输入。
9. 是否能处理 tool discovery、schema drift、分页、通知、超时、取消和错误分类。
10. 是否能诚实说明项目用了 MCP 的哪一部分，而不是“调用了一个 HTTP API”就称为完整 MCP 平台。

真正深入的回答会同时包含：协议事实、运行机制、信任边界、生产取舍和项目证据。

## 2. 先说明规范版本

截至 2026-07-14：

- 官方规范页仍将 [`2025-11-25`](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) 标为 latest。
- 标准传输是 stdio 和 Streamable HTTP；Streamable HTTP 已取代旧 `HTTP+SSE` transport。
- `2025-11-25` 引入的 Tasks 仍标为 experimental。
- 2026 年已经通过提案准备弃用 Roots、Sampling 和 Logging，但它们仍存在于当前稳定规范。
- [`2026-07-28` Release Candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) 提出了 stateless core、Extensions、Tasks 扩展和授权加固等破坏性变化，最终版尚未到发布日期。

面试中推荐这样说：

> 我会先报清协议版本。下面基础流程按 2025-11-25 稳定规范回答；对于 2026-07-28，我只把它作为候选演进方向，不把 RC 行为说成当前所有客户端都支持。

这句话能避免大量“背了过期博客”的问题。

## 3. 一分钟总回答

> MCP，也就是 Model Context Protocol，是让 AI Host 以标准协议连接外部能力提供方的开放协议。它统一了能力发现、调用、上下文读取、生命周期、传输和授权接口。Server 可以暴露 Tools、Resources 和 Prompts；Host 内的 MCP Client 与每个 Server 建立协议连接，再把合适的能力提供给模型或用户界面。
>
> MCP 不等于 Function Calling。Function Calling 是模型向 Host 表达“想调用哪个函数和参数”；MCP 解决 Host 如何发现并调用外部 Server。典型链路是 MCP Client 先 `tools/list`，Host 按权限筛选后把 schema 绑定给模型，模型生成 tool call，Host 再通过 MCP `tools/call` 执行。
>
> 生产难点不在把工具列出来，而在信任边界：Server 描述、schema 和返回内容都不能天然信任；远程 MCP 要做 OAuth audience、最小 scope 和禁止 token passthrough；本地 stdio server 等同于安装本地软件，需要沙箱和最小权限。Host 还要做 allowlist、审批、输入输出校验、超时、幂等、审计和 prompt injection 防护。

## 4. 核心架构与角色

### Q1：MCP 是什么？解决了什么问题？

#### 高质量回答

> MCP 是 AI 应用连接外部数据与能力的标准协议。过去每个 AI Host 都要为文件系统、GitHub、数据库、日历等写专用集成；MCP 统一了发现、调用和数据交换契约，使一个 Server 可以被不同兼容 Host 使用。

> 它主要降低集成的 M×N 适配成本，但不会自动解决业务授权、工具质量、安全审批和 Agent 规划。

#### 追问：为什么称它为“协议”，不是“框架”？

> 因为它规定参与方、消息、方法、生命周期、传输和语义。Python / TypeScript SDK 只是协议实现；不用官方 SDK也可以实现兼容 Server，但必须遵守 JSON-RPC 和规范要求。

### Q2：Host、Client、Server 分别是什么？

#### 高质量回答

| 角色 | 责任 |
|---|---|
| Host | 面向用户的 AI 应用，管理模型、权限、UI 和多个连接 |
| MCP Client | Host 内的协议参与者，通常对应一个 Server 连接 |
| MCP Server | 暴露 Tools、Resources、Prompts 等能力 |
| Model | 做语义决策，可能选择工具，但不是 MCP transport endpoint |

> 例如桌面 Agent 是 Host；它为文件系统 Server 和 Git Server 分别创建 MCP Client；Server 访问本地文件或 Git API；模型只看到 Host 筛选后的工具 schema。

#### 追问：为什么通常是一个 Client 对一个 Server？

> 这样协议版本、capability、session、授权和故障域更清晰。Host 可以管理多个 Client，但不应把多个 Server 的同名工具直接无命名空间地混在一起。

### Q3：MCP 的分层是什么？

#### 高质量回答

> 官方架构把 MCP 分成 data layer 和 transport layer。Data layer 基于 JSON-RPC 2.0，定义生命周期、Tools、Resources、Prompts、通知等语义；transport layer 定义 stdio、Streamable HTTP 的连接、消息 framing 和相应授权方式。[官方架构说明](https://modelcontextprotocol.io/docs/learn/architecture)

#### 追问：为什么分层重要？

> 同一套 `tools/list` / `tools/call` 语义可以运行在本地 stdio 或远程 HTTP 上，但威胁模型、凭据和部署方式不同。业务代码不应把 transport 细节散落到 tool adapter 中。

### Q4：MCP 与 Function Calling 的区别？

#### 高质量回答

```text
MCP：Host ↔ 外部能力 Server 的发现和调用协议
Function Calling：Model → Host 的结构化行动意图
```

典型组合：

```text
MCP tools/list
→ Host 规范化与权限筛选
→ 把工具 schema 绑定给 Model
→ Model 生成 function/tool call
→ Host policy 校验
→ MCP tools/call
→ Tool result 返回 Model
```

> 模型不需要“会 MCP”。Host 可以把 MCP Tool 转换成任意模型厂商的 Function Calling schema。

#### 追问：不用 LLM 能调用 MCP Tool 吗？

> 可以。UI、定时任务或确定性 workflow 都能直接发 `tools/call`。MCP 规定能力接口，不强制由模型决定调用。

### Q5：MCP 与 REST / OpenAPI 的区别？

#### 高质量回答

> REST / OpenAPI 主要描述 Web API；MCP 是面向 AI Host 的双向协议，包含初始化、能力协商、工具、资源、提示词、通知和交互能力。MCP Server 内部常常仍调用 REST API。

> MCP 不是 REST 的替代品，而是 AI integration adapter。对稳定内部服务，可以保留 REST 作为业务 API，在外面提供薄 MCP Server。

#### 追问：能否自动把所有 OpenAPI endpoint 暴露成 MCP Tool？

> 技术上可以，生产上不应无审核全量暴露。REST schema 往往粒度过细、权限过大、参数不适合模型，还可能暴露管理接口。需要重新做业务工具设计、描述、scope、审批和输出归一化。

### Q6：MCP 与 RAG 的区别？

> RAG 是检索增强生成方法；MCP 是连接协议。RAG 检索器可以暴露为 Tool，也可以把文档暴露成 Resource。使用 MCP 不代表做了 RAG，使用 RAG 也不需要 MCP。

### Q7：MCP 与插件系统有什么区别？

> 插件是产品级安装、权限、分发和生命周期概念；MCP 是协议。一个插件可以包含 MCP Server，也可以只包含 skills、UI 或本地代码。协议兼容不意味着插件可信或可自动安装。

## 5. JSON-RPC 与生命周期

### Q8：MCP 为什么使用 JSON-RPC 2.0？

> JSON-RPC 提供 request、response、notification、method、params、result 和标准 error envelope，既能运行在 stdio，也能运行在 HTTP。它比随意定义 JSON 更利于 ID 关联、双向请求和错误处理。

### Q9：Request、Response、Notification 的区别？

#### 高质量回答

- Request 有 `id`，接收方必须用相同 ID 返回 result 或 error。
- Response 与请求 ID 对应。
- Notification 没有 `id`，发送方不等待响应。

> `notifications/initialized`、`notifications/tools/list_changed` 都是 notification。实现时不能给 notification 返回普通 JSON-RPC response。

#### 追问：并发请求如何关联？

> 通过 JSON-RPC ID，而不是响应顺序。Client 应维护 pending map，并验证 response ID；HTTP 单请求单响应也不应跳过验证，尤其在 SSE 多消息或共享 session 场景。

### Q10：初始化流程是什么？

#### 高质量回答

当前稳定规范的基本流程是：

```text
Client → initialize(protocolVersion, capabilities, clientInfo)
Server → InitializeResult(protocolVersion, capabilities, serverInfo, instructions?)
Client → notifications/initialized
双方进入 operation phase
```

初始化必须是第一段协议交互，完成版本与能力协商后才能使用相应能力。[Lifecycle 规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)

#### 追问：Server 返回不同 protocolVersion 怎么办？

> Client 必须检查能否支持。如果不能，应断开，而不是忽略返回值继续用自己固定版本发送消息。

### Q11：Capability Negotiation 有什么意义？

> 双方只调用对方声明支持的能力。例如 Server 声明 `tools` 才能调用 Tools；`listChanged` 表示它会发送列表变化通知；Client 声明 elicitation 才能接收相关请求。Capability 是运行契约，不是装饰性 metadata。

#### 追问：声明 capability 就代表允许当前用户调用所有工具吗？

> 不代表。Capability 表示协议实现支持，具体 tool availability 仍受用户、scope、tenant 和 policy 控制。

### Q12：如何处理协议版本兼容？

> 保存支持版本集合，初始化时明确协商；HTTP 后续请求携带协商后的 `MCP-Protocol-Version`；对未知版本 fail clearly。Server schema、tool spec 和客户端 adapter 还应有 contract tests。版本兼容与业务工具版本是两层问题。

### Q13：Shutdown 如何做？

> stdio 通常由 Client 关闭输入、等待 Server 退出，必要时终止进程；Streamable HTTP 的 stateful session 可以用 DELETE 结束 session，但 Server 允许返回 405。无论 transport，都要关闭 pending calls、连接和子进程，并处理超时。

## 6. Tools、Resources 与 Prompts

### Q14：Tools、Resources、Prompts 的核心区别？

#### 高质量回答

| Primitive | 主要用途 | 官方典型控制方 | 常见操作 |
|---|---|---|---|
| Tools | 执行动作、查询或计算 | Model-controlled | `tools/list`、`tools/call` |
| Resources | 提供上下文数据 | Application-controlled | `resources/list`、`resources/read` |
| Prompts | 可复用交互模板 | User-controlled | `prompts/list`、`prompts/get` |

官方把 Tools 描述为模型可发现和选择的动作，把 Resources 描述为由 Host 决定如何纳入上下文，把 Prompts 设计为用户显式选择的模板。这是典型交互模式，不是不可改变的 UI 强制规则。[Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)、[Resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)、[Prompts](https://modelcontextprotocol.io/specification/2025-11-25/server/prompts)

### Q15：什么时候把能力设计成 Tool，什么时候设计成 Resource？

> “执行一个带参数的动作并返回结果”更像 Tool；“通过 URI 读取上下文对象”更像 Resource。读取数据库也可以是 Tool，关键是交互语义：是否需要模型构造操作参数、是否有副作用、是否适合订阅和复用 URI。

#### 追问：Resource 一定只读吗？

> Resource primitive 本身用于读取和订阅内容；修改资源通常通过 Tool。这样能把 context selection 与 mutation 权限分离。

### Q16：`tools/list` 返回什么？

> Tool 至少有 name、description 和 inputSchema，还可有 title、icons、outputSchema、annotations 和 execution metadata。列表支持 cursor pagination；Server 声明 `listChanged` 后可发送 `notifications/tools/list_changed`。[Tool 规范](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)

#### 追问：为什么 Tool description 也是安全输入？

> 描述可能被 Host 放入模型上下文，恶意 Server 可以在描述中注入指令或诱导数据外传。Host 应将其视为不可信供应链内容，做 Server allowlist、长度限制、人工审核、hash 和命名空间隔离。

### Q17：Tool inputSchema 和 outputSchema 怎么用？

> Server 用 inputSchema 描述参数并在执行前验证；outputSchema 可约束 structuredContent。规范要求 Server 输出符合自己声明的 output schema，Client 也应再次验证。Schema 是结构契约，不是授权。

#### 追问：没有参数的 Tool 怎么写？

> 推荐 `{ "type": "object", "additionalProperties": false }`，明确只接受空对象，而不是用 null 或完全开放对象。

### Q18：Tool result 支持哪些内容？

> 可以返回 text、image、audio、resource link、embedded resource 和 structuredContent。声明 outputSchema 时，应校验 structuredContent；为兼容旧客户端，稳定规范建议同时提供序列化文本内容。

### Q19：Protocol Error 和 Tool Execution Error 有什么区别？

#### 高质量回答

> 未知 method、malformed JSON-RPC、未知工具等协议问题使用 JSON-RPC error；API 失败、业务拒绝、可修正参数等执行问题通常返回 tool result 并设置 `isError: true`。后者可以提供给模型尝试修正，前者通常不是换参数能解决。[官方错误分类](https://modelcontextprotocol.io/specification/2025-11-25/server/tools#error-handling)

#### 追问：权限拒绝属于哪种？

> 可按实现映射，但不能为了让模型“自修复”暴露绕过权限的方法。无权调用通常应该稳定拒绝，Host 也不应自动重试。

### Q20：Resource 如何唯一标识？

> 使用 URI。可以是 `https://`、`file://`、`git://` 或自定义 scheme。URI 是标识与定位语义，不代表 Host 可以绕过 Server 直接访问真实文件。

### Q21：Resource Template 是什么？

> 它使用 URI Template 暴露参数化资源，例如 `docs://courses/{course_id}/units/{unit_id}`。Client 可列出模板并填入参数，必要时结合 completion。它比为每个可能对象列出一条静态 Resource 更可扩展。

### Q22：Resource subscription 怎么工作？

> Server 声明 `resources.subscribe` 后，Client 可订阅指定 URI；资源变化时 Server 发 `notifications/resources/updated`。通知只说明变化，Client 通常还要重新 read。还需要防止高频通知风暴和越权订阅。

### Q23：Prompts 为什么不是普通 Server 配置文件？

> Prompts 是可发现、可参数化的协议 primitive，Host 可以让用户通过命令或 UI 选择。它们返回结构化 messages，而不是直接在 Server 上调用模型。Host 仍应显示来源并把远端 prompt 当不可信内容。

### Q24：MCP Prompt 能否覆盖 Host system prompt？

> 不应该。Host 决定不同来源消息如何组合，安全和权限规则保持最高优先级。远端 Prompt 是内容输入，不是新的信任根。

## 7. Client Features 与交互能力

### Q25：Sampling 是什么？

> 在当前稳定规范中，Sampling 允许 Server 请求 Client / Host 使用其模型生成内容。这样 Server 不需要持有模型 API key，Host 保留模型选择和用户控制。它是 Server → Client request，与 Server 自己调用 LLM 不同。

#### 追问：为什么 Sampling 有安全风险？

> Server 可能诱导 Host 带入过多上下文、消耗预算或调用工具。Host 必须审查请求、限制 context、model、token 和 tool use，并让用户了解调用。2026 年的标准提案已经决定在后续规范弃用 core Sampling，因此新设计还要考虑迁移。[弃用提案](https://modelcontextprotocol.io/seps/2577-deprecate-roots-sampling-and-logging)

### Q26：Elicitation 是什么？

> Elicitation 允许 Server 通过 Client 向用户请求额外信息。稳定规范支持 form mode 和 URL mode：form 用结构化 schema 收集普通输入；密码、API key、access token、支付凭据等敏感信息不得走 form，必须使用 URL mode，让敏感交互不经过 MCP Client。[Elicitation 规范](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)

#### 追问：用户必须能做什么？

> 看清哪个 Server 在请求、审阅和修改数据、拒绝或取消；URL mode 还应显示目标域名并获得导航同意。

### Q27：Roots 是什么？是安全沙箱吗？

> Roots 在当前稳定规范中向 Server 提示 Client 认为相关的文件系统根目录，但它不是强制 sandbox。Server 仍可能拥有进程环境允许的其他访问权限。安全必须靠 OS 权限、容器、文件 allowlist 和路径校验。

> 由于采用率和语义问题，Roots 已进入后续规范弃用方向，面试时要区分当前稳定能力和未来变化。

### Q28：为什么 Logging 也准备被弃用？

> 官方提案认为 stderr、OpenTelemetry 等成熟机制更适合日志，协议内 logging 增加实现复杂度且采用率低。协议日志也不应替代业务 trace 和安全审计。

## 8. Transport 深挖

### Q29：MCP 有哪些标准 Transport？

> `2025-11-25` 稳定规范定义 stdio 与 Streamable HTTP。旧 `HTTP+SSE` transport 已被 Streamable HTTP 替代，但实现可能为了兼容旧客户端同时保留。[Transport 规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)

### Q30：stdio 如何工作？

> Client 启动 Server 子进程，通过 stdin 发送 JSON-RPC，通过 stdout 读取协议消息。消息以换行分隔；Server 的 stdout 只能输出合法 MCP 消息，日志必须写 stderr。任何 debug print 到 stdout 都可能破坏协议 framing。

#### 追问：stdio 为什么不等于安全？

> 本地 Server 以进程身份运行，能访问它的环境变量、文件和网络。安装一个恶意 stdio Server 等同于安装本地软件。需要审核来源、固定版本、最小环境变量、工作目录、文件权限、网络限制和沙箱。

### Q31：Streamable HTTP 如何工作？

> Server 提供单一 MCP endpoint，处理 POST 和 GET；POST 承载 Client 消息，Server 可返回 JSON 或 SSE；GET 可建立 Server → Client 的消息流。SSE 是 Streamable HTTP 的可选传输手段，不等于旧 HTTP+SSE transport。

### Q32：为什么 Streamable HTTP 要校验 Origin？

> 为防 DNS rebinding：恶意网页可能诱导浏览器访问本机或内网 MCP Server。规范要求 Server 校验传入 Origin；本地服务应只绑定 localhost，并对连接做认证。

#### 追问：Origin 校验能替代认证吗？

> 不能。非浏览器 Client 可以构造 header。Origin 是特定攻击的防线之一，认证授权仍必须独立完成。

### Q33：`MCP-Session-Id` 是什么？

> 稳定 Streamable HTTP Server 可在 initialize response 分配加密安全的 session ID，Client 后续请求携带它，结束时可 DELETE。Session ID 用于关联会话状态，不应当作用户认证凭据。

#### 追问：如果 Server 返回 404 呢？

> 对携带 session ID 的请求返回 404 表示 session 已终止，Client 应重新 initialize，而不是不断重发旧 ID。

### Q34：为什么 2026-07-28 RC 要推 stateless core？

> 候选版目标是减少 sticky session 和共享 session store，使远程 Server 更容易在普通 HTTP 基础设施后水平扩展。但这是 RC 的破坏性方向；当前稳定客户端仍应按已协商版本处理 lifecycle 和 session，不能单方面删除 initialize。

### Q35：自定义 Transport 可以吗？

> 规范允许 pluggable custom transport，但互操作性下降，必须自己定义 framing、连接、授权、重连和安全。除非有明确基础设施约束，优先使用标准 transport。

## 9. Authorization 与 Security

### Q36：MCP Authorization 是不是强制的？

> 授权能力取决于部署和 transport；对访问用户数据的远程 HTTP Server，生产上应实施授权。stdio 通常从受控环境或外部凭据机制获取 credential，而不是照搬远程 HTTP OAuth flow。[Authorization 教程](https://modelcontextprotocol.io/docs/tutorials/security/authorization)

### Q37：远程 MCP 的 OAuth 关键点是什么？

#### 高质量回答

- MCP Server 作为 OAuth resource server。
- Client 通过 metadata 发现授权信息。
- 使用 OAuth 2.1 安全要求和 PKCE。
- 请求包含 `resource` 参数，令牌绑定目标 MCP Server。
- Server 必须验证 issuer、audience、expiry、scope 等。
- 使用 HTTPS 和严格 redirect URI。

当前稳定规范明确要求 Server 只接受签发给自己的 token。[Authorization 规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)

### Q38：什么是 Token Passthrough？为什么禁止？

> Client 给 MCP Server 的 token audience 是 MCP Server。Server 不应原样把它转发给下游 API；否则下游可能错误接受不属于自己的 token，打破 audience 边界并形成 confused deputy。Server 访问下游时应获取单独、面向下游 audience 的 token，必要时做规范的 token exchange。

### Q39：什么是 Confused Deputy？

> MCP Proxy 可能拥有第三方 API 权限，恶意 Client 借它执行自己本不被允许的操作。防御包括每次调用重新校验用户与 scope、第三方授权时绑定具体 client / user consent、最小权限、资源级授权和禁止 token passthrough。[官方安全实践](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)

### Q40：MCP 中的 Prompt Injection 有哪些来源？

- Tool description / server instructions。
- Resource 内容、网页、邮件和文档。
- Tool result。
- Prompt primitive。
- MCP App / UI 内容。

> Host 必须把所有 Server 内容视为数据而不是高优先级指令。System prompt 不是唯一防线，还需要确定性 policy、最小工具、数据流控制和审批。

### Q41：什么是 Tool Poisoning？

> 恶意或被攻破的 Server 在 tool name、description、schema 或 result 中植入诱导指令，影响模型选择或让其泄露来自其他 Server 的数据。防御包括 Server allowlist、schema review、namespacing、描述 hash、变更审批、隔离跨 Server 上下文和调用前展示参数。

### Q42：为什么 Tool annotations 不能直接相信？

> `readOnlyHint`、destructive 等 annotation 本质由 Server 自报。官方也要求 Client 对不可信 Server 的 annotation 保持不信任。Host 应以本地 risk override 和策略为准，不能因为 Server 声称 read-only 就跳过审批。

### Q43：本地 MCP Server 最危险的能力有哪些？

> 文件系统、shell、浏览器 cookie、SSH key、云凭据、环境变量和内网访问。应在容器或 OS sandbox 中运行，限制工作目录和网络，只传必要 env，不允许未经审核的安装命令。

### Q44：如何防 SSRF？

> Server 接收 URL、metadata URL 或 redirect 配置时，应限制 scheme、解析并校验最终 IP、阻止 loopback / link-local / metadata / 私网段、控制 redirect、做 DNS rebinding 防护、限制响应大小和 timeout。简单字符串检查 `localhost` 不够。

### Q45：Session Hijacking 如何防？

> 使用高熵不可预测 session ID；HTTPS；不在日志和 URL 泄露；每次请求重新做授权；session 绑定用户 / client；过期和撤销；不能用 session 代替认证；Host 防止不同 Server 或 tenant 混用 session。

### Q46：MCP 如何做最小权限？

> 三层最小化：连接哪些 Server、当前任务暴露哪些工具、每个 Server token 有哪些 scope。再加资源级 policy、参数约束和操作审批。不要初始化后把 `tools/list` 的所有结果无条件传给模型。

### Q47：用户审批应该绑定什么？

> Server identity、tool name、规范化参数、目标资源、风险、用户、有效期和 request hash。审批“发送消息”不能覆盖模型后来换收件人或正文的调用。

### Q48：MCP Registry 中的 Server 能直接信任吗？

> 不能。Registry 解决发现和分发，不自动证明运行时行为安全。仍需 publisher 验证、固定 artifact digest、依赖扫描、配置审查、运行沙箱和持续监测。

## 10. Discovery、Catalog 与执行治理

### Q49：Host 如何管理大量 MCP Tools？

> 先把 Server 发现结果规范化进 Catalog，记录 server identity、protocol version、tool name、schema hash、risk 和 health；再按 task、user scope、tenant、approval 和健康状态用 Resolver 筛选，只把最小集合给模型。

### Q50：同名 Tool 怎么办？

> 使用稳定 namespace，例如 `mcp.feishu.im_message_list` 或 `(server_id, tool_name)` 作为内部唯一键。模型可见名要稳定、短且无冲突，审计必须保留原始 Server 和 tool name。

### Q51：`notifications/tools/list_changed` 到了怎么办？

> 不应立即让运行中 episode 静默换 schema。Client 重新分页拉取 tools，校验并形成 candidate catalog；比较 spec hash；敏感变化进入审核；原子发布新 revision。运行中的任务继续使用已固定 snapshot 或明确失败迁移。

### Q52：为什么 cursor 必须视为 opaque？

> Cursor 是 Server 的分页状态，Client 不能解析、修改或用业务含义推断它。还要设置最大页数和总工具数，防恶意或错误 Server 无限分页。

### Q53：Tool discovery 可以每请求做吗？

> 通常不应。它增加延迟、上下文不稳定和供应链攻击窗口。应在连接 / refresh 阶段发现，发布 immutable snapshot，通过 listChanged 或管理员刷新更新。

### Q54：如何做 Tool timeout、retry 和 idempotency？

> Host 统一 Gateway 设置 connect / read / total timeout；只对明确瞬态错误重试；读操作通常可重试，写操作只有 provider 支持幂等键时才自动重试。MCP 协议不会替业务 Server保证 exactly-once。

### Q55：Server 返回大结果怎么办？

> 限制 response bytes、content item 数、文本长度和二进制大小；大数据优先返回 Resource link，再按需 read；模型上下文做摘要和选择，不能把整个数据库 dump 直接塞入 prompt。

### Q56：如何观察一次 MCP 调用？

至少关联：

- trace / episode / user / tenant。
- Server ID、transport、protocol version、session。
- JSON-RPC request ID、method。
- tool name、spec hash、catalog revision。
- policy、approval、input / output 安全 hash。
- latency、bytes、retry、error type。
- 下游 provider trace。

> 原始 token、secret 和敏感 Resource 内容不能无差别写日志。

## 11. Tasks、Progress 与 Cancellation

### Q57：MCP Tasks 是什么？

> `2025-11-25` 引入 experimental Tasks，把昂贵请求表示成 durable state machine，支持轮询、延迟取结果、状态通知和取消。Task 有 ID、status、TTL、poll interval 等。[Tasks 规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks)

### Q58：Tasks 等于 Celery / Job Queue 吗？

> 不等于。Tasks 定义协议层状态和交互，Server 内部仍需要持久化 job runner、lease、retry、worker 和结果存储。协议 handle 不能让进程内 coroutine 自动变 durable。

### Q59：Task 有哪些状态？

> 当前实验规范包括 working、input_required、completed、failed、cancelled 等。Notification 是可选的，请求方不能只依赖推送，仍需按 pollInterval 查询。

### Q60：Cancel 成功后底层任务一定停了吗？

> 不一定。规范要求状态转为 cancelled，但底层执行可能无法立即停止，甚至最终完成。Server 必须确保 cancelled 之后不把迟到结果重新变成 completed，也要处理已产生的外部副作用。

### Q61：Progress notification 是否可靠交付？

> 不能当权威状态。它改善用户体验，最终状态仍通过 task / result 查询。progressToken 应视为 opaque correlation token。

## 12. 性能、可靠性与测试

### Q62：stdio 和 HTTP 哪个性能更好？

> 没有绝对答案。stdio 少网络层、适合本地单 Client；HTTP 支持远程、多 Client、独立扩缩容和标准网关。真实性能取决于 Server 工作、连接复用、序列化、SSE、授权和下游 API。

### Q63：MCP Client 要不要复用连接？

> HTTP 应复用 AsyncClient / connection pool，stdio 复用 Server process 和 session。每次 Tool Call 重新建连接或进程会增加 DNS、TLS、初始化和资源开销。

### Q64：Server 不可用如何降级？

> Catalog 标记 health；非关键 Server 从可用工具集合移除；已有任务按 snapshot 明确失败或走语义一致的 fallback；写操作不能在不知是否成功时盲目切另一个 provider。Fallback 也必须审计来源和差异。

### Q65：如何测试 MCP Client？

1. JSON-RPC request / response ID contract。
2. initialize、版本和 capability negotiation。
3. stdio framing / stdout 污染。
4. HTTP JSON、SSE、session、重连和 404 session reset。
5. tools/resources/prompts pagination。
6. listChanged 和 schema drift。
7. protocol error 与 `isError` tool error。
8. timeout、cancel、partial stream 和 malformed Server。
9. OAuth audience、scope、PKCE、token passthrough 拒绝。
10. prompt injection、恶意 description、超大结果和 SSRF。

### Q66：如何测试 MCP Server？

> 用官方 Inspector / SDK contract test 加自有安全测试；验证声明 capability 与实现一致；input/output schema；每个 tool 的 ownership、idempotency、rate limit；不同 tenant 隔离；通知和分页；断连清理；真实下游故障。协议通过不等于业务授权通过。

### Q67：什么是 Contract Test 的版本矩阵？

> 至少覆盖当前稳定版本、项目当前兼容旧版本和准备升级版本；不同 SDK 语言实现互测；对 RC 单独实验，不混入稳定生产。保存 golden messages 时避免把 request ID、session ID 等动态字段写死。

## 13. 近期规范演进怎么回答

### Q68：2026 年 MCP 最大的演进方向是什么？

#### 推荐回答

> 截至 2026-07-14，`2026-07-28` 仍是 RC。它的方向包括 stateless core、first-class Extensions、Tasks 扩展、MCP Apps、授权加固和正式 deprecation policy；Roots、Sampling、Logging 走向弃用。由于存在 breaking changes，生产系统应做双版本 adapter 和 contract test，而不是在稳定 Server 上提前假设 handshake 已消失。

### Q69：为什么要有 Extensions？

> Core 越大，所有 Client / Server 的实现和协商成本越高。Extensions 让 Tasks、Apps 等可选能力独立演进，Host 按需支持。但扩展仍需要命名、版本、capability 和安全治理，不能变成随意 `_meta` 私有字段堆积。

### Q70：MCP Apps 是什么？

> 它是让 Server 向 Host 提供交互式 UI 的扩展方向。Host 渲染远端 UI 时必须按不可信内容处理，使用 sandboxed iframe、严格 CSP、声明网络域、审计 postMessage / tool call，并防 phishing 和数据外传。BinnAgent 当前 Artifact / iframe 是应用内协议，不应称为完整 MCP Apps Host。

## 14. BinnAgent 项目专属压力面试

### Q71：BinnAgent 当前到底用了多少 MCP？

#### 高质量回答

> 当前有一条专用飞书 MCP Client 链路，用于群聊学习线索。它通过 HTTP 发送 `initialize`，接收可选 `Mcp-Session-Id`，发送 `notifications/initialized`，再调用 `tools/call`；能解析普通 JSON 和简单 SSE tool result，并将飞书 payload 归一化成中性 group-learning message。MCP 失败时可以回退到飞书 OpenAPI。

> 这是真实 MCP 调用，但不是通用平台：没有 `tools/list` discovery、capability 校验、resources / prompts、OAuth、通用 notifications、Catalog MCP adapter 或模型自由 tool selection。

### Q72：这条链路是 Agent 自主 Tool Calling 吗？

> 不是。`FeishuMcpMessageImporter` 由确定性业务流程调用固定工具名，如 `im.v1.message.list` 和 `chatMembers.get`。模型没有从动态工具集合中选择调用。这样更可控，也符合当前同步任务的业务特点。

### Q73：当前初始化实现有什么协议风险？

> Client 固定发送 `2025-06-18`，但没有验证 Server 返回的 `protocolVersion`，测试甚至允许 initialize result 缺少 capability；随后 header 仍固定旧版本。它也不检查 Server 是否声明 tools capability。正确做法是解析 InitializeResult、协商支持版本、持久化 negotiated version，并只调用已声明能力。

### Q74：当前 HttpFeishuMcpClient 有哪些工程边界？

- 每次 POST 新建 AsyncClient，没有连接复用。
- 没有通用 `tools/list` 和 schema validation。
- SSE decoder 只取首个 `data:` JSON，不是完整多事件流实现。
- 没有核对 response JSON-RPC ID。
- 没有 GET server stream、listChanged、progress 或 cancel。
- session 失效 404 后不会自动重新 initialize。
- 没有显式 close / DELETE session 生命周期。
- 没有 OAuth 和 token audience 验证。
- 错误消息可能携带截断的远端响应，需要进一步脱敏。

> 对当前固定、低频的飞书调用它是可工作的最小 adapter，但不能直接复用成通用 MCP SDK。

### Q75：OpenAPI fallback 有什么优点和风险？

> 优点是 MCP sidecar 不可用时仍能同步消息。风险是 MCP 调用是否已经产生副作用可能未知；两个 provider 的 schema、权限和分页语义可能不同；fallback 可能掩盖长期 MCP 故障。读取操作相对安全，发送消息等写操作必须有稳定 idempotency key、明确错误分类和 fallback audit。

### Q76：飞书群消息同步为什么不是实时订阅？

> 当前 MCP 主要用固定 `message.list` 做 polling，并保存 cursor。MCP Tool Call 本身不是消息队列；是否实时取决于 Server 提供的 resource subscription、事件工具或飞书 webhook。对学习线索，低频同步反而能控制隐私、成本和噪声。

### Q77：当前项目如何避免把所有群消息写入 learner Memory？

> MCP adapter 只负责拉取和标准化。后续按 participant 映射、当前 learner、analysis 开关和文本类型过滤；显式标签生成候选，无标签进入待分析；用户接受后才写 Vocabulary、WritingPhrase 或 Progress。MCP 传输成功不等于业务数据可以直接进入长期状态。

### Q78：BinnAgent Tool Catalog 与 MCP 怎么连接？

> 目标是 Discovery Manager 从受信配置连接 Server，`tools/list` 后把远端定义规范化为内部 ToolSpec / Descriptor，记录 server、version、spec hash、risk 和 health；Resolver 按 TaskSpec 与 learner scope 筛选；McpToolAdapter 通过 Gateway 执行。当前 Catalog 只有 internal discovery，通用 MCP discovery 仍是 roadmap。

### Q79：为什么不能把飞书 Server 的 tool schema 直接放进 Catalog？

> 远端描述和 schema 会漂移，也可能被篡改。应设置 server / tool allowlist、schema 大小和关键字限制、命名空间、risk override；先进入 candidate snapshot，diff 和审核后原子发布；运行中 episode 保留旧 spec hash。

### Q80：如果用两周改进 BinnAgent MCP，你怎么排优先级？

第一阶段先修专用 Client：

1. 抽象 protocol version negotiation，验证 InitializeResult 和 capability。
2. 复用 httpx AsyncClient，增加 close、404 reinitialize 和 response ID 校验。
3. 使用成熟 SDK 或实现完整 SSE message correlation，不再只读第一条 data。
4. 给固定飞书 tools 增加本地 input/output schema、timeout 和错误分类。
5. 对 write fallback 加 idempotency 和审计。

第二阶段进入 Catalog：

6. 配置级 Server allowlist 和凭据引用。
7. 实现 `tools/list` pagination、namespace、spec hash 和 candidate review。
8. 增加 McpToolAdapter，让调用统一经过 Gateway 与 learner context。
9. 支持 listChanged 后原子 refresh，不改变运行中 episode。

第三阶段补安全与测试：

10. 若接远程多用户 Server，实施 OAuth resource / audience / scope 验证。
11. 增加恶意 schema、prompt injection、超大结果、SSRF 和 session hijack tests。
12. 做 2025-06-18 / 2025-11-25 兼容矩阵；对 2026-07-28 RC 只做隔离实验。

## 15. 系统设计题：设计企业知识与工单 MCP

面试官如果要求“设计一个能查内部知识、创建工单的 MCP Server”，可以这样回答：

1. 把知识文档暴露为 `resources` / parameterized resource template。
2. 把全文搜索暴露为只读 `knowledge.search` Tool。
3. 把创建工单拆成 `ticket.draft` 与 `ticket.create`，后者是写操作。
4. 远程使用 Streamable HTTP，按稳定版本完成 initialize 和 capability negotiation。
5. OAuth token audience 绑定 MCP Server；Server 访问工单 API 使用独立下游 token。
6. 所有查询按 current user 和 tenant 做资源级授权。
7. Host 只向模型暴露当前任务所需 tools，create 前展示完整参数并审批。
8. Tool schema 禁止额外字段，输出有 schema 和大小限制。
9. 使用 idempotency key 避免重复创建工单。
10. 大文档返回 resource link，不直接塞满 Tool result。
11. 记录 server、tool spec hash、user、approval、ticket ID 和 trace。
12. 用恶意文档测试 indirect prompt injection，确保文档不能触发 create。

这种回答同时覆盖协议、领域建模和安全，优于“用 SDK 写两个 decorator”。

## 16. “深入用过”才容易回答的快问快答

### 1. MCP 是模型协议吗？

更准确是 AI Host 与外部能力 Server 的协议；模型通常不直接连接 MCP transport。

### 2. Notification 有 JSON-RPC ID 吗？

没有，也不应收到普通 response。

### 3. initialize 后第一条通知是什么？

当前稳定生命周期中是 `notifications/initialized`。

### 4. Server 声明 tools capability 是否代表所有用户可调用全部 Tools？

不代表，具体工具仍受身份、scope 和 policy 控制。

### 5. Tool annotation 是否可信？

只有在 Server 已被信任且本地 policy 接受时才可参考，不能作为唯一安全依据。

### 6. Resource 与 Tool result 的区别？

Resource 是 URI 标识、可 list/read/subscribe 的上下文对象；Tool result 是一次动作返回，也可以链接或嵌入 Resource。

### 7. MCP 的旧 HTTP+SSE 是当前标准 Transport 吗？

不是，已由 Streamable HTTP 取代；SSE 仍可作为 Streamable HTTP 的响应流机制。

### 8. stdio Server 可以向 stdout 打日志吗？

不可以，stdout 只能输出 MCP message；日志写 stderr。

### 9. Session ID 是认证凭据吗？

不是，不能替代 OAuth 或用户授权。

### 10. Origin 校验能替代 OAuth 吗？

不能，只是防 DNS rebinding 的一层。

### 11. MCP Client token 能否原样传给下游 API？

不能，token passthrough 破坏 audience 边界。

### 12. Tool schema validation 是否等于授权？

不等于，合法参数仍可能访问非法 tenant 或资源。

### 13. `tools/list_changed` 后能否立即替换运行中工具？

不应静默替换，应形成新 catalog revision，运行中任务使用快照。

### 14. Cursor 能否解析出页码？

不能假设，cursor 必须视为 opaque。

### 15. Tasks 是否已稳定？

在 2025-11-25 规范中仍是 experimental。

### 16. Cancel 是否保证底层副作用没发生？

不保证，需要 Server 自己处理取消、幂等和补偿。

### 17. Roots 是 OS sandbox 吗？

不是，只是协议上下文提示。

### 18. 2026-07-28 规范现在可以按 final 实现吗？

截至本文时间不能，它仍是 RC，应隔离试验并等待最终版本。

### 19. MCP Registry 中列出的 Server 能否自动信任？

不能，仍需供应链与运行时安全审查。

### 20. BinnAgent 当前有通用 MCP discovery 吗？

没有，只有飞书专项 HTTP Client 和架构规划。

## 17. 容易让面试官扣分的回答

### “MCP 就是统一版 Function Calling。”

不准确。Function Calling 是模型到 Host 的行动表达，MCP 是 Host / Client 与 Server 的协议。

### “MCP Server 把工具发给模型，模型直接调用。”

遗漏 Host 的筛选、policy 和执行边界。模型不直接持有 transport 和凭据。

### “只要支持 tools/list 和 tools/call 就完整支持 MCP。”

忽略初始化、版本、capability、transport、错误、授权和生命周期。

### “本地 stdio 不走网络，所以安全。”

错误。本地 Server 可能拥有文件、环境变量和网络权限。

### “Resource 就是 RAG 文档。”

过窄。Resource 可以是文件、schema、应用对象和二进制内容；是否做检索由 Host / Server 决定。

### “OAuth token 直接传给下游最简单。”

这是规范明确防范的 token passthrough 风险。

### “Server 说 Tool 是 read-only，就不用确认。”

Annotation 是不可信 hint，本地风险策略才是执行依据。

### “SSE transport 就是当前 MCP HTTP 标准。”

应回答 Streamable HTTP；旧 HTTP+SSE 已被替代。

### “Tasks 提供了持久任务，所以不需要 job queue。”

协议状态不等于 Server 内部执行可靠性。

### “BinnAgent 已经完成 MCP 平台。”

与代码不符。当前是飞书专项 Client，通用 discovery 和 Catalog adapter 尚未完成。

## 18. 五分钟项目讲稿

> 我把 MCP 理解为 AI Host 与外部能力 Server 之间的标准协议，而不是模型 Function Calling 的同义词。Host 内部 MCP Client 先完成版本和 capability negotiation，发现 Server 的 Tools、Resources 和 Prompts；Host 再结合用户、任务和风险选择能力。模型如果生成 tool call，真正的 MCP tools/call、凭据、审批和审计仍由 Host Runtime 控制。
>
> BinnAgent 当前没有为了简历把所有内部工具都 MCP 化，因为内部 Python service 直接调用更简单。项目有一条真实但专用的飞书 MCP 链路：HTTP Client 做 initialize、initialized notification、session header 和 tools/call，支持 JSON与简单 SSE result，再把消息归一化到 group-learning 模型。MCP 不可用时可回退飞书 OpenAPI。
>
> 这条链路不是模型自主 Agent，而是确定性 importer 调固定工具。它当前也有明确边界：固定 2025-06-18 版本但没有真正验证协商结果，没有 tools/list 与 capability check，每次请求新建 HTTP client，SSE 只解析第一条 data，没有 OAuth、listChanged、resources 和通用 Catalog adapter。所以我会把它称为专项 MCP adapter，而不是完整 MCP 平台。
>
> 如果扩展，我不会先把所有远端 Tools 直接交给模型。Discovery Manager 会从管理员 allowlist 连接 Server，分页 tools/list，做 namespace、schema 校验、risk override 和 spec hash，形成 candidate catalog；审核后原子发布 revision。Resolver 根据 TaskSpec、learner ownership 和 scope 选择最小工具集合，执行统一经过 Gateway 做 input/output schema、timeout、idempotency、approval 和 ToolCall audit。
>
> 安全上，远端 MCP 的 token audience 必须绑定 Server，不能 passthrough 到下游 API；本地 stdio Server 按本地软件处理，限制文件、env 和网络；Server description、Resource 和 Tool result 全都视为不可信内容，防止 indirect prompt injection 和 tool poisoning。对于 2026-07-28 的 stateless core 和 Extensions，我会先做兼容实验，因为截至当前它仍是 RC，生产仍按 2025-11-25 稳定规范实现。

## 19. 面试前最终自检

你应该能不看文档回答：

- Host、Client、Server 和 Model 的关系。
- MCP 与 Function Calling、REST、RAG 的区别。
- JSON-RPC request / response / notification 的 ID 语义。
- initialize、版本协商、capability negotiation 和 shutdown。
- Tools、Resources、Prompts 的不同控制模型。
- stdio、Streamable HTTP 与旧 HTTP+SSE 的区别。
- Sampling、Elicitation、Roots、Tasks 的语义和版本状态。
- audience binding、token passthrough、confused deputy、SSRF 和 DNS rebinding。
- 为什么 Tool description、annotation 和 result 都不可信。
- tool discovery、schema drift、catalog snapshot 和 listChanged 如何治理。
- Tasks 为什么不能替代 durable worker。
- BinnAgent 飞书 MCP 当前完成了什么、缺什么、怎么升级。

## 20. 主要官方资料

- [MCP Architecture](https://modelcontextprotocol.io/docs/learn/architecture)
- [Lifecycle 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [Transports 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [Authorization 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [Resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)
- [Prompts](https://modelcontextprotocol.io/specification/2025-11-25/server/prompts)
- [Elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)
- [Experimental Tasks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks)
- [Roots、Sampling、Logging Deprecation SEP](https://modelcontextprotocol.io/seps/2577-deprecate-roots-sampling-and-logging)
- [2026-07-28 Release Candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)
- [Official Specification Repository](https://github.com/modelcontextprotocol/modelcontextprotocol)

## 21. 项目相关文档

- [AI Agent、Tools 与 Function Calling 面试指南](AI-Agent-Tools-Function-Calling面试指南.md)
- [Dynamic Tool Registry、Discovery 与 Runtime Injection](../architecture/15-dynamic-tool-registry-discovery-injection.md)
- [Learning Tools and MCP](../architecture/05-learning-tools-and-mcp.md)
- [飞书 MCP 群聊学习线索导入方案](../architecture/feishu_mcp_group_learning_source_spec.md)

