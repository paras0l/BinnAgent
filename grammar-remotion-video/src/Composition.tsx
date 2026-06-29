import React from "react";
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const scenePlan = [
  { name: "title", start: 0, duration: 240 },
  { name: "definition", start: 240, duration: 360 },
  { name: "present", start: 600, duration: 390 },
  { name: "past", start: 990, duration: 390 },
  { name: "wish", start: 1380, duration: 360 },
  { name: "that", start: 1740, duration: 360 },
  { name: "quiz", start: 2100, duration: 420 },
  { name: "wrap", start: 2520, duration: 180 },
];

const lessonSections = [
  {
    label: "现在反事实",
    formula: "If + 主语 + were / 动词过去式, 主语 + would + 动词原形",
    example: "If I were taller, I would join the basketball team.",
    note: "事实是：我现在不够高，所以没有加入篮球队。",
    color: "#3b82f6",
  },
  {
    label: "过去反事实",
    formula: "If + 主语 + had + 过去分词, 主语 + would have + 过去分词",
    example: "If she had studied harder, she would have passed the test.",
    note: "事实是：她过去没有更努力，所以没有通过考试。",
    color: "#f97316",
  },
  {
    label: "wish 句型",
    formula: "wish + 过去式 / had + 过去分词",
    example: "I wish I knew the answer. / I wish I had listened carefully.",
    note: "wish 后面常表达遗憾、愿望，时态往后退一步。",
    color: "#14b8a6",
  },
  {
    label: "建议与要求",
    formula: "suggest / important that + 主语 + 动词原形",
    example: "The teacher suggested that he review his notes.",
    note: "that 从句里用动词原形，第三人称也不加 s。",
    color: "#8b5cf6",
  },
];

const quizOptions = [
  "A. If I am a bird, I will fly.",
  "B. If I were a bird, I would fly.",
  "C. If I was fly, I would be a bird.",
];

const container: React.CSSProperties = {
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  background:
    "radial-gradient(circle at 20% 12%, rgba(59,130,246,0.22), transparent 26%), radial-gradient(circle at 82% 26%, rgba(249,115,22,0.16), transparent 24%), linear-gradient(135deg, #f8fafc 0%, #ecfeff 46%, #fff7ed 100%)",
  color: "#0f172a",
};

const sceneInner: React.CSSProperties = {
  width: "100%",
  height: "100%",
  padding: "54px 72px",
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
};

const card: React.CSSProperties = {
  background: "rgba(255,255,255,0.88)",
  border: "1px solid rgba(15,23,42,0.12)",
  boxShadow: "0 24px 80px rgba(15,23,42,0.12)",
  borderRadius: 28,
};

const getScene = (name: string) => {
  const scene = scenePlan.find((item) => item.name === name);
  if (!scene) {
    throw new Error(`Missing scene: ${name}`);
  }
  return scene;
};

const appear = (frame: number, fps: number, delay = 0) =>
  spring({
    frame: frame - delay,
    fps,
    config: { damping: 18, stiffness: 120, mass: 0.8 },
  });

const fade = (frame: number, from: number, to: number) =>
  interpolate(frame, [from, to], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

const SceneHeader: React.FC<{ eyebrow: string; title: string }> = ({
  eyebrow,
  title,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = appear(frame, fps);

  return (
    <div
      style={{
        transform: `translateY(${interpolate(pop, [0, 1], [18, 0])}px)`,
        opacity: pop,
      }}
    >
      <div
        style={{
          fontSize: 26,
          fontWeight: 800,
          color: "#2563eb",
          marginBottom: 12,
        }}
      >
        {eyebrow}
      </div>
      <div style={{ fontSize: 64, fontWeight: 900, lineHeight: 1.02 }}>
        {title}
      </div>
    </div>
  );
};

const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const width = interpolate(frame, [0, 2700], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        bottom: 0,
        height: 8,
        width: `${width}%`,
        background: "linear-gradient(90deg, #2563eb, #14b8a6, #f97316)",
      }}
    />
  );
};

const FloatingGrammarCards: React.FC = () => {
  const frame = useCurrentFrame();
  const terms = ["were", "would", "had done", "wish", "that + do"];

  return (
    <>
      {terms.map((term, index) => {
        const y = Math.sin((frame + index * 19) / 24) * 10;
        const x = Math.cos((frame + index * 12) / 30) * 8;
        const opacity = fade(frame, 12 + index * 7, 44 + index * 7);
        return (
          <div
            key={term}
            style={{
              ...card,
              position: "absolute",
              right: 88 + (index % 2) * 170,
              top: 94 + index * 92,
              padding: "18px 24px",
              fontSize: 30,
              fontWeight: 900,
              color: index % 2 ? "#0f766e" : "#1d4ed8",
              transform: `translate(${x}px, ${y}px) rotate(${
                index % 2 ? -3 : 3
              }deg)`,
              opacity,
            }}
          >
            {term}
          </div>
        );
      })}
    </>
  );
};

const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const titlePop = appear(frame, fps, 8);
  const subOpacity = fade(frame, 45, 80);

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <div />
        <div style={{ width: 780 }}>
          <div
            style={{
              fontSize: 34,
              fontWeight: 800,
              color: "#2563eb",
              marginBottom: 18,
              opacity: fade(frame, 0, 24),
            }}
          >
            90 秒英语语法课
          </div>
          <h1
            style={{
              margin: 0,
              fontSize: 104,
              lineHeight: 0.98,
              letterSpacing: 0,
              transform: `scale(${interpolate(titlePop, [0, 1], [0.9, 1])})`,
              transformOrigin: "left center",
              opacity: titlePop,
            }}
          >
            什么是
            <br />
            虚拟语气？
          </h1>
          <p
            style={{
              fontSize: 34,
              lineHeight: 1.35,
              marginTop: 28,
              maxWidth: 760,
              opacity: subOpacity,
            }}
          >
            它不是“虚假语气”，而是用特殊动词形式表达假设、愿望、建议和遗憾。
          </p>
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, color: "#475569" }}>
          面向中学生 · 中文讲解 · 英文例句
        </div>
      </div>
      <FloatingGrammarCards />
      <ProgressBar />
    </AbsoluteFill>
  );
};

const DefinitionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = appear(frame, fps, 12);
  const marker = interpolate(frame, [70, 150], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader eyebrow="核心定义" title="虚拟语气 = 事实之外的表达" />
        <div
          style={{
            ...card,
            padding: 44,
            transform: `translateY(${interpolate(scale, [0, 1], [34, 0])}px)`,
            opacity: scale,
          }}
        >
          <div style={{ fontSize: 39, lineHeight: 1.5, fontWeight: 780 }}>
            当我们说的内容不是现实事实，而是
            <span style={{ color: "#2563eb" }}> 假设 </span>、
            <span style={{ color: "#0f766e" }}> 愿望 </span>、
            <span style={{ color: "#7c3aed" }}> 建议 </span>或
            <span style={{ color: "#ea580c" }}> 遗憾 </span>
            时，英语常用虚拟语气。
          </div>
          <div
            style={{
              marginTop: 34,
              padding: "24px 28px",
              borderRadius: 22,
              background: "#0f172a",
              color: "#f8fafc",
              fontSize: 34,
              fontWeight: 850,
              position: "relative",
              overflow: "hidden",
            }}
          >
            The key idea: not real now, not real then, or not decided yet.
            <div
              style={{
                position: "absolute",
                left: 24,
                bottom: 13,
                height: 5,
                width: `${marker * 86}%`,
                background: "#38bdf8",
                borderRadius: 999,
              }}
            />
          </div>
        </div>
        <Narration>
          记住一个判断方法：如果句子在说“不是事实”或“希望它发生”，就要警惕虚拟语气。
        </Narration>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const PatternScene: React.FC<{ sectionIndex: number; title: string }> = ({
  sectionIndex,
  title,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const section = lessonSections[sectionIndex];
  const formulaIn = appear(frame, fps, 18);
  const exampleIn = appear(frame, fps, 70);
  const factIn = appear(frame, fps, 128);

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader eyebrow={section.label} title={title} />
        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}
        >
          <InfoCard
            kicker="结构"
            color={section.color}
            scale={formulaIn}
            delayY={30}
          >
            {section.formula}
          </InfoCard>
          <InfoCard
            kicker="例句"
            color={section.color}
            scale={exampleIn}
            delayY={36}
          >
            {section.example}
          </InfoCard>
        </div>
        <div
          style={{
            ...card,
            padding: "30px 34px",
            borderLeft: `12px solid ${section.color}`,
            opacity: factIn,
            transform: `translateX(${interpolate(factIn, [0, 1], [-36, 0])}px)`,
          }}
        >
          <div style={{ fontSize: 26, color: "#64748b", fontWeight: 800 }}>
            中文理解
          </div>
          <div style={{ fontSize: 36, lineHeight: 1.35, fontWeight: 850 }}>
            {section.note}
          </div>
        </div>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const InfoCard: React.FC<{
  kicker: string;
  color: string;
  scale: number;
  delayY: number;
  children: React.ReactNode;
}> = ({ kicker, color, scale, delayY, children }) => (
  <div
    style={{
      ...card,
      minHeight: 250,
      padding: 36,
      transform: `translateY(${interpolate(scale, [0, 1], [delayY, 0])}px)`,
      opacity: scale,
    }}
  >
    <div
      style={{
        display: "inline-flex",
        padding: "8px 16px",
        borderRadius: 999,
        background: `${color}1f`,
        color,
        fontSize: 24,
        fontWeight: 900,
        marginBottom: 26,
      }}
    >
      {kicker}
    </div>
    <div style={{ fontSize: 36, lineHeight: 1.25, fontWeight: 880 }}>
      {children}
    </div>
  </div>
);

const ThatPatternScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const section = lessonSections[3];
  const pulse = spring({
    frame: frame - 145,
    fps,
    config: { damping: 10, stiffness: 90 },
  });

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader
          eyebrow={section.label}
          title="that 从句里，动词回到原形"
        />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.1fr 0.9fr",
            gap: 32,
          }}
        >
          <InfoCard
            kicker="常见词"
            color={section.color}
            scale={appear(frame, fps, 14)}
            delayY={24}
          >
            <span style={{ display: "block" }}>suggest / recommend</span>
            <span style={{ display: "block" }}>demand / require</span>
            <span style={{ display: "block" }}>important / necessary</span>
          </InfoCard>
          <InfoCard
            kicker="结构"
            color={section.color}
            scale={appear(frame, fps, 62)}
            delayY={24}
          >
            that + 主语 + 动词原形
          </InfoCard>
        </div>
        <div
          style={{
            ...card,
            padding: 34,
            fontSize: 39,
            fontWeight: 860,
            lineHeight: 1.35,
            opacity: fade(frame, 104, 136),
          }}
        >
          It is important that everyone{" "}
          <span
            style={{
              display: "inline-block",
              color: "#7c3aed",
              transform: `scale(${interpolate(pulse, [0, 1], [1, 1.12])})`,
            }}
          >
            be
          </span>{" "}
          on time.
          <div style={{ fontSize: 28, color: "#64748b", marginTop: 14 }}>
            不是 everyone is，而是 everyone be。
          </div>
        </div>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const QuizScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const answerReveal = fade(frame, 245, 285);
  const timer = interpolate(frame, [80, 230], [100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader eyebrow="小测试" title="哪一句是正确的现在反事实？" />
        <div
          style={{
            height: 12,
            borderRadius: 999,
            background: "rgba(15,23,42,0.1)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${timer}%`,
              background: "linear-gradient(90deg, #2563eb, #f97316)",
            }}
          />
        </div>
        <div style={{ display: "grid", gap: 20 }}>
          {quizOptions.map((option, index) => {
            const optionIn = appear(frame, fps, 42 + index * 28);
            const isAnswer = index === 1;
            return (
              <div
                key={option}
                style={{
                  ...card,
                  padding: "28px 34px",
                  fontSize: 36,
                  fontWeight: 850,
                  borderColor: isAnswer
                    ? `rgba(20,184,166,${0.2 + answerReveal * 0.7})`
                    : "rgba(15,23,42,0.12)",
                  background: isAnswer
                    ? `rgba(240,253,250,${0.88 + answerReveal * 0.12})`
                    : "rgba(255,255,255,0.88)",
                  transform: `translateX(${interpolate(
                    optionIn,
                    [0, 1],
                    [-26, 0],
                  )}px) scale(${isAnswer ? 1 + answerReveal * 0.03 : 1})`,
                  opacity: optionIn,
                }}
              >
                {option}
              </div>
            );
          })}
        </div>
        <div
          style={{
            fontSize: 34,
            lineHeight: 1.35,
            fontWeight: 850,
            opacity: answerReveal,
            color: "#0f766e",
          }}
        >
          答案：B。现在事实相反时，be 动词常用 were，主句用 would + 动词原形。
        </div>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const WrapScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = appear(frame, fps, 8);
  const items = [
    "现在反事实：were / did + would do",
    "过去反事实：had done + would have done",
    "wish 和 that 句型：看语境，动词形式要后退或用原形",
  ];

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <div />
        <div
          style={{
            ...card,
            padding: 46,
            transform: `scale(${interpolate(pop, [0, 1], [0.94, 1])})`,
            opacity: pop,
          }}
        >
          <div style={{ fontSize: 64, fontWeight: 930, marginBottom: 30 }}>
            记住三件事
          </div>
          <div style={{ display: "grid", gap: 18 }}>
            {items.map((item, index) => (
              <div
                key={item}
                style={{
                  fontSize: 32,
                  lineHeight: 1.35,
                  fontWeight: 820,
                  opacity: fade(frame, 38 + index * 18, 64 + index * 18),
                }}
              >
                {index + 1}. {item}
              </div>
            ))}
          </div>
        </div>
        <Narration>
          虚拟语气的关键不是死背名字，而是先判断：这句话是不是在说“和事实不一样”。
        </Narration>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const Narration: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      alignSelf: "stretch",
      padding: "20px 28px",
      borderRadius: 20,
      background: "rgba(15,23,42,0.86)",
      color: "#f8fafc",
      fontSize: 28,
      lineHeight: 1.35,
      fontWeight: 760,
    }}
  >
    {children}
  </div>
);

const SceneSequence: React.FC<{
  name: string;
  children: React.ReactNode;
}> = ({ name, children }) => {
  const scene = getScene(name);
  return (
    <Sequence from={scene.start} durationInFrames={scene.duration}>
      {children}
    </Sequence>
  );
};

export const GrammarMoodLesson: React.FC = () => (
  <>
    <SceneSequence name="title">
      <TitleScene />
    </SceneSequence>
    <SceneSequence name="definition">
      <DefinitionScene />
    </SceneSequence>
    <SceneSequence name="present">
      <PatternScene sectionIndex={0} title="和现在事实相反" />
    </SceneSequence>
    <SceneSequence name="past">
      <PatternScene sectionIndex={1} title="和过去事实相反" />
    </SceneSequence>
    <SceneSequence name="wish">
      <PatternScene sectionIndex={2} title="wish 表达愿望和遗憾" />
    </SceneSequence>
    <SceneSequence name="that">
      <ThatPatternScene />
    </SceneSequence>
    <SceneSequence name="quiz">
      <QuizScene />
    </SceneSequence>
    <SceneSequence name="wrap">
      <WrapScene />
    </SceneSequence>
  </>
);
