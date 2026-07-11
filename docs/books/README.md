# 教材研究资料

这里保留人教版七年级英语教材研究输入和可核查的结构化产物。应用中的公共教材目录使用短结构化学习资料，原 PDF 与 Markdown 不作删除或覆盖。

- `七年级上册-分单元教学内容解析.md`：3 个过渡单元、7 个正式单元的目标、活动链、语言知识和评价任务。
- `七年级上册-分单元词汇表.md`：教材 Vocabulary in Each Unit 分单元词表。
- `七年级上册-Vocabulary-from-Primary-School.md`：小学阶段复现词汇，独立于本册新增词汇。
- `audio/七年级上册-英语朗读宝/`：10 个单元与 Reading Plus 连续朗读音频，约 2 小时 36 分钟。
- `01-Starter-Unit-1-Hello.timeline.json`：Starter Unit 1 的 186 段精校点读时间轴，已验证 0 重叠、898203 ms 内不越界。

应用运行时清单位于 `src/classroom/assets/pep_grade7_upper_2024/`，由 `scripts/build_grade7_upper_catalog.py` 从上述原始资料生成：覆盖 10 个单元、333 条本册词汇、349 条小学复现词、10 组 Grammar Lab 和正文第 1-74 印刷页的完整活动页题图。每组 Grammar Lab 包含明确的 can-do 目标、核心规则、结构模板、教材语境例句、典型错误、3 道即时辨析题与迁移表达任务；题图由 2024 PDF 原页渲染裁切，清单保留印刷页码、PDF 页序、页面文本和单元导学/Section A/Pronunciation/Section B/Project 类型；原 Markdown 与 PDF 不作修改。

当前限制：其余 9 个单元和 Reading Plus 尚未完成逐句时间轴，应用中自动降级为连续朗读；不得宣称这些音频已完成人工逐句回听。
