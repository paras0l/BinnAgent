我已按当前仓库做了一版“功能 × 页面 × 归属 × UI 验收点”的清单，并持续把自查结果回填到前端实现。

最近整改进展：

- Header / 学习中心已按 issue #33 收敛为 `AI对话 / 探索 / 学习中心`，学习设置进入用户菜单；学习设置弹层已补 dialog 语义、ESC 关闭、焦点恢复、Tab 循环和恢复默认二次确认。
- `ChatContainer` / Chat 输入区已补统一 `Button` / `IconButton`、聊天输入 `name` / `autocomplete` / `aria-live`、typing reduced-motion、消息 hover 反馈和侧栏 overscroll 控制；移动端历史对话 / 学习状态侧栏已补遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环；`LoginPage` 表单字段与能力卡 hover 状态已补齐。
- Dashboard Profile / Records 已补能力雷达、掌握度分布、薄弱点排行、活动热力、每日完成趋势、正确率与复习负荷趋势。
- `DashboardPage` 词汇工作区已补统一练习入口卡、词汇搜索/新增表单 `name` / `autocomplete` / focus-visible 状态，词汇行改为真实按钮入口加独立删除操作；Dashboard 共享统计卡、学习目标进度条和词汇复习卡已清理伪按钮与 `transition-all`。
- `VocabularyDetailPage` 已补生成-回填-保存四步 stepper，生成指令、HTML 回填、个人词卡和构词笔记表单已统一 `name` / `autocomplete` / focus-visible 与省略号占位文案；沉浸阅读已补 dialog 语义、ESC 关闭、焦点恢复和 Tab 循环。
- `VocabularyPracticePage` 继续保持 TaskShell，一屏任务页已清理 `transition-all`，核心按钮补齐 `type` / focus-visible，拼写答案和自定义数量输入补齐 `name` / `autocomplete` / `inputMode`；总结页已补答对率环、本组结果分布和复习负荷条。
- `AddExerciseForm` / `ExerciseRenderer` / `ExerciseSessionDialog` 已补练习表单 `name` / `autocomplete` / focus-visible、选项 pressed/focus 状态、提交/生成 loading 文案、练习进度条、弹层内部滚动、ESC 关闭、焦点恢复和 Tab 循环，使教材练习入口更接近 TaskShell。
- `DailyLessonRuntimeDialog` 已改为固定头部、内部滚动内容和固定底部 ActionBar，补选项 pressed/focus、提交 loading、ESC 关闭、焦点恢复和 Tab 循环。
- `ExplorePage` 搜索框已补 `name` / `autocomplete` / `aria-label` / focus-visible 和省略号占位文案，能力卡和收藏按钮补齐 hover / focus-visible / disabled 语义。
- `WordPartsPage` 的“我的掌握”已补整体掌握堆叠条、prefix/root/suffix 掌握条和练习次数趋势；拆词练习答案已补展开/收起动效、`aria-expanded` 和提示计数 live 状态；重置本地记录已加确认弹窗。
- `ReadingWorkshopPage` 的复盘页已补关键词频次条、句子难度热力图、阅读流程进度和正文高亮覆盖。
- `WorkspaceTabs`、`FilterChip` 已补 `type="button"`、pressed、focus-visible 状态；相关页面移除本轮发现的 `transition-all`。
- `WritingPhrasebookPage` 的主操作、详情操作、导入操作、练习推进和编辑抽屉关键按钮已改用统一 `Button` / `IconButton`；练习检测页已补进度条、题型分布和已填写统计。
- `WritingPhrasebookPage` 的练习检测页已补移动端句式列表抽屉，具备遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环；写作调用页已补写作位置覆盖、句式功能分布和难度分布；编辑抽屉表单已补 `name` / `autocomplete` / `inputMode`、overscroll、dialog 语义、ESC 关闭、焦点恢复、Tab 循环和删除确认。
- `PronunciationPage` 的 Minimal Pairs / Records 已从占位页升级为可用工作区：支持易混音组选择、左右词播放、对比句练习、自评记录、音标完成度、shadowing 自评分布、最小对立音清晰率和练习概览。
- `GrammarPage` 已补知识点分类矩阵、已打开/已学习/已缓存/喜爱状态卡、难度掌握分布和生成链路状态卡；预览页 HTML 输入可折叠，沉浸阅读已补 dialog 语义、ESC 关闭、焦点恢复和 Tab 循环；重新生成、清空 HTML、删除目标网站已接入确认弹窗，关键表单字段补齐 `name` / `autocomplete` / focus-visible。
- `KnowledgeBasePage` 已补移动端教材目录 / 学习概览抽屉，教材上传 / 课程学习 / 练习弹层具备遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环；教材学习概览图表已覆盖教材单元、知识点、RAG 片段、待校对、单元掌握堆叠条、知识点类型覆盖、教材路径进度、解析与索引覆盖。
- `EpisodeDebugPage` / Dev Console Graph Runs 已补 Graph Run Overview、Node Waterfall、Event Rhythm、Tool Latency 和 Verification Map，让 trace 先图形化扫读，再下钻表格/JSON。
- Dev Console `RAG Debug` 已补语义化检索表单、Top-K score bar、score bucket、chunk source distribution 和 retrieval mode mix，能先扫召回质量再看 chunk / raw JSON。
- `ReadingWorkshopPage` 已补移动端材料历史 / 精读句子列表抽屉，具备遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环；复盘页新增语法卡点分布图；本轮触及的阅读表单字段补齐 `name` / `autocomplete` / focus-visible 和省略号占位文案。
- `PronunciationPage` 的音标详情已补移动端 bottom sheet，具备遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环；Shadowing 工作区已补移动端句子列表抽屉，当前句已补原句播放状态、节奏条、重音词可视化、本地麦克风录音、实时波形、回放和重录。

# 1. 用户端功能总账

| 功能域         | 当前可用功能                                                 | 页面体现                                       | 当前 UI 状态                                                                                               | 后续确认重点                                                           |
| ----------- | ------------------------------------------------------ | ------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| 登录与学习者空间    | 昵称/邮箱登录，创建或恢复 learner，本地保存 learner 信息                  | `LoginPage`                                | 左侧产品说明 + 右侧登录卡片；提交时有 loading spinner；错误 toast；表单字段已补 `name` / `autocomplete`，能力卡已有 hover 反馈。                                                         | 后续继续统一视觉 token，并细化移动端上下布局。                  |
| AI 对话       | 流式聊天、取消生成、会话历史、记忆面板、Skill 状态条、Agent Skill 退出           | `ChatPage` / `ChatContainer`               | 左侧会话栏、中间聊天区、右侧记忆栏；History 和 Memory 可折叠；输入区和图标操作已接入统一 Button/IconButton，streaming/typing 有 live region 与消息 hover；移动端历史 / 学习状态侧栏具备遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环。                                                                | 后续继续强化更细的 streaming 光标/typing 动效。     |
| 探索能力中心      | 能力搜索、分类筛选、收藏、推荐卡、点击启动能力、跳转专项页面或进入 Chat Skill           | `ExplorePage`                              | FeatureHero + 推荐 + 分类 chip + feature card；能打开 Grammar、Reading、Writing、WordParts、VocabularyDetail 等子页面；搜索框和能力卡 hover/focus/favorite 状态已补基础规范。 | 后续继续加强推荐分组折叠、能力启动 loading 骨架和收藏反馈动画。                    |
| 学习中心首页      | 今日学习路径、学习状态、活动日历、学习路线、词汇入口、个人学习概览                      | `DashboardPage`                            | Home / vocabulary / profile / records 内部 workspace；有 activity calendar、路线卡、状态条；Profile / Records 图表已补齐；共享统计卡、目标进度和复习卡片已补真实按钮/focus/显式 transition。                        | 后续继续接真实 mastery/error aggregation，减少轻量估算。                            |
| 词汇管理        | 添加词、复习队列、删除、跳转新词/复习/拼写练习、只读词条详情                        | `DashboardPage` 内 Vocabulary Workspace     | 词汇列表、添加表单、统计、练习入口；练习入口卡、搜索/新增表单、词汇行和复习卡键盘/focus 状态已统一。                                                                                     | 后续补批量操作、复习优先级图示和更完整的列表 loading skeleton。                                |
| 教材知识库       | 上传教材、解析/ingest 状态、教材结构、单元学习、练习任务、解析校对、来源切换、学习概览图表             | `KnowledgeBasePage`                        | 学习者端保留“今日单元 / 练习任务”两个 workspace；左右有 CurriculumRail 和 ContextPanel，移动端以带遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环的抽屉打开；上传教材弹层已补同样的键盘与焦点行为；主区已补教材学习概览图表。                              | 后续补更细的 learner-facing 单元复盘图示。                              |
| 每日教材题 / 单元题 | Daily lesson、单题提交、反馈、mastery/recommendations、教材练习题启动   | `KnowledgeBasePage` 弹层与 exercise workspace | DailyLesson modal 展示题目、选项/文本作答、反馈、推荐；共享 `ExerciseRenderer` 已补进度条、选项状态、提交 loading 与弹层内部滚动；DailyLesson、课程学习和练习弹层均已补 ESC 关闭、焦点恢复和 Tab 循环。                                                                  | 后续补推荐完成后的复盘图示。                             |
| 词汇练习        | 新词、复习、拼写三种模式；TTS；英/美音；键盘快捷键；提示；构词信息；总结页                | `VocabularyPracticePage`                   | practice 阶段使用 h-dvh、固定 top/bottom、中间滚动；底部 action bar 固定；核心按钮、进度条和拼写输入已补 focus/name/autocomplete 与显式 transition；summary 已补答对率、结果分布和复习负荷图。                                               | 这是 TaskShell 标准样板；后续补跨 session due queue 分布和拼写错误热力图。                    |
| 词汇详解        | 输入词条、生成 prompt、外部模型回填 HTML、安全预览、沉浸阅读、加入词库、个人词卡编辑、练习接入  | `VocabularyDetailPage`                     | 四个 workspace：词条输入 / 生成指令 / 回填预览 / 词卡沉淀；已补生成-回填-保存 stepper、关键表单 focus/name/autocomplete 和沉浸阅读弹层焦点管理。                                                                | 后续补个人词卡状态 timeline、保存前 diff 和更细的 HTML 解析质量提示。                        |
| 发音训练        | 音标卡、搜索/筛选、播放、音素高亮、完成进度、今日 5 个、随机练、影子跟读、自评记录、最小对立音练习、训练记录图表            | `PronunciationPage`                        | workspace 包括音标训练、影子跟读、最小对立音、训练记录；音标详情移动端 bottom sheet、Minimal Pairs / Records 和 Shadowing 列表抽屉已有可用交互和本地记录图表。                                                   | 后续补自动跟读评分。 |
| 影子跟读        | 句子列表、分块朗读、重音词、语调提示、练习建议、本地录音、回放、自评、本地记录                        | `PronunciationPage` Shadowing Workspace    | 左侧句子列表 + 右侧当前句详情；提示可隐藏；移动端句子列表以带遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环的抽屉打开，当前句提供原句播放、节奏条、重音词提示、本地麦克风录音、实时波形和录音回放。                                                                                | 后续补自动评分和 bottom sheet 动画。                                  |
| 语法微课        | 语法知识点库、生成 prompt、跳转目标 AI、HTML 缓存、回填预览、沉浸阅读、目标网站设置、练习接入、知识点状态图表 | `GrammarPage`                              | 四个 workspace：知识点 / 生成指令 / 预览回填 / 目标设置；已补分类矩阵、状态卡、难度掌握分布、生成链路状态卡、预览输入折叠和沉浸阅读弹层焦点管理。                                                                 | 后续继续补跨 session 练习正确率趋势和更完整的 stepper。                        |
| 精读与泛读       | 材料输入、自动标题建议、历史材料、泛读任务、关键词、精读拆句、语法卡点、复盘沉淀               | `ReadingWorkshopPage`                      | 四个 workspace：材料输入 / 泛读模式 / 精读模式 / 沉淀复盘；材料历史和精读句子列表已支持移动端抽屉，具备遮罩、dialog 语义、ESC 关闭、焦点恢复和 Tab 循环；复盘页已有关键词频次、句子难度热力图、语法卡点分布、阅读流程进度和正文高亮覆盖；精读可跳到 GrammarPage。                                              | 后续继续加强正文逐句高亮交互。                            |
| 词根词缀        | 方法入门、词根词缀库、搜索/筛选、拆词练习、提示/答案、掌握状态、本地进度                  | `WordPartsPage`                            | 四个 workspace：方法入门 / 词根词缀库 / 拆词练习 / 我的掌握；进度页已有整体掌握堆叠条、类型掌握条和练习次数趋势；拆词答案 reveal 已有展开动效和可访问状态。                                                               | 后续继续清理词根卡手写交互状态，并补更强的词根关系图。             |
| 写作好句        | 句式收藏、搜索/筛选、更多筛选折叠、新增/编辑 drawer、导入好句、候选收藏、练习检测、写作调用     | `WritingPhrasebookPage`                    | 四个 workspace：收藏馆 / 导入好句 / 练习检测 / 写作调用；编辑通过 drawer，具备 dialog 语义、ESC 关闭、焦点恢复和 Tab 循环；关键按钮已接入统一 Button/IconButton，删除有确认；练习页已有进度、题型分布图、移动端句式列表抽屉、写作位置覆盖、句式功能分布和难度分布。                                                     | 后续补真实 attempt 正确率趋势和 drawer/bottom sheet 动画。         |
| 学习记录与画像     | 活动热力、每日完成趋势、正确率/复习负荷趋势、能力雷达、掌握度分布、薄弱点排行、推荐原因            | `DashboardPage` profile / records          | 用户端学习中心内部二级视图；只展示学习者能理解的记录和画像，不展示 raw memory/debug evidence。                              | 后续可接入更真实的 mastery/error aggregation 数据源，替换当前轻量估算图表。                         |
| 学习记忆控制      | 查看记忆、整理、导出、重置计划、开关记忆设置、编辑/删除/禁用记忆、证据展示                 | `MemoryCenterPage`                         | 仅由 Dev Console 懒加载；页面本身使用 FeatureHero、ReasonCard、EvidencePanel、ConfirmDialog。                         | 不回到用户端一级导航；用户端只保留学习记录和学习者画像。                                      |

---

# 2. 用户端页面清单

## A. 当前主入口页面

| 页面                       | 当前入口                                        | 页面职责                      | 必须确认的 UI 点                                 |
| ------------------------ | ------------------------------------------- | ------------------------- | ------------------------------------------ |
| `LoginPage`              | 未登录时展示                                      | 创建/恢复学习空间                 | 登录卡、产品说明卡、表单 focus/loading/error、能力卡 hover、移动端上下布局   |
| `ChatPage`               | 主导航 AI 对话                                   | Agent 对话、Skill 执行、会话/记忆辅助 | 左右栏折叠、统一按钮、消息 hover、streaming/typing live 状态、移动端 drawer |
| `ExplorePage`            | 主导航 探索                                      | 所有能力的入口与推荐                | 能力卡 hover、分类 chip、收藏、推荐原因、启动 loading       |
| `DashboardPage`          | 主导航 学习中心                                    | 学习首页、词汇、画像、记录             | 首页图表、热力图、学习路线、内部 workspace 切换              |
| `KnowledgeBasePage`      | 学习中心进入 Daily Learning                       | 教材学习工作台                   | CurriculumRail / ContextPanel 折叠，四工作区布局，教材练习和 DailyLesson 弹层内部滚动/底部操作固定    |
| `VocabularyPracticePage` | 学习中心/知识库/词汇入口                               | 新词、复习、拼写正式任务流             | TaskShell、固定底部操作区、反馈动画、键盘操作                |
| `PronunciationPage`      | Explore 或 AppTab                            | 发音训练                      | IPA 网格、详情 panel、音频状态、Shadowing 交互          |
| `GrammarPage`            | Explore / Reading / Knowledge grammar topic | 语法微知识点                    | 生成链路、HTML 回填、沉浸阅读、练习模块                     |
| `VocabularyDetailPage`   | Explore / VocabularyPractice readonly       | 词汇详解与词卡沉淀                 | 生成-回填-保存 stepper、词卡编辑、构词分析                 |
| `ReadingWorkshopPage`    | Explore                                     | 精读/泛读                     | 阅读文本高亮、句子列表折叠、复盘图示                         |
| `WordPartsPage`          | Explore                                     | 词根词缀                      | 方法卡、词库筛选、拆词练习、掌握图表                         |
| `WritingPhrasebookPage`  | Explore                                     | 写作表达资产                    | drawer、筛选折叠、导入候选、练习检测、写作调用                 |

当前 `src/pages` 下还存在 `MemoryCenterPage` 和 `EpisodeDebugPage`，但从 `App.tsx` 的用户端渲染逻辑看，它们不是普通用户主路径页面；Dev Console 会懒加载这两个页面用于调试/控制。

---

## B. 用户端页面的布局规则

现有设计系统已经写得比较明确：标准功能页应使用 `PageShell`、`FeatureHero`、`SurfaceCard`、`WorkspaceTabs`；推荐要展示原因，证据/来源要有统一结构；删除/清空/否认长期记忆必须有确认；空状态必须给下一步动作。

任务页规则也已经明确：正式练习阶段应使用固定视口，TopBar 和 ActionBar 固定，中间内容内部滚动，底部只放提交、评分、下一题等关键推进动作；13 英寸笔记本和移动端都要保证关键操作首屏可见。

---

# 3. Dev Console 功能与页面清单

Dev Console 路由当前定义了 12 个主要页面：Learners、Recent Episodes、Graph Runs、Textbook Parsing、Memory Debug、Tool Registry、Tool Call Records、Evidence Debug、RAG Debug、Prompt Debug、VerificationReport、Simulation Report。

| Dev Console 页面             |                  路由 | 当前功能                                                                                                | 页面体现                                                             | 后续 UI 重点                                          |
| -------------------------- | ------------------: | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------- |
| Learners                   |     `/dev/learners` | 搜索 learner、设置当前 learner、查看 episodes                                                                 | 搜索表单 + learner 表格 + actions。                                     | 大表格移动端改 card；增加 learner 指标图。                      |
| Recent Episodes            |     `/dev/episodes` | 按 learner/status/source/entrypoint/limit 过滤 episodes，打开 trace                                       | 过滤表单 + episode 表格。                                               | 加状态分布、失败原因、运行耗时趋势。                                |
| Graph Runs / Episode Trace |   `/dev/graph-runs` | 查看 Episode Summary、Graph/Checkpoint、Timeline、Tool Calls、Prompt Executions、Verification、EvidenceRefs | `EpisodeDebugPage` 使用 full PageShell + 左主右侧栏；已补 Graph Run Overview、Node Waterfall、Event Rhythm、Tool Latency 和 Verification Map。                    | 后续继续加更完整 DAG、节点耗时 waterfall、筛选和 raw JSON 折叠策略。              |
| Textbook Parsing           |    `/dev/textbooks` | 查看教材 source、解析状态、quality、parser runs、review queue、evidence browser                                  | sources 表格 + detail + review queue + parser run panels。          | 解析治理需要漏斗图、质量雷达、review 队列优先级。                      |
| Memory Debug               |       `/dev/memory` | 记忆查看、整理、导出、设置开关、控制记忆项                                                                               | 复用 `MemoryCenterPage`。                                           | Dev 保留 raw/evidence；用户端不暴露 Memory Center，只展示记录/画像。 |
| Tool Registry              |        `/dev/tools` | 查看 `/api/tools` 返回的 ToolSpec、schema                                                                 | Dev Console App 内 fetch tools 并渲染 cards/schema。                  | Schema 需要可折叠 JSON、搜索、分组、调用频率。                     |
| Tool Call Records          |   `/dev/tool-calls` | 按 episode 查看工具调用记录                                                                                  | 读取 `/api/runtime/episodes/{episodeId}`，展示 tool calls 与 raw JSON。 | 增加 latency bar、status badge、错误聚合。                 |
| Evidence Debug             |     `/dev/evidence` | evidence resolve 调试                                                                                 | 表单请求 `/api/evidence/resolve`。                                    | Evidence 链路要图形化：来源 → 使用位置 → 检查结果。                 |
| RAG Debug                  |          `/dev/rag` | RAG search 调试、chunk/score 展示                                                                        | 请求 `/api/debug/rag/search`；已补语义化检索表单、Top-K score bar、score bucket、chunk source distribution、retrieval mode mix 与 chunk cards。                  | 后续继续补 query 版本对比、召回覆盖率和 chunk diff。                         |
| Prompt Debug               |      `/dev/prompts` | prompt render 调试                                                                                    | 请求 `/api/prompts/{promptId}/render`。                             | 需要变量编辑器、diff、schema validation 状态。                |
| Verification Report        | `/dev/verification` | episode verification report 查看                                                                      | 请求 `/api/runtime/episodes/{id}/verification`。                    | 加 checks pass/fail 图、severity 分组。                 |
| Simulation Report          |   `/dev/simulation` | simulation scenarios 与最新 report                                                                     | 加载 `/api/debug/simulation/scenarios` 与最新 report。                 | 加场景覆盖矩阵、失败类型趋势、回归对比。                              |

Dev Console Shell 目前已有桌面左侧导航，移动端改为 select；但大部分内容还是表格和 raw JSON，需要后续加折叠、图表和可视化链路。

---

# 4. 组件交互验收清单

## 4.1 所有用户端组件都必须有状态响应

| 组件类型                 | 必须具备状态                                                                            |
| -------------------- | --------------------------------------------------------------------------------- |
| Button / IconButton  | default、hover、pressed、focus-visible、loading、disabled、success、danger               |
| Card / FeatureCard   | hover elevation、轻微 translate、selected ring、active background、disabled/coming soon |
| FilterChip / Tabs    | hover、active、keyboard focus、横向滚动阴影、选中切换动效                                         |
| List Row / Table Row | hover highlight、selected、loading skeleton、empty state                             |
| Drawer / Side Panel  | open/close 动画、ESC 关闭、遮罩、焦点管理、移动端全宽                                                |
| Audio / TTS 控件       | playing、paused、error、unsupported、active highlight、波形/pulse                        |
| Task Feedback        | correct、wrong、partial、retry、next available、summary completed                      |
| Forms                | focus、validation、saving、saved、error、dirty state、reset confirm                     |

按钮层级已经在设计系统中定义：Primary 用于保存/确认/开始练习，Secondary 用于复制/新增/编辑，Ghost/Icon 用于收藏/归档/关闭，删除类必须有 danger hover；每页最多一个最强主操作。

---

## 4.2 动效规则

| 场景                | 建议动效                                                 |
| ----------------- | ---------------------------------------------------- |
| 卡片 hover          | `translateY(-2px)` + shadow + border color，120–180ms |
| tab/workspace 切换  | 内容 fade/slide，150–220ms                              |
| drawer/side panel | 右/左滑入，250–320ms，带 overlay fade                       |
| 练习正确              | 轻微 scale + success glow；拼写正确可保留现有 confetti           |
| 练习错误              | 轻微 shake + letter diff 高亮，不要刺眼                       |
| TTS/播放            | icon pulse、当前词/音素 highlight、播放结束 fade                |
| 进度变化              | progress bar width transition，300–500ms              |
| 长表格加载             | skeleton row，不要整页闪烁                                  |
| Dev trace         | timeline/waterfall 渐进展开                              |

---

# 5. 图表与可视化清单

用户特别强调“要有丰富的图表表现形式”，建议按功能域补齐：

| 页面/域                   | 推荐图表                                                                               |
| ---------------------- | ---------------------------------------------------------------------------------- |
| Dashboard 首页           | 学习活动 heatmap、7/30 天学习趋势线、今日任务完成环、技能掌握雷达图、复习负荷柱状图                                   |
| Dashboard Profile      | vocabulary / grammar / reading / writing / pronunciation 五维能力雷达、薄弱点排行、最近错因堆叠条      |
| Dashboard Records      | session timeline、学习事件流、每日完成量、正确率趋势                                                 |
| KnowledgeBase          | 教材目录树、单元路径进度、单元掌握堆叠条、知识点类型覆盖、解析与索引覆盖、RAG 片段和待校对指标已落地；后续补 parser quality radar / review funnel            |
| VocabularyPractice     | TaskShell 固定操作区、拼写输入状态、summary 答对率环、本组结果分布和复习负荷条已落地；后续补跨 session 遗忘曲线、due queue 分布、拼写错误热力图、掌握度趋势、词性/来源分布                                            |
| VocabularyDetail       | 生成-回填-保存 stepper、构词拆解编辑和沉浸阅读弹层焦点管理已落地；后续补词义结构树、个人词卡状态 timeline 和保存前 diff                                                        |
| Pronunciation          | IPA matrix、音素分类网格、音标详情 bottom sheet、音标完成度、shadowing 自评分布、shadowing 练习次数趋势、最小对立音清晰率、句子节奏/重音条、Shadowing 列表抽屉、本地录音、实时波形和回放已落地；后续补自动评分                                 |
| Grammar                | 知识点分类矩阵、已学/收藏/缓存状态图、难度掌握分布、生成链路状态、预览输入折叠和沉浸阅读弹层焦点管理已落地；后续补跨 session 练习正确率趋势                                                        |
| ReadingWorkshop        | 词数/句数/耗时指标卡、句子难度 heatmap、关键词频次、语法卡点分布、阅读流程进度和正文高亮覆盖已落地；后续补正文逐句高亮交互                                              |
| WordParts              | prefix/root/suffix 掌握度堆叠条、练习次数趋势、拆词答案 reveal 展开动效已落地；后续补词根关系图                                             |
| WritingPhrasebook      | 练习进度、题型分布、待填写数量、练习句式列表抽屉、句式功能分布、难度分布和写作位置 coverage 已落地；后续补真实练习正确率趋势                                              |
| Dev Console Graph Runs | Graph Run Overview、事件 rhythm、node waterfall、tool latency、verification pass/fail donut 已落地；后续补完整 DAG 和节点耗时 waterfall |
| Dev Console Textbook   | parser quality radar、review queue funnel、source status stacked bar                 |
| Dev Console RAG        | Top-K score bar、score bucket、chunk source distribution、retrieval mode mix 已落地；后续补 score scatter、query 版本对比和召回覆盖率                                  |
| Dev Console Simulation | scenario coverage matrix、失败类型趋势、版本对比图                                              |

---

# 6. 折叠与响应式布局清单

| 页面                 | 桌面布局                                    | 平板布局            | 移动端布局               | 必须折叠的区域                                 |
| ------------------ | --------------------------------------- | --------------- | ------------------- | --------------------------------------- |
| Chat               | 左历史 + 中聊天 + 右记忆                         | 右记忆 drawer      | 单列聊天 + 双 drawer     | history、memory                          |
| Explore            | Hero + 推荐 + 卡片网格                        | 两列卡片            | 单列卡片                | category/filter、推荐说明                    |
| Dashboard          | 统计 + 路线 + heatmap                       | 两列              | 单列                  | 学习路线详情、记录筛选                             |
| KnowledgeBase      | 左 CurriculumRail + 中内容 + 右 ContextPanel | 左右 panel drawer | 单列 + bottom/drawer  | CurriculumRail、ContextPanel、source list |
| VocabularyPractice | 固定 TaskShell                            | 双区压缩            | 单列任务 + 底部 action    | support panel、hint/details              |
| Pronunciation      | 音标网格 + sticky detail                    | detail drawer   | detail bottom sheet + shadowing drawer | detail panel、shadowing list             |
| Grammar            | 左生成/输入 + 右预览                            | 预览下移            | 单列 stepper          | prompt preview、HTML input               |
| ReadingWorkshop    | 左/右双栏                                   | 侧栏折叠            | 单列                  | sentence list、history                   |
| WordParts          | 主内容 + 右详情                               | 详情下移            | 单列                  | filters、part detail                     |
| WritingPhrasebook  | 左列表 + 右详情                               | 详情下移            | 单列 + drawer         | filters、practice list、edit drawer       |
| Dev Console        | 左 nav + 内容                              | nav select      | 表格转 card            | sidebar、raw JSON、filters                |

---

# 7. 视觉统一清单

当前设计系统的方向是“功能优先的英语学习工作台”，不是所有页面完全一样，而是统一外壳、组件、状态反馈、推荐原因和证据表达。

需要统一的内容：

| 项        | 统一要求                                              |
| -------- | ------------------------------------------------- |
| 页面外壳     | 标准学习页统一 `PageShell`；复杂工作台可用 `variant="full"`      |
| 顶部说明     | 功能页统一 `FeatureHero`，只放 1–2 个关键 action             |
| 工作区      | 复杂功能统一 `WorkspaceTabs`，不要把所有工具堆在一屏                |
| 卡片       | 统一 `SurfaceCard`，减少裸 `bg-white border slate` 手写样式 |
| 按钮       | 统一 Button/IconButton 语义层级                         |
| Chip/Tag | 筛选 chip 与只读 tag 分开样式                              |
| 状态       | Loading/Error/Empty/StatusBanner 统一               |
| 推荐解释     | ReasonCard / EvidencePanel 统一                     |
| 删除/重置    | ConfirmDialog 统一                                  |
| 文案       | 页面不显示内部设计原则，只显示学习任务直接相关文案                         |

---

# 8. 当前明显缺口

1. **复杂页面折叠策略基本收口**：Chat 移动侧栏、Knowledge 教材目录 / 学习概览、Reading 材料历史 / 精读句子列表、Pronunciation 音标详情 / Shadowing 句子列表、Grammar / VocabularyDetail 沉浸阅读、Writing 练习句式列表、DailyLesson 与 Writing 编辑抽屉已补 ESC / 焦点恢复 / Tab 循环；剩余工作主要是 drawer / bottom sheet 的细微入场动效统一。
2. **交互状态仍需继续归一**：`WorkspaceTabs`、`FilterChip`、`ChatContainer`、`LoginPage`、`ExplorePage`、`DashboardPage` 词汇区与共享卡片、`AddExerciseForm` / `ExerciseRenderer`、`VocabularyPracticePage`、`GrammarPage`、`KnowledgeBasePage`、`ReadingWorkshopPage`、`WritingPhrasebookPage` 关键路径已补基础状态，但部分页面还有手写 button class；hover、focus、loading、disabled、danger 状态需要继续清理。
3. **图表数据源仍可增强**：Dashboard、Grammar、KnowledgeBase、Pronunciation、Reading、WordParts、WritingPhrasebook 已补一批图表，但部分指标仍是基于 summary/localStorage/当前 session 的轻量估算，后续应接入更完整 mastery/error aggregation。
4. **Dev Console 后续优化暂停**：Graph Runs / Episode Trace 与 RAG Debug 已补首层可视化；按当前范围不继续推进 Dev Console 的 Textbook Parsing、Simulation、Verification 或 RAG 深化，保留为后续可选事项。
5. **Pronunciation 仍缺自动评分闭环**：Minimal Pairs / Records 已不是占位，音标详情和 Shadowing 列表已有移动端弹层交互，Shadowing 已补原句播放态、节奏/重音可视化、本地录音、实时波形、回放和练习次数趋势；自动跟读评分仍需要后端/STT 能力支持。
