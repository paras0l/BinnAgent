# FastAPI 深度面试题、参考回答与压力追问

> 目标：让回答体现对 ASGI、依赖注入、异步 I/O、事务、认证授权、流式响应、后台任务、测试与生产部署的真实理解，而不是只会写 `@router.get()`。
>
> 项目背景：BinnAgent 当前使用 FastAPI 0.137.2、Starlette 1.3.1、Pydantic 2.13.4、SQLAlchemy 2.0.51、asyncpg 和 Uvicorn 0.49.0。`pyproject.toml` 使用宽松下限，面试时应主动说明生产升级需要锁定版本并做契约回归。

## 1. 面试官真正想判断什么

看到简历写 FastAPI，我主要判断：

1. 是否理解 ASGI 请求生命周期，而不只是装饰器语法。
2. 是否知道 `async def` 什么时候提升吞吐，什么时候反而阻塞事件循环。
3. 是否能正确设计依赖注入、资源生命周期和事务边界。
4. 是否把认证、资源级授权和请求参数验证区分开。
5. 是否处理过 SSE、文件上传、后台任务和客户端断开。
6. 是否知道多 worker、连接池、进程内单例和部署一致性的关系。
7. 是否能设计稳定的 API 契约、异常模型、幂等和分页。
8. 是否能用依赖覆盖、ASGITransport、真实数据库和故障注入测试。
9. 是否能指出项目当前方案的边界，而不是把 demo 配置说成生产就绪。

真正的深度往往体现在“请求成功返回之外会发生什么”：提交事务失败、客户端断线、worker 重启、后台任务丢失、依赖清理时机、同一资源被并发修改时，系统是否仍然正确。

## 2. 一分钟总回答

如果面试官问“你怎么理解 FastAPI”，可以回答：

> FastAPI 是建立在 Starlette 和 Pydantic 之上的 ASGI Web 框架。Starlette 提供请求路由、中间件、响应和 ASGI 能力，Pydantic 负责数据校验与 schema，Uvicorn 作为 ASGI Server 驱动事件循环。
>
> 我认为它真正的工程价值不只是自动文档，而是类型驱动的 API 契约、可组合的依赖图、原生异步和与 ASGI 生态的集成。但框架不会自动解决事务、授权、幂等、后台任务可靠性和阻塞 I/O，这些仍需要应用设计。
>
> 在 BinnAgent 中，我用 yield dependency 管理 AsyncSession 事务，用 ownership dependency 把 learner 授权放在路由入口，用 lifespan 初始化 Tool Catalog 并释放 Redis、模型客户端和观测资源；聊天流使用 SSE，并在 generator 内创建独立 session，避免长期持有请求级事务。项目当前仍有生产边界，例如本地 header 身份不是正式认证、教材解析使用进程内 BackgroundTasks、健康检查和多 worker catalog 一致性还需要完善。

## 3. FastAPI 与 ASGI 基础

### Q1：一次 FastAPI 请求经过哪些层？

#### 高质量回答

```text
Client
→ Reverse Proxy / Load Balancer
→ Uvicorn ASGI Server
→ ASGI middleware stack
→ Starlette router
→ FastAPI dependency resolution
→ request parsing + Pydantic validation
→ endpoint / service
→ response serialization + validation
→ dependency cleanup
→ ASGI response events
```

> Uvicorn 负责网络连接和 ASGI 调用；Starlette 负责底层 Web 能力；FastAPI 负责依赖注入、参数提取、校验和 OpenAPI。理解分层后，遇到 CORS、streaming、middleware、validation 或 event loop 问题时才能定位到正确层。

#### 追问：FastAPI 是 Web Server 吗？

> 不是。FastAPI 是 ASGI application framework，通常由 Uvicorn 等 ASGI Server 运行。生产还常在前面放反向代理或云负载均衡。

### Q2：WSGI 和 ASGI 的区别是什么？

#### 高质量回答

> WSGI 主要是同步 request-response 接口；ASGI 是异步协议，能表达 HTTP、WebSocket、lifespan 和流式事件。ASGI 不代表所有代码都会自动并发，应用内部如果执行阻塞 I/O，仍会阻塞 event loop。

#### 追问：ASGI 如何返回 HTTP 响应？

> Server 调用 application 的 `scope, receive, send` 接口。应用通过 `send` 发出 response start 和一个或多个 response body event；流式响应就是分多次发送 body，而不是一次生成完整字节串。

### Q3：FastAPI、Starlette、Pydantic、Uvicorn 分别做什么？

#### 高质量回答

| 组件 | 主要责任 |
|---|---|
| FastAPI | 参数声明、依赖注入、校验集成、OpenAPI |
| Starlette | ASGI 路由、中间件、Request / Response、WebSocket |
| Pydantic | 数据解析、校验、序列化和 JSON Schema |
| Uvicorn | 网络服务器、事件循环和 ASGI 协议驱动 |

> SQLAlchemy、Redis、httpx 等只是应用依赖，FastAPI 不替它们管理业务事务和连接一致性。

### Q4：为什么 FastAPI 性能通常不错？

#### 高质量回答

> 它基于轻量 ASGI 栈并支持异步 I/O，Pydantic 2 的校验核心也较高效。但真实性能取决于数据库、外部模型、序列化、连接池和业务逻辑。框架 benchmark 不能代表一个包含 LLM、RAG 和数据库写入的应用吞吐。

#### 追问：换成 FastAPI 就能解决慢接口吗？

> 不能。CPU 密集任务、慢 SQL、串行外部调用和连接池耗尽不会因为框架异步而消失。应先做 trace 和 profile，分解排队、DB、provider、serialization 和网络耗时。

## 4. `async def`、并发与阻塞

### Q5：FastAPI 中什么时候用 `async def`，什么时候用普通 `def`？

#### 高质量回答

> 调用 asyncpg、异步 httpx、Redis async client 等可等待 I/O 时使用 `async def`。如果依赖库只有同步阻塞接口，可以用普通 `def`，FastAPI 会在线程池中执行同步 endpoint；也可以显式把短阻塞工作移到线程池。

> 关键不是语法，而是调用链是否真正异步。`async def` 中直接调用同步文件、requests、CPU 密集 PDF 解析，反而会阻塞事件循环并影响同一 worker 的其他请求。

#### 追问：普通 `def` endpoint 会阻塞 event loop 吗？

> FastAPI / Starlette 通常把同步 endpoint 放到线程池，因此不会直接占住 event loop，但线程池容量有限。把大量长 CPU 任务都塞进去仍会排队和争用资源。

### Q6：并发、并行和异步有什么区别？

#### 高质量回答

> 异步是一种在等待 I/O 时让出控制权的编程方式；并发是多个任务在时间上推进；并行是多个任务同一时刻在不同 CPU core 或机器执行。单 event loop 可以高并发，但 CPU 密集 Python 代码仍不能获得真正多核并行。

#### 追问：CPU 密集任务怎么处理？

> 短任务可限制性地放线程或进程池；重 PDF 解析、embedding 批处理等应进入独立 worker / job queue，避免占用 API worker。还要做 job 状态、幂等、租约、重试和取消，而不只是 `create_task()`。

### Q7：在 `async def` 中使用 `time.sleep()` 会怎样？

> 它会阻塞当前 worker 的 event loop。异步等待使用 `await asyncio.sleep()`；同步阻塞库需要线程池或独立 worker。

#### 追问：SQLAlchemy AsyncSession 是否意味着所有 ORM 操作都不阻塞？

> 网络 I/O 通过异步 driver 执行，但 Python 对象构造、序列化、复杂业务计算仍占 CPU。还要避免触发隐式 lazy load，因为异步上下文中隐式 I/O 难以控制，最好显式查询或 eager loading。

### Q8：`asyncio.gather()` 是否可以随便并行数据库查询？

#### 高质量回答

> 不能在多个并发 coroutine 中共享同一个 AsyncSession。Session 表示事务和单位工作，不是并发安全对象。独立只读任务若确实需要并行，应使用独立 session，并评估连接池压力；很多时候一条合并 SQL 比并发多条 SQL 更好。

#### 追问：并行调用外部模型时还要考虑什么？

> provider 限流、连接池、取消传播、部分失败、总 timeout 和预算。需要 semaphore 或 provider 级 concurrency limit，不能仅用 gather 无上限 fan-out。

## 5. 路由、参数与 API 契约

### Q9：FastAPI 如何判断参数来自 path、query、header、cookie 还是 body？

#### 高质量回答

> 与 path 模板同名的标量通常来自 path；其他简单标量默认作为 query；Pydantic model 通常作为 body；也可以用 `Path`、`Query`、`Header`、`Cookie`、`Body` 显式声明。生产 API 我偏向显式声明重要约束，减少重构时来源变化。

### Q10：为什么要使用 request model 和 response model？

#### 高质量回答

> Request model 提供边界校验和清晰契约；response model 除了生成文档，还能验证和过滤输出，防止 ORM 对象中的内部字段、密钥或其他 learner 数据意外返回。不能只把 Pydantic 当类型提示。

#### 追问：返回类型注解和 `response_model` 有什么关系？

> FastAPI 可从返回注解生成响应 schema，也可以显式指定 `response_model`。当内部返回对象类型与公开契约不同，或需要明确过滤时，我会使用独立 response model，避免把数据库模型直接当 API schema。

### Q11：Pydantic v2 常用哪些能力？

#### 高质量回答

- `Field` 做范围、长度、别名和描述。
- `field_validator` 做单字段规范化。
- `model_validator` 做跨字段不变量。
- `model_validate()` 从外部数据构建模型。
- `model_dump(mode="json")` 输出 JSON 兼容数据。
- `ConfigDict` 控制 extra、strict、from_attributes 等行为。

> 业务校验不能全部塞进 Pydantic。需要数据库、当前用户或外部状态的规则应在 service / dependency 中完成。

### Q12：为什么 `metadata: dict[str, Any]` 要谨慎？

#### 高质量回答

> 它提供扩展性，但绕过了很多 schema 约束，可能让未知字段进入日志、数据库和后续 prompt。应限制大小和允许键，敏感字段拒绝，稳定后升级为明确 schema。BinnAgent 多个 request model 有自由 metadata，这是灵活点也是治理边界。

### Q13：如何设计状态码？

#### 高质量回答

| 场景 | 常见状态码 |
|---|---:|
| 成功创建资源 | 201 |
| 已接受异步任务 | 202 |
| 成功无响应体 | 204 |
| 请求格式或校验失败 | 422 |
| 未认证 | 401 |
| 已认证但无权限 | 403 |
| 资源不存在 | 404 |
| 当前状态冲突 / 重复提交 | 409 |
| 负载过大 | 413 |
| 不支持的媒体类型 | 415 |
| 上游响应错误 | 502 |
| 服务暂时不可用 | 503 |

> 状态码还要配稳定的错误 code，不能让客户端依赖中文 detail 文案判断业务。

### Q14：PUT 和 PATCH 怎么选？

> PUT 通常表达对资源的完整替换或可幂等设置；PATCH 表达部分更新。无论方法名是什么，都要定义缺失字段、null、版本冲突和幂等语义。BinnAgent 的 classroom progress 使用 PUT，但 body 更像完整进度快照，这个选择是合理的。

### Q15：API 如何做版本管理？

#### 高质量回答

> 兼容性优先：新增可选字段通常可向后兼容，删除、重命名、改变枚举或语义需要新版本或过渡。可使用 `/api/v1`、Header 或独立 schema 包，但最重要的是 consumer contract test、弃用窗口和变更日志。数据库 migration 版本不等于 API 版本。

## 6. 依赖注入系统

### Q16：FastAPI 的 `Depends` 是什么？

#### 高质量回答

> `Depends` 声明一个请求级依赖图。FastAPI 根据函数签名解析子依赖、执行校验，并把结果注入 endpoint。它适合当前用户、数据库 session、权限策略和可替换 provider，不只是为了少写参数。

> 同一请求中相同依赖默认会缓存结果，因此多个下游依赖可以共享一个 session 或 current user；需要重新执行时可显式关闭缓存，但要清楚资源成本。

#### 追问：依赖的执行和清理顺序？

> 按依赖图先执行前置依赖，yield dependency 的清理按栈反向执行。具体清理与 streaming response 的时序在 FastAPI 历史版本中有变化，因此长期流不要依赖模糊时序，应写版本固定的集成测试并显式管理所需资源。

### Q17：yield dependency 如何管理数据库？

#### 高质量回答

```python
async def get_db_session():
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

> yield 前创建资源，endpoint 执行时使用，yield 后提交或回滚并清理。它形成默认的 request transaction，但并不适合所有接口。

#### 追问：为什么不一定每个请求都自动 commit？

> GET 也会走 commit；复杂业务可能需要中途提交或多个独立事务；StreamingResponse 生命周期较长；如果 endpoint 内显式 commit，dependency 又 commit，语义会混杂。更清晰的方案是明确 unit-of-work：只读 session 不提交，写 service 明确事务边界，依赖负责 rollback 和 close。

### Q18：BinnAgent 的 `get_db_session()` 有什么优点和风险？

#### 高质量回答

优点：

- 每请求独立 AsyncSession。
- 正常完成统一 commit，异常统一 rollback。
- endpoint 不需要重复资源清理。

风险：

- 所有 endpoint 包括只读请求都会 commit。
- 部分 endpoint 又手动 commit，事务边界不统一。
- 长请求会长期占用连接和 transaction。
- `async with` 已会关闭 session，finally 再 close 略显重复。
- commit 发生在 dependency teardown，业务代码容易误以为返回前已经持久化成功。

> 我会保留 request-scoped session，但把关键事务交给明确的 Unit of Work / service，并规定何处允许显式 commit。

### Q19：依赖注入是否等于 Service Locator？

> 不完全相同。FastAPI 根据显式函数签名构建依赖图，调用者可以看见依赖；Service Locator 通常在函数内部从全局容器取对象，依赖更隐蔽。但如果所有业务 service 都直接依赖 FastAPI `Depends`，也会把领域层绑死在 Web 框架。我的做法是路由用 Depends 构造可信上下文，普通 Python service 使用显式构造参数。

### Q20：如何测试 Depends？

#### 高质量回答

> 用 `app.dependency_overrides[dependency] = fake_dependency` 替换数据库、current user 或 provider，测试结束必须清理。对权限依赖还要做真实集成测试，避免 override 把所有 ownership 检查绕过后产生虚假的覆盖率。

## 7. SQLAlchemy AsyncSession 与事务

### Q21：Session、Connection 和 Transaction 的区别？

#### 高质量回答

> Engine 管理连接池；Connection 是数据库连接；Transaction 是一组原子操作；ORM Session 是单位工作和 identity map，内部按需获取连接并管理 transaction。Session 不是数据库本身，也不应跨请求或并发 task 共享。

### Q22：`flush()` 和 `commit()` 的区别？

> `flush()` 把待处理 SQL 发给当前 transaction，使生成 ID 和约束错误提前出现，但事务仍可回滚；`commit()` 提交事务并使变更对其他事务可见。业务流程中需要新 ID 时常 flush，不应为了拿 ID 就提前 commit 破坏原子性。

### Q23：为什么 BinnAgent 设置 `expire_on_commit=False`？

> commit 后 ORM 对象属性不会立即过期，API 可以继续序列化对象，减少异步环境中意外 lazy load。但代价是对象可能持有陈旧状态，因此不能把 commit 后的实例当成数据库最新事实；需要时显式 refresh 或重新查询。

### Q24：如何避免 N+1 查询？

> 先通过 SQL trace 发现，再使用 selectinload / joinedload、批量查询、聚合 SQL 或明确 projection。不能在 response serialization 时让 ORM 关系隐式逐条加载，异步 ORM 下尤其容易失败或产生不可见 I/O。

### Q25：如何处理并发更新？

#### 高质量回答

- 数据库唯一约束保证最终不变量。
- 使用 version column / ETag 做 optimistic concurrency。
- 必要时 `SELECT ... FOR UPDATE` 做悲观锁。
- 使用原子 SQL update 而不是 read-modify-write。
- 为重复命令设计 idempotency key。

> 只在 Python 中先查“是否存在”再 insert 仍有竞态，必须让数据库约束兜底，并把 IntegrityError 转成稳定的 409 或幂等结果。

### Q26：事务中调用 LLM 或远程 API 有什么问题？

> 会长时间占用连接和锁，增加死锁、超时和池耗尽风险。通常先读必要快照并结束事务，再调用外部服务，最后开短事务验证版本并写入。若必须保证跨系统一致性，使用状态机、outbox 或 Saga，而不是把数据库 transaction 一直开着等待模型。

### Q27：连接池如何配置？

#### 高质量回答

> 要结合 worker 数、每 worker 并发、数据库最大连接和长请求比例计算，而不是每个 worker 都给很大 pool。关键配置包括 pool size、overflow、timeout、recycle 和 pre-ping。BinnAgent 已启用 `pool_pre_ping=True`，能减少使用失效连接，但不能替代合理 pool sizing 和数据库监控。

## 8. 认证、授权与安全

### Q28：认证和授权有什么区别？

> 认证回答“你是谁”，授权回答“你能否访问这个 learner / episode / memory”。请求中有合法 user ID 不代表能访问任意 path 参数。资源级授权必须在查询或 service 边界执行。

### Q29：BinnAgent 当前身份方案是什么？能用于生产吗？

#### 高质量回答

> 当前 `get_current_user()` 从 `x-user-id` / `x-dev-user-id` 读取 UUID，没有 header 时回退到固定本地用户，并允许访问未认领 learner。这是本地开发身份 shim，不是生产认证。生产必须由受信任网关或应用验证签名 token / session，不能相信客户端任意 header。

#### 追问：如果前面有 API Gateway 注入 header 呢？

> 必须保证外部客户端无法直连应用，也不能覆盖该 header；网关先清除外部同名 header，再注入签名或受 mTLS 保护的身份。应用仍应验证 issuer、audience、expiry 和必要 scope。

### Q30：BinnAgent 的 learner ownership dependency 有什么价值？

> 路由 prefix 带 `{learner_id}`，`get_current_learner → require_learner_access → get_current_user + db` 构成依赖链。endpoint 使用 `current_learner.id` 调 service，减少直接相信 path learner_id 的风险。这比每个 router 手写一遍鉴权更一致，也便于测试覆盖。

#### 追问：只在父 learner 路由鉴权够吗？

> 还要对 episode、checkpoint、attempt 等子资源做 scoped query，例如同时过滤 `resource.id` 和 `learner_id`，防止替换子资源 ID。BinnAgent 的 ownership helpers 已提供这类查询，但旧接口仍需持续审计。

### Q31：403 和 404 在资源授权中怎么选？

> 401 用于未认证；已认证但明确无权通常是 403。对于敏感资源，为避免泄露其是否存在，可以把“不存在”和“不属于当前用户”都返回 404。关键是整个 API 保持一致并记录内部真实拒绝原因。

### Q32：为什么参数校验不能替代授权？

> Pydantic 能证明 `learner_id` 是合法 UUID，不能证明它属于当前用户。认证和 ownership 必须基于可信上下文与数据库关系重新判断。

### Q33：Debug API 为什么返回 404 而不是 401/403？

> 这是降低调试面暴露的选择：未启用、origin 不允许、token 缺失或错误都表现为不存在。但 Origin 不是认证机制，非浏览器客户端可伪造；真正边界仍是强 token、网络隔离和关闭生产 debug console。token 比较还可以使用 constant-time compare，并做轮换与审计。

### Q34：还需要哪些常见 Web 安全措施？

- CORS 只允许可信 origin，不使用带凭据的通配符。
- 请求体、文件、分页和并发限制。
- 反向代理层 timeout、rate limit 和 header 清理。
- 输出编码和 Content-Type 正确，避免把不可信 HTML 直接执行。
- secret 不写日志和响应。
- 上传文件做路径、类型、大小、恶意内容和存储隔离。
- 对 state-changing cookie 请求做 CSRF 防护。
- OpenAPI / debug / internal endpoints 做环境隔离。

## 9. Lifespan、Middleware 与应用资源

### Q35：为什么推荐 lifespan，而不是旧 startup / shutdown 事件？

> Lifespan 用一个 async context manager 清晰表达应用启动和关闭，适合初始化连接池、客户端、catalog 和观测资源，并在 finally 中释放。它还能让测试显式控制生命周期。

### Q36：BinnAgent 的 lifespan 做了什么？

> 启动时初始化 Tool Catalog，并尝试从数据库加载 sandbox permission policy，放到应用状态；关闭时释放 Redis、ModelRouter 和 observability。这体现了共享资源由应用生命周期管理，而不是每请求新建客户端。

#### 追问：这里有什么风险？

> 加载 sandbox policy 的异常被全部吞掉，虽然注释说明会保留 strict policy，但数据库不可用、迁移缺失和代码 bug 都无法区分。生产应至少结构化记录异常，并让 readiness 反映依赖状态；对关键配置决定 fail-fast 还是安全降级。

### Q37：`app.state` 和模块全局单例怎么选？

> `app.state` 让资源与 application instance 绑定，测试可创建多个 app；模块全局更简单但导入时初始化、测试隔离和多 app 场景较差。无论哪种，多 worker 下每个进程都有一份，不能把它当集群共享状态。

#### 追问：BinnAgent Tool Catalog 多 worker 有什么问题？

> enable / disable 和 refresh 当前主要修改进程内 catalog。请求打到另一个 worker 可能看到不同状态。生产需要数据库 / Redis 保存 revision 和控制面状态，进程订阅失效通知，或把管理操作广播并验证收敛。

### Q38：Middleware 和 Dependency 有什么区别？

> Middleware 包围所有匹配请求，适合 trace ID、访问日志、CORS、压缩等横切逻辑；Dependency 只在指定路由依赖图执行，能拿到解析后的业务参数，适合 current user、DB session 和资源授权。异常处理器负责统一把异常映射为响应。不要把所有业务鉴权塞进一个无法理解资源 ID 的通用 middleware。

### Q39：Middleware 顺序为什么重要？

> 外层 middleware 先收到请求、后收到响应。CORS、异常捕获、日志和 trace 的顺序会决定错误响应是否带 CORS header、是否记录完整耗时和异常。应通过测试确认，而不是只看注册顺序猜测。

## 10. 异常与错误契约

### Q40：`HTTPException` 应该在哪里抛？

> 路由和 Web adapter 可以把业务结果映射为 HTTPException；领域 service 更适合抛明确的 domain exception，避免绑定 FastAPI。全局 exception handler 再转换为统一错误 envelope。BinnAgent 部分 service 和 ownership helper 直接抛 HTTPException，开发快，但领域层与 HTTP 耦合较强。

### Q41：统一错误响应应该包含什么？

```json
{
  "error": {
    "code": "episode_not_waiting",
    "message": "Episode is not waiting for an answer",
    "request_id": "req_...",
    "details": null
  }
}
```

> `code` 给客户端稳定判断，message 给用户或开发者，request_id 关联日志。内部 stack、SQL、provider secret 不返回。Validation error 也可归一化，但保留字段路径。

### Q42：502、503、504 如何区分？

> 502 表示上游返回无效响应；503 表示本服务或依赖暂时不可用；504 通常由 gateway 表示等待上游超时。应用内部也可映射 timeout，但要与网关配置一致。BinnAgent 把模型不可用映射 503、schema 错误映射 502，是可解释的区分。

### Q43：能否 `except Exception` 后返回 200 + failed？

> 不建议。它破坏 HTTP 和监控语义，让调用方把失败当成功。只有业务协议明确规定异步 job 状态时，HTTP 200 返回 `{status:"failed"}` 才可能合理；未预期异常应记录并返回 5xx。

## 11. StreamingResponse、SSE 与 WebSocket

### Q44：BinnAgent 的聊天流为什么用 SSE？

> 聊天 token 主要是服务端单向推送，SSE 基于 HTTP、浏览器支持 EventSource 语义、容易穿过代理并支持 event 类型。WebSocket 更适合真正双向、低延迟交互，但连接管理、认证续期和基础设施更复杂。

### Q45：实现 SSE 需要注意什么？

- `Content-Type: text/event-stream`。
- 正确的 `event:` / `data:` 格式和空行分隔。
- 禁止代理缓冲，如 `X-Accel-Buffering: no`。
- 合理 Cache-Control。
- 心跳防止 idle timeout。
- 检测客户端断开并取消上游模型流。
- 事件 ID / sequence 支持重连和去重。
- 对 error、done 和业务后处理状态定义明确协议。

> BinnAgent 已设置 media type、no-cache 和禁止 Nginx buffering，并区分 meta、delta、continuation、error、done、skill 事件；后续还应增加 heartbeat、disconnect 检测和 resume cursor。

### Q46：StreamingResponse 中为什么不能一直使用请求级 DB session？

#### 高质量回答

> 流可能持续很久，依赖清理时机又与框架版本相关。长期持有 session 会占用连接和 transaction，客户端断线也可能延迟释放。BinnAgent 在进入 stream 前读取并 commit，然后 generator 内用新的短 session 做 PromptExecution 和最终持久化，这是更稳健的方向。

#### 追问：当前实现还可以怎么改？

> 每个持久化阶段使用短事务；把生成与保存状态做 event ID 幂等；监听 disconnect 并取消 provider；定义 assistant 消息是生成开始即占位还是完成后落库；避免 `done` 后仍长时间运行 vocabulary agent，否则客户端会以为连接已经结束但服务还在工作。

### Q47：客户端断线后 generator 会自动停吗？

> 不能只依赖自然异常。要检查 Request disconnect、处理 cancellation，并确保 httpx stream、数据库 session 和 provider 请求能正确关闭。有些外部调用不支持立即取消，还需要后台清理和幂等结果处理。

### Q48：SSE 如何恢复丢失事件？

> 每个事件带单调 sequence / event ID，服务端把关键事件持久化；客户端重连发送 Last-Event-ID 或业务 cursor。纯 token delta 可以选择不完整恢复，但最终消息和状态必须能通过普通 GET 查询，stream 不能成为唯一事实来源。

## 12. BackgroundTasks 与任务队列

### Q49：FastAPI `BackgroundTasks` 的语义是什么？

> 它在响应之后由同一应用进程执行，适合短小、非关键的后处理。它不是持久化任务队列：进程重启会丢失，缺少跨 worker 调度、租约、可靠重试、死信和独立扩缩容。

### Q50：BinnAgent 用 BackgroundTasks 做教材解析有什么问题？

> 教材解析可能耗时长、CPU 和内存重，而且是用户可见业务任务。当前代码先创建 queued ParserRun 并 commit，再把解析加入 BackgroundTasks，这比直接在请求内处理好，也保留了状态；但 worker 重启后 queued / running task不会自动继续，任务还可能占用 API worker。

#### 改进回答

> 将 ParserRun 作为 durable job source，独立 worker 按 lease claim；使用 `(source_id, input_hash, parser_version)` 幂等；周期更新 heartbeat 和 progress；lease 超时可重试；达到上限进入 failed / review queue；API 的 202 只返回 job ID。BinnAgent 的 exercise pool 已有独立 Worker 思路，教材解析可统一到类似模型。

### Q51：什么时候 BackgroundTasks 是合适的？

> 短审计日志、非关键通知、缓存失效等即使偶尔丢失也能容忍的任务。发送关键邮件、支付、长解析、Memory 核心写入不应只依赖进程内 background task。

## 13. 文件上传与静态响应

### Q52：BinnAgent 当前 PDF 上传链路有什么优点？

> 使用 `Path(filename).name` 防目录穿越；检查 Content-Type、PDF magic prefix 和大小；按 SHA-256 去重；真实存储名使用 digest；删除文件时 resolve 并验证仍位于 upload directory。这些都比直接保存用户文件名安全。

### Q53：当前 `await request.body()` 有什么问题？

> 它会把整个文件读进内存，50 MB 并发上传会迅速增加 worker 内存；随后 `Path.write_bytes()` 是同步文件 I/O，位于 async endpoint 中会阻塞 event loop。更稳妥的是 `UploadFile` 或 request stream 分块读取、边计算 hash 边写临时文件，限制总字节，完成后原子 rename，并将对象存储 I/O 异步化或放线程池。

#### 追问：只检查 `%PDF` 足够吗？

> 不够。它只能排除明显错误，不能证明文件安全或可解析。需要解析器隔离、页数 / 解压大小限制、超时、恶意文件扫描，并且不在主 API 进程执行不可信重解析。

### Q54：FileResponse 如何防路径穿越？

> 不把用户 path 直接拼到文件系统；先从受控 catalog 映射资源，resolve 后校验路径位于允许根目录；限制 filename 和扩展名；不存在统一返回 404。BinnAgent 的 audio / asset helpers 应承担这个可信映射职责。

## 14. 测试策略

### Q55：如何测试 FastAPI 应用？

#### 高质量回答

1. Pydantic / service unit tests。
2. Router contract test：状态码、schema、headers、错误 code。
3. Dependency test：认证、ownership 和 session rollback。
4. ASGI integration：`httpx.AsyncClient + ASGITransport`。
5. Test DB：事务、约束、并发和 migration。
6. 外部 provider 使用 fake transport / recorded response。
7. SSE 测 event 顺序、错误、断开和最终持久化。
8. E2E 经真实 Uvicorn / proxy 验证网络层行为。

### Q56：ASGITransport 测试有哪些盲点？

> 它速度快且不占真实端口，但不会覆盖真实 socket、proxy buffering、worker、timeout、TLS 和连接断开差异。还要注意 httpx 的 ASGITransport 默认不一定自动运行 lifespan；BinnAgent 当前简单 fixture 直接传 `ASGITransport(app=app)`，可能没有验证 Tool Catalog startup 和资源 shutdown。应使用 lifespan manager 或显式 app factory 生命周期测试。

### Q57：如何隔离测试数据库？

> 每测试事务回滚适合单连接场景，但 background task / 多 session 看不到同一未提交事务；也可以每测试独立 schema / database，代价更高。异步集成测试要与应用 session factory 指向同一 test database，并禁止误连开发库。Migration tests 应从空库执行 Alembic upgrade，而不是只调用 metadata.create_all。

### Q58：依赖 override 最容易犯什么错？

> 测试后未清理导致跨测试污染；override current user 后没有再测真实 ownership；fake session 生命周期与生产不同；全局 app 在并行测试中共享 overrides。更稳妥的是 app factory + fixture 作用域清理。

### Q59：如何测试事务 rollback？

> 构造 service 在写入一半后抛异常，调用 endpoint 后用独立 session 查询，确认没有部分写入；再测试 IntegrityError 是否映射为预期 409；对手动 commit 的 endpoint 额外检查是否打破 request atomicity。

### Q60：SSE 怎么测试？

> fake model 逐块输出，使用流式 client 读取并解析 event；断言 meta → delta* → done / error 顺序；模拟 provider timeout 和客户端取消；最后用新 session 查询消息是否落库。还要测试 UTF-8、多行 data、空 chunk 和 continuation 上限。

## 15. 部署、扩展与可观测性

### Q61：Uvicorn worker 数怎么确定？

> 没有固定公式。I/O 密集应用可每 worker 承担较高并发，但还受数据库 pool、外部 provider、内存和长连接影响。通过压测找 event loop lag、P95、连接池等待和内存拐点。SSE 长连接会长期占用 worker 的连接状态，但等待 I/O 时不必独占线程。

### Q62：多 worker 下哪些对象不共享？

> Python 全局变量、内存 cache、app.state、InMemory checkpointer、Tool Catalog 和进程内限流器都不共享。共享状态需要 Postgres、Redis 或专门控制面。关闭一个 worker 也只释放该进程自己的客户端。

### Q63：健康检查如何设计？

#### 高质量回答

- Liveness：进程和 event loop 是否活着，不依赖所有外部服务。
- Readiness：是否能接流量，检查关键配置、数据库和必要 catalog。
- Dependency diagnostics：模型、Redis 等详细状态，受内部权限保护。

> BinnAgent `/health` 当前只返回固定 ok，更接近 liveness；`/internal/model/health` 检查模型。还应增加数据库与 migration readiness，并避免 readiness 因非关键模型短暂失败而频繁杀进程。

### Q64：如何做 graceful shutdown？

> 停止接收新请求，等待有限时间内的在途请求和 stream，取消或交接后台任务，flush 观测数据，关闭 HTTP / Redis / DB 资源。超过 deadline 后强制退出。长任务必须可从 durable job 恢复，不能依赖进程永不退出。

### Q65：要记录哪些 API 指标？

- request count、状态码、P50/P95/P99。
- in-flight 请求、SSE 连接、断开和持续时间。
- DB pool active / wait / timeout、SQL latency。
- provider latency、token、error、retry。
- background job queue depth、lease timeout、failure。
- event loop lag、CPU、memory、worker restart。

> 日志使用 request / trace / learner-safe correlation ID，敏感请求体和 token 不记录。高基数字段不能直接作为 metrics label。

### Q66：超时应该在哪些层设置？

> Client、reverse proxy、Uvicorn / ASGI、应用 service、数据库和外部 httpx 都要有协调的 timeout。外层 timeout 应略大于内层，内层先失败并释放资源。SSE 的 idle timeout 需要 heartbeat 或单独配置，不能与普通 API 一刀切。

### Q67：如何做限流？

> 根据可信 user / tenant、IP 和能力类型限制，不只按客户端可伪造 header。模型生成、上传和普通读取应有不同 quota；多 worker 使用 Redis 等共享计数；返回 429 和 Retry-After。限流还要与 provider quota、并发 semaphore 和预算结合。

## 16. BinnAgent 项目专属压力面试

### Q68：请评价 BinnAgent 的 FastAPI 分层。

#### 推荐回答

> 优点是 router 按领域拆分，Pydantic request schema 明确，AsyncSession 和 ModelRouter 通过 dependency 注入，核心学习流程进入 orchestrator / service，lifespan 管共享资源。learner 路由开始统一使用 ownership dependency。

> 当前问题是部分 router 文件过大，例如 knowledge 和 chat 承担较多 helper 与业务逻辑；异常契约不统一；部分 service 直接抛 HTTPException；身份仍是 dev header；请求事务和显式 commit 混用；后台解析还在 API 进程。下一步应按 API adapter、application service、domain、infrastructure 拆边界，而不是机械按文件行数拆。

### Q69：`src/db.py` 和 `src/api/deps.py` 都有 session dependency，有什么问题？

> `get_db()` 与 `get_db_session()` 逻辑几乎重复，容易在 timeout、commit 策略或 instrumentation 上漂移。应保留单一规范依赖，或让一个调用另一个；同时明确 API request UoW 与 worker session factory 的不同使用方式。

### Q70：为什么 chat stream 进入 generator 前主动 `await db.commit()`？

> 它先读取 / 创建 thread、history 和 Memory context，然后结束请求级事务，避免整个模型流期间占用该 transaction。generator 里再用独立 session 保存 PromptExecution 和最终消息。这体现了流式接口需要短事务，而不是沿用普通 request-scoped transaction 到连接结束。

#### 追问：如果创建的是新 thread，`persist_new=False` 又没有先保存怎么办？

> 必须检查 helper 的具体语义和最终 `_persist_stream_chat_turn` 是否在独立事务中完整创建 thread 与消息，并通过重复请求和异常测试保证不会出现返回临时 ID 后持久化失败。面试中不要只看一行 commit 就下结论，要沿调用链验证事实。

### Q71：SSE 在 `done` 之后还发送 `skill` 事件是否合理？

> 协议上可以，但 `done` 通常被客户端理解为整个 stream 完成。当前 BinnAgent 在 done 后运行 vocabulary agent 并继续发 skill 状态，语义容易混乱，也延长连接。可以把前一个事件改成 `message_done`，最终用 `stream_done`；或将 vocabulary agent 变成 durable background job，通过普通事件 / polling 展示。

### Q72：知识上传接口最大的生产风险是什么？

> 除了 learner ownership 需要进一步统一，最大的运行风险是整个 body 入内存、同步磁盘写位于 async endpoint，以及长解析进入 BackgroundTasks。改造顺序应是先认证授权和 streaming upload，再对象存储与独立 parser worker，最后补恶意 PDF 隔离、quota 和生命周期清理。

### Q73：`require_debug_access` 的 Origin 检查能防非浏览器访问吗？

> 不能。Origin 是浏览器安全上下文信号，命令行客户端可以伪造或不发送。它只能是附加约束，真正控制依赖 bearer token、网络隔离、生产默认关闭和审计。

### Q74：为什么 `/health` 固定返回 ok 仍然有价值？

> 它是低成本 liveness，不应执行慢外部检查。但不能把它当 readiness。部署平台应分别配置 liveness 和 readiness，避免数据库不可用时仍持续把新流量发给实例。

### Q75：FastAPI lifespan 中初始化 catalog 失败会怎样？

> `tool_catalog.initialize()` 位于 try 之外，失败会让应用启动失败，这对关键 catalog 是 fail-fast。sandbox policy 查询位于捕获块中，失败会安全降级。两者体现不同 criticality，但需要日志和 readiness 把降级状态显式化。

### Q76：让你用两周改进 BinnAgent FastAPI 层，怎么排序？

第一阶段先收紧安全与契约：

1. 正式认证或受信任 gateway identity，关闭默认本地用户生产路径。
2. 审计所有 learner-owned 路由，统一 `get_current_learner` 和 scoped resource query。
3. 统一错误 envelope、业务 error code 和 request ID。
4. 合并重复 DB dependencies，明确 transaction / commit 规范。

第二阶段解决可靠性和长任务：

5. PDF 改流式上传、临时文件和对象存储。
6. 教材解析迁移到 durable worker，BackgroundTasks 只保留轻任务。
7. SSE 加 disconnect、heartbeat、事件 ID 和清晰 done 语义。
8. 多 worker Tool Catalog 使用共享 revision / invalidation。

第三阶段补生产验证：

9. 增加 readiness、DB pool、event loop lag 和 stream metrics。
10. 使用 lifespan-aware ASGI tests、真实 Postgres integration、proxy 下 SSE E2E。
11. 锁定 FastAPI / Starlette / Pydantic 兼容版本，建立升级测试矩阵。

## 17. “深入用过”才容易回答的快问快答

### 1. `async def` 里调用同步 requests 会怎样？

阻塞 event loop；应使用异步客户端、线程池或独立 worker。

### 2. 普通 `def` endpoint 在哪里执行？

通常由 Starlette 在线程池执行，但线程池容量有限。

### 3. AsyncSession 能否被 `asyncio.gather()` 的多个任务共享？

不能，Session 不是并发安全对象。

### 4. `flush()` 是否提交事务？

不提交，只把 SQL 发到当前事务。

### 5. Pydantic 校验 UUID 是否代表有权限？

不代表，授权必须基于可信身份和资源关系。

### 6. response model 只有文档作用吗？

不是，还能验证和过滤输出，减少敏感字段泄露。

### 7. `Depends` 默认是否缓存同一依赖？

在同一请求依赖图中通常会缓存，可显式关闭，但要理解资源语义。

### 8. `BackgroundTasks` 是任务队列吗？

不是，它运行在同一进程，重启可能丢失。

### 9. `app.state` 是否跨 worker 共享？

不共享，每个进程一份。

### 10. ASGITransport 是否等于真实部署测试？

不等于，不覆盖 socket、proxy、worker、TLS 等，而且要显式注意 lifespan。

### 11. SSE 是否适合客户端向服务端频繁发消息？

不适合，它主要是单向推送；双向实时交互考虑 WebSocket。

### 12. StreamingResponse 能否长期持有 request transaction？

技术上可能，但通常不应，容易占用连接并放大清理风险。

### 13. CORS 是认证吗？

不是，它是浏览器跨域策略，非浏览器客户端不受约束。

### 14. 先查不存在再 insert 是否能防重复？

不能消除竞态，必须有数据库唯一约束或幂等键。

### 15. 多 worker 能否使用内存限流器？

只能限制单进程，不能形成全局 quota。

### 16. `pool_pre_ping` 能否解决所有数据库断连？

不能，只能在借出连接时检测部分失效连接，还需 timeout、retry 和 pool 监控。

### 17. liveness 能否依赖模型服务？

通常不应，否则模型短故障会导致 API worker 被反复重启。

### 18. 上传文件只检查扩展名够吗？

不够，还需大小、内容识别、解析隔离和存储边界。

### 19. dependency cleanup 失败会怎样？

它仍是请求失败的一部分，应被异常处理和观测；不能假设 endpoint return 就一定成功提交。

### 20. FastAPI 会自动解决业务幂等吗？

不会，需要 API、service 和数据库共同设计。

## 18. 容易让面试官扣分的回答

### “FastAPI 快是因为用了 async。”

太笼统。要说明异步只改善 I/O 等待，阻塞库和 CPU 任务仍是瓶颈。

### “所有接口都写 async def 就行。”

错误。真正调用链必须异步，阻塞操作要隔离。

### “Pydantic 已经保证接口安全。”

错误。它主要保证数据结构，不能替代认证、授权、限流和业务不变量。

### “每个请求一个 Session，就不会有事务问题。”

忽略了外部调用、显式 commit、长 stream、并发写和 commit 失败。

### “BackgroundTasks 会在后台可靠执行。”

它不是 durable queue，进程退出会丢失。

### “加几个 Uvicorn workers 就能水平扩容。”

进程内 catalog、cache、限流和 InMemory state 会分裂，还要考虑 DB 连接总数。

### “401 和 403 都差不多。”

说明没有真正做过认证授权边界。

### “SSE 就是 yield 字符串。”

忽略了协议格式、代理缓冲、heartbeat、断开、取消和重连。

### “测试用 AsyncClient 通过就等于生产没问题。”

ASGITransport 不覆盖真实网络、proxy、worker 和 lifecycle 全部行为。

### “BinnAgent 当前已经是生产认证。”

与代码不符。当前 header + local fallback 明确是开发身份方案。

## 19. 五分钟项目讲稿

> BinnAgent 的 FastAPI 层不仅承载 CRUD，还连接 LangGraph 学习流程、模型流式输出、教材上传解析、Memory 和 Tool Catalog。我把路由作为 Web adapter：Pydantic 定义输入输出契约，Depends 注入 AsyncSession、ModelRouter 和当前 learner，复杂业务进入 orchestrator 或 service。
>
> 数据库使用 SQLAlchemy AsyncSession。当前 request dependency 默认成功 commit、异常 rollback，这让普通写接口简洁，但我也认识到它不是万能事务模型：GET 也会 commit，部分 endpoint 有显式 commit，长流不能一直持有 request transaction。聊天 SSE 在进入 generator 前主动结束原事务，流内使用短 session 完成 PromptExecution 和消息持久化，这是为了避免连接池被长流占满。
>
> 在安全上，learner 路由通过 `get_current_learner` 依赖做 ownership，子资源查询还需要同时过滤 learner_id。当前 `x-user-id` 和固定 local user 只是开发身份 shim，不能当生产认证；生产必须验证 token 或可信 gateway 身份，并关闭 unclaimed learner fallback。
>
> 对异步我不会简单说全部使用 async。asyncpg、httpx 和 Redis 等 I/O 适合 async，但当前 PDF 上传一次读取整个 body，并在 async endpoint 里同步写文件；长教材解析又使用 BackgroundTasks。这在并发和重启下都有风险，应该改成流式 upload + 对象存储 + durable parser worker。
>
> 生命周期方面，应用启动初始化 Tool Catalog，关闭时释放 Redis、模型客户端和 observability。需要注意多 worker 中 app.state 和模块单例都不共享，所以 catalog enable / refresh 要有共享 revision 和失效通知。健康检查也应拆 liveness、readiness 和依赖诊断。
>
> 测试上我会用 ASGITransport 做快速 contract test，用 dependency override 注入 fake provider，但认证、事务、migration 和 streaming 还要用真实 Postgres与 lifespan-aware integration；SSE 必须在真实 proxy 下测试 buffering、断线和 heartbeat。我的理解是 FastAPI 提供了优秀的 ASGI 和依赖骨架，但生产正确性仍来自清晰事务、授权、幂等、资源生命周期和可观测性。

## 20. 面试前最终自检

你应该能不看文档回答：

- Uvicorn、ASGI、Starlette、FastAPI、Pydantic 的分工。
- `async def`、线程池、CPU 密集任务的边界。
- Depends 的依赖图、缓存和 yield cleanup。
- AsyncSession 为什么不能并发共享，flush 与 commit 的区别。
- 请求级事务在 streaming 和外部 LLM 调用中的风险。
- 认证、learner ownership 和 scoped resource query 的区别。
- BackgroundTasks 为什么不是 durable queue。
- SSE 的 buffer、heartbeat、disconnect、event ID 和最终一致性。
- lifespan、app.state 和多 worker 的关系。
- ASGITransport、dependency override 和真实 E2E 的不同覆盖范围。
- BinnAgent 当前身份、PDF 上传、后台解析和健康检查的真实边界。
- 如果用两周升级 FastAPI 层，你的优先级和验证方法。

## 21. 相关文档

- [AI Agent、Tools 与 Function Calling 面试指南](AI-Agent-Tools-Function-Calling面试指南.md)
- [LangGraph 深度面试题、参考回答与压力追问](LangGraph深度面试题与追问.md)
- [Agent Runtime / Harness Interview Brief](agent-runtime-harness.md)
- [Learner Scope Audit](../security/learner_scope_audit.md)
- [Cloud Deployment](../deployment-cloud.md)
- [Web Frontend](../web-frontend.md)

