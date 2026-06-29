# 英语语法教学视频：什么是虚拟语气

这是一个可运行、易修改的 Remotion 项目，用 React 组件制作 90 秒英语语法教学视频。

## 视频配置

- Composition ID: `SubjunctiveMoodLesson`
- 时长: 90 秒
- 帧率: 30fps
- 分辨率: 1280 x 720
- 内容: 中文讲解，英文例句展示，不使用外部素材

## 场景结构

代码位于 `src/Composition.tsx`，主要场景包括：

1. 标题：什么是虚拟语气
2. 核心定义
3. 和现在事实相反
4. 和过去事实相反
5. `wish` 句型
6. `suggest / important that` 句型
7. 小测试
8. 总结

## 常用命令

```bash
npm install
npm run dev
npm run lint
npx remotion still SubjunctiveMoodLesson --frame=900 --scale=0.25 --output=out/frame-900.png
npx remotion render SubjunctiveMoodLesson
```

## 修改建议

- 修改文案：编辑 `lessonSections`、`quizOptions` 和各个 scene 组件中的中文讲解。
- 修改时长：同步调整 `scenePlan` 和 `src/Root.tsx` 中的 `durationInFrames`。
- 修改动画：查看 `appear()`、`fade()`，以及各场景里的 `interpolate()` 和 `spring()`。
