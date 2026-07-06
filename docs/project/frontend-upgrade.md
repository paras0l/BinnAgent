我已按当前仓库做了一版“功能 × 页面 × 归属 × UI 验收点”的清单；这次只是梳理，没有改代码。

# 1. 用户端功能总账

| 功能域         | 当前可用功能                                                 | 页面体现                                       | 当前 UI 状态                                                                                               | 后续确认重点                                                           |
| ----------- | ------------------------------------------------------ | ------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| 登录与学习者空间    | 昵称/邮箱登录，创建或恢复 learner，本地保存 learner 信息                  | `LoginPage`                                | 左侧产品说明 + 右侧登录卡片；提交时有 loading spinner；错误 toast。                                                         | 登录页需要统一视觉 token；四个能力卡要有 hover/进入动效；移动端上下布局要更舒服。                  |
| AI 对话       | 流式聊天、取消生成、会话历史、记忆面板、Skill 状态条、Agent Skill 退出           | `ChatPage` / `ChatContainer`               | 左侧会话栏、中间聊天区、右侧记忆栏；History 和 Memory 可折叠。                                                                | 必须强化 streaming 动效、typing indicator、消息 hover 操作、移动端抽屉式历史/记忆栏。     |
| 探索能力中心      | 能力搜索、分类筛选、收藏、推荐卡、点击启动能力、跳转专项页面或进入 Chat Skill           | `ExplorePage`                              | FeatureHero + 推荐 + 分类 chip + feature card；能打开 Grammar、Reading、Writing、WordParts、VocabularyDetail 等子页面。 | 卡片 hover、推荐原因、收藏动效、状态 badge、能力启动 loading 要统一。                    |
| 学习中心首页      | 今日学习路径、学习状态、活动日历、学习路线、词汇入口、个人学习概览                      | `DashboardPage`                            | Home / vocabulary / profile / records 内部 workspace；有 activity calendar、路线卡、状态条。                        | 这是用户端核心首页，需要最多图表：趋势、热力、掌握度、复习负荷、错因分布。                            |
| 词汇管理        | 添加词、复习队列、删除、跳转新词/复习/拼写练习、只读词条详情                        | `DashboardPage` 内 Vocabulary Workspace     | 词汇列表、添加表单、统计、练习入口。                                                                                     | 列表行 hover、批量操作、掌握度 badge、复习优先级图示。                                |
| 教材知识库       | 上传教材、解析/ingest 状态、教材结构、单元学习、练习任务、解析校对、来源切换             | `KnowledgeBasePage`                        | 四个 workspace：教材结构 / 单元学习 / 练习任务 / 解析校对；左右有 CurriculumRail 和 ContextPanel。                              | 必须做可折叠左右栏；教材树、单元进度、解析质量、RAG 覆盖要图形化。                              |
| 每日教材题 / 单元题 | Daily lesson、单题提交、反馈、mastery/recommendations、教材练习题启动   | `KnowledgeBasePage` 弹层与 exercise workspace | DailyLesson modal 展示题目、选项/文本作答、反馈、推荐。                                                                  | 题目弹层要更接近 TaskShell；反馈出现后下一步操作仍要固定可见。                             |
| 词汇练习        | 新词、复习、拼写三种模式；TTS；英/美音；键盘快捷键；提示；构词信息；总结页                | `VocabularyPracticePage`                   | practice 阶段使用 h-dvh、固定 top/bottom、中间滚动；底部 action bar 固定。                                               | 这是 TaskShell 标准样板；正确/错误、拼写差异、TTS、提示展开都要有明确动效。                    |
| 词汇详解        | 输入词条、生成 prompt、外部模型回填 HTML、安全预览、沉浸阅读、加入词库、个人词卡编辑、练习接入  | `VocabularyDetailPage`                     | 四个 workspace：词条输入 / 生成指令 / 回填预览 / 词卡沉淀。                                                                | 生成-回填-保存要做成 stepper；HTML 状态、保存状态、词卡状态要清楚。                        |
| 发音训练        | 音标卡、搜索/筛选、播放、音素高亮、完成进度、今日 5 个、随机练、影子跟读、自评记录            | `PronunciationPage`                        | workspace 包括音标训练、影子跟读、最小对立音、训练记录；后两个目前是 placeholder。                                                   | 音频播放必须有 pulse/waveform；音标卡 hover 已有基础，但要统一动效；placeholder 要列为待设计。 |
| 影子跟读        | 句子列表、分块朗读、重音词、语调提示、练习建议、自评、本地记录                        | `PronunciationPage` Shadowing Workspace    | 左侧句子列表 + 右侧当前句详情；提示可隐藏。                                                                                | 需要节奏条、重音可视化、录音/播放状态位；移动端列表应可折叠。                                  |
| 语法微课        | 语法知识点库、生成 prompt、跳转目标 AI、HTML 缓存、回填预览、沉浸阅读、目标网站设置、练习接入 | `GrammarPage`                              | 四个 workspace：知识点 / 生成指令 / 预览回填 / 目标设置。                                                                 | 需要把 cache 状态、生成链路、练习状态做成统一状态条；预览页左右栏要能折叠。                        |
| 精读与泛读       | 材料输入、自动标题建议、历史材料、泛读任务、关键词、精读拆句、语法卡点、复盘沉淀               | `ReadingWorkshopPage`                      | 四个 workspace：材料输入 / 泛读模式 / 精读模式 / 沉淀复盘；精读可跳到 GrammarPage。                                              | 需要文本高亮、句子难度、阅读流程进度、语法卡点图示；左侧句子栏移动端折叠。                            |
| 词根词缀        | 方法入门、词根词缀库、搜索/筛选、拆词练习、提示/答案、掌握状态、本地进度                  | `WordPartsPage`                            | 四个 workspace：方法入门 / 词根词缀库 / 拆词练习 / 我的掌握。                                                               | 进度页要加图表；拆词练习答案 reveal 应有展开动效；词根卡需要统一 hover/selected。             |
| 写作好句        | 句式收藏、搜索/筛选、更多筛选折叠、新增/编辑 drawer、导入好句、候选收藏、练习检测、写作调用     | `WritingPhrasebookPage`                    | 四个 workspace：收藏馆 / 导入好句 / 练习检测 / 写作调用；编辑通过 drawer。                                                     | 这是当前较好的 UI 参考，但还要把自定义按钮换成统一 Button/IconButton，并补充练习结果图表。         |
| 学习记录与画像     | 活动热力、每日完成趋势、正确率/复习负荷趋势、能力雷达、掌握度分布、薄弱点排行、推荐原因            | `DashboardPage` profile / records          | 用户端学习中心内部二级视图；只展示学习者能理解的记录和画像，不展示 raw memory/debug evidence。                              | 后续可接入更真实的 mastery/error aggregation 数据源，替换当前轻量估算图表。                         |
| 学习记忆控制      | 查看记忆、整理、导出、重置计划、开关记忆设置、编辑/删除/禁用记忆、证据展示                 | `MemoryCenterPage`                         | 仅由 Dev Console 懒加载；页面本身使用 FeatureHero、ReasonCard、EvidencePanel、ConfirmDialog。                         | 不回到用户端一级导航；用户端只保留学习记录和学习者画像。                                      |

---

# 2. 用户端页面清单

## A. 当前主入口页面

| 页面                       | 当前入口                                        | 页面职责                      | 必须确认的 UI 点                                 |
| ------------------------ | ------------------------------------------- | ------------------------- | ------------------------------------------ |
| `LoginPage`              | 未登录时展示                                      | 创建/恢复学习空间                 | 登录卡、产品说明卡、表单 focus/loading/error、移动端上下布局   |
| `ChatPage`               | 主导航 AI 对话                                   | Agent 对话、Skill 执行、会话/记忆辅助 | 左右栏折叠、消息 hover、streaming、typing、移动端 drawer |
| `ExplorePage`            | 主导航 探索                                      | 所有能力的入口与推荐                | 能力卡 hover、分类 chip、收藏、推荐原因、启动 loading       |
| `DashboardPage`          | 主导航 学习中心                                    | 学习首页、词汇、画像、记录             | 首页图表、热力图、学习路线、内部 workspace 切换              |
| `KnowledgeBasePage`      | 学习中心进入 Daily Learning                       | 教材学习工作台                   | CurriculumRail / ContextPanel 折叠，四工作区布局    |
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
| Graph Runs / Episode Trace |   `/dev/graph-runs` | 查看 Episode Summary、Graph/Checkpoint、Timeline、Tool Calls、Prompt Executions、Verification、EvidenceRefs | `EpisodeDebugPage` 使用 full PageShell + 左主右侧栏。                    | 强烈建议加 DAG/Timeline/waterfall，而不是纯表格。              |
| Textbook Parsing           |    `/dev/textbooks` | 查看教材 source、解析状态、quality、parser runs、review queue、evidence browser                                  | sources 表格 + detail + review queue + parser run panels。          | 解析治理需要漏斗图、质量雷达、review 队列优先级。                      |
| Memory Debug               |       `/dev/memory` | 记忆查看、整理、导出、设置开关、控制记忆项                                                                               | 复用 `MemoryCenterPage`。                                           | Dev 保留 raw/evidence；用户端不暴露 Memory Center，只展示记录/画像。 |
| Tool Registry              |        `/dev/tools` | 查看 `/api/tools` 返回的 ToolSpec、schema                                                                 | Dev Console App 内 fetch tools 并渲染 cards/schema。                  | Schema 需要可折叠 JSON、搜索、分组、调用频率。                     |
| Tool Call Records          |   `/dev/tool-calls` | 按 episode 查看工具调用记录                                                                                  | 读取 `/api/runtime/episodes/{episodeId}`，展示 tool calls 与 raw JSON。 | 增加 latency bar、status badge、错误聚合。                 |
| Evidence Debug             |     `/dev/evidence` | evidence resolve 调试                                                                                 | 表单请求 `/api/evidence/resolve`。                                    | Evidence 链路要图形化：来源 → 使用位置 → 检查结果。                 |
| RAG Debug                  |          `/dev/rag` | RAG search 调试、chunk/score 展示                                                                        | 请求 `/api/debug/rag/search`，展示 metrics 与 chunks。                  | 加 score 分布、chunk 来源、召回覆盖。                         |
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
| KnowledgeBase          | 教材目录树、单元进度 timeline、解析质量 score card、parser warnings 分布、RAG coverage 条形图            |
| VocabularyPractice     | 遗忘曲线、due queue 分布、拼写错误热力图、掌握度趋势、词性/来源分布                                            |
| VocabularyDetail       | 词义结构树、构词拆解图、个人词卡状态 timeline                                                        |
| Pronunciation          | IPA matrix、音素分类网格、shadowing 练习次数趋势、句子节奏/重音条、音素完成度环                                 |
| Grammar                | 知识点分类矩阵、已学/收藏/缓存状态图、练习正确率趋势                                                        |
| ReadingWorkshop        | 词数/句数/耗时指标卡、句子难度 heatmap、关键词频次、语法卡点分布                                              |
| WordParts              | prefix/root/suffix 掌握度堆叠条、练习次数趋势、词根关系图                                             |
| WritingPhrasebook      | 句式功能分布、难度分布、待复习数量、练习正确率、写作位置 coverage                                              |
| Dev Console Graph Runs | DAG、事件 timeline、node waterfall、tool latency histogram、verification pass/fail donut |
| Dev Console Textbook   | parser quality radar、review queue funnel、source status stacked bar                 |
| Dev Console RAG        | score scatter、top-k bar、chunk source distribution                                  |
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
| Pronunciation      | 音标网格 + sticky detail                    | detail drawer   | detail bottom sheet | detail panel、shadowing list             |
| Grammar            | 左生成/输入 + 右预览                            | 预览下移            | 单列 stepper          | prompt preview、HTML input               |
| ReadingWorkshop    | 左/右双栏                                   | 侧栏折叠            | 单列                  | sentence list、history                   |
| WordParts          | 主内容 + 右详情                               | 详情下移            | 单列                  | filters、part detail                     |
| WritingPhrasebook  | 左列表 + 右详情                               | 详情下移            | 单列 + drawer         | filters、edit drawer                     |
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

1. **复杂页面折叠策略不统一**：Chat 已有折叠，Knowledge/Pronunciation/Reading/Writing 等复杂页面需要统一 drawer/bottom sheet 规则。
2. **交互状态仍需继续归一**：部分页面使用统一 Button，部分页面还有手写 button class；hover、focus、loading、disabled、danger 状态需要继续清理。
3. **图表数据源仍可增强**：Dashboard 已补能力雷达、掌握度分布、趋势图和热力图，但部分指标仍是基于 summary 的轻量估算，后续应接入更完整 mastery/error aggregation。
4. **Dev Console 太偏表格/JSON**：适合开发，但需要更多可视化链路，尤其 Graph Runs、Textbook Parsing、Verification、RAG。
5. **Pronunciation 的 Minimal Pairs / Records 仍是占位**：后续确认界面时要标成“待设计/待接入”，不能误认为完整功能。

