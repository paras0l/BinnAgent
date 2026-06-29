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

const durationInFrames = 2700;

const scenePlan = [
  { name: "title", start: 0, duration: 240 },
  { name: "definition", start: 240, duration: 330 },
  { name: "formula", start: 570, duration: 360 },
  { name: "tenses", start: 930, duration: 420 },
  { name: "transform", start: 1350, duration: 420 },
  { name: "usage", start: 1770, duration: 330 },
  { name: "quiz", start: 2100, duration: 420 },
  { name: "wrap", start: 2520, duration: 180 },
];

const tenseRows = [
  {
    label: "一般现在时",
    structure: "am / is / are + done",
    example: "English is spoken by many people.",
  },
  {
    label: "一般过去时",
    structure: "was / were + done",
    example: "The window was broken yesterday.",
  },
  {
    label: "一般将来时",
    structure: "will be + done",
    example: "The homework will be checked tomorrow.",
  },
];

const quizOptions = [
  "A. The room cleans every day.",
  "B. The room is cleaned every day.",
  "C. The room is clean every day by.",
];

const container: React.CSSProperties = {
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  background:
    "radial-gradient(circle at 18% 14%, rgba(20,184,166,0.2), transparent 26%), radial-gradient(circle at 82% 18%, rgba(99,102,241,0.16), transparent 24%), linear-gradient(135deg, #f8fafc 0%, #f0fdfa 48%, #eef2ff 100%)",
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
  background: "rgba(255,255,255,0.9)",
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
    config: { damping: 18, stiffness: 118, mass: 0.82 },
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
          color: "#0f766e",
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
  const width = interpolate(frame, [0, durationInFrames], [0, 100], {
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
        background: "linear-gradient(90deg, #0f766e, #2563eb, #7c3aed)",
      }}
    />
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
      fontSize: 26,
      lineHeight: 1.35,
      fontWeight: 760,
    }}
  >
    {children}
  </div>
);

const FloatingCards: React.FC = () => {
  const frame = useCurrentFrame();
  const terms = ["be", "done", "by", "is made", "was written"];

  return (
    <>
      {terms.map((term, index) => {
        const opacity = fade(frame, 10 + index * 8, 42 + index * 8);
        const y = Math.sin((frame + index * 17) / 23) * 10;
        const x = Math.cos((frame + index * 13) / 29) * 8;

        return (
          <div
            key={term}
            style={{
              ...card,
              position: "absolute",
              right: 82 + (index % 2) * 175,
              top: 92 + index * 88,
              padding: "18px 24px",
              fontSize: 30,
              fontWeight: 900,
              color: index % 2 ? "#1d4ed8" : "#0f766e",
              transform: `translate(${x}px, ${y}px) rotate(${
                index % 2 ? 3 : -3
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

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <div />
        <div style={{ width: 780 }}>
          <div
            style={{
              fontSize: 34,
              fontWeight: 800,
              color: "#0f766e",
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
            被动语态？
          </h1>
          <p
            style={{
              fontSize: 34,
              lineHeight: 1.35,
              marginTop: 28,
              maxWidth: 760,
              opacity: fade(frame, 48, 82),
            }}
          >
            当我们更关心“事情被做了”，而不是“谁做的”，就常用被动语态。
          </p>
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, color: "#475569" }}>
          面向中学生 · 中文讲解 · 英文例句
        </div>
      </div>
      <FloatingCards />
      <ProgressBar />
    </AbsoluteFill>
  );
};

const DefinitionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = appear(frame, fps, 14);
  const focus = interpolate(frame, [78, 150], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader eyebrow="核心定义" title="被动语态：主语是动作的承受者" />
        <div
          style={{
            ...card,
            padding: 44,
            opacity: pop,
            transform: `translateY(${interpolate(pop, [0, 1], [34, 0])}px)`,
          }}
        >
          <div style={{ fontSize: 38, lineHeight: 1.5, fontWeight: 800 }}>
            主动语态关注
            <span style={{ color: "#2563eb" }}> 谁做动作 </span>；被动语态关注
            <span style={{ color: "#0f766e" }}> 谁承受动作 </span>。
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
            Active: Tom cleans the room.
            <br />
            Passive: The room is cleaned by Tom.
            <div
              style={{
                position: "absolute",
                left: 24,
                bottom: 13,
                height: 5,
                width: `${focus * 82}%`,
                background: "#2dd4bf",
                borderRadius: 999,
              }}
            />
          </div>
        </div>
        <Narration>
          中文里像“房间被打扫了”，英语里常对应 The room is cleaned。
        </Narration>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const FormulaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const bePop = appear(frame, fps, 30);
  const donePop = appear(frame, fps, 82);

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader eyebrow="核心结构" title="be + 过去分词" />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 32,
          }}
        >
          <FormulaBlock label="be" detail="随时态和主语变化" scale={bePop} />
          <FormulaBlock label="done" detail="动词的过去分词" scale={donePop} />
        </div>
        <div
          style={{
            ...card,
            padding: "30px 34px",
            borderLeft: "12px solid #0f766e",
            opacity: fade(frame, 132, 166),
          }}
        >
          <div style={{ fontSize: 36, lineHeight: 1.35, fontWeight: 860 }}>
            The cake <span style={{ color: "#0f766e" }}>is made</span> by my
            mother.
          </div>
          <div style={{ fontSize: 28, color: "#64748b", marginTop: 12 }}>
            is 是 be，made 是 make 的过去分词。
          </div>
        </div>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const FormulaBlock: React.FC<{
  label: string;
  detail: string;
  scale: number;
}> = ({ label, detail, scale }) => (
  <div
    style={{
      ...card,
      minHeight: 260,
      padding: 42,
      opacity: scale,
      transform: `translateY(${interpolate(scale, [0, 1], [34, 0])}px)`,
    }}
  >
    <div style={{ fontSize: 92, lineHeight: 1, fontWeight: 940 }}>{label}</div>
    <div
      style={{
        marginTop: 24,
        color: "#475569",
        fontSize: 34,
        fontWeight: 820,
        lineHeight: 1.25,
      }}
    >
      {detail}
    </div>
  </div>
);

const TensesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader eyebrow="常见时态" title="变的是 be，不变的是 done" />
        <div style={{ display: "grid", gap: 18 }}>
          {tenseRows.map((row, index) => {
            const pop = appear(frame, fps, 28 + index * 34);

            return (
              <div
                key={row.label}
                style={{
                  ...card,
                  padding: "24px 30px",
                  display: "grid",
                  gridTemplateColumns: "220px 330px 1fr",
                  alignItems: "center",
                  gap: 24,
                  opacity: pop,
                  transform: `translateX(${interpolate(
                    pop,
                    [0, 1],
                    [-36, 0],
                  )}px)`,
                }}
              >
                <div
                  style={{ fontSize: 27, fontWeight: 900, color: "#0f766e" }}
                >
                  {row.label}
                </div>
                <div style={{ fontSize: 29, fontWeight: 880 }}>
                  {row.structure}
                </div>
                <div style={{ fontSize: 28, fontWeight: 780 }}>
                  {row.example}
                </div>
              </div>
            );
          })}
        </div>
        <Narration>
          判断被动语态时，先找 be，再看它后面是不是过去分词。
        </Narration>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const TransformScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const arrow = spring({
    frame: frame - 98,
    fps,
    config: { damping: 12, stiffness: 100 },
  });

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader eyebrow="主动变被动" title="宾语提前，动词变 be + done" />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 120px 1fr",
            gap: 28,
            alignItems: "center",
          }}
        >
          <SentenceCard
            label="主动"
            text="The boy broke the cup."
            hint="谁打碎？the boy"
            delay={24}
          />
          <div
            style={{
              fontSize: 72,
              color: "#0f766e",
              fontWeight: 900,
              textAlign: "center",
              opacity: arrow,
              transform: `scale(${interpolate(arrow, [0, 1], [0.72, 1])})`,
            }}
          >
            →
          </div>
          <SentenceCard
            label="被动"
            text="The cup was broken by the boy."
            hint="谁承受？the cup"
            delay={118}
          />
        </div>
        <div
          style={{
            ...card,
            padding: "26px 32px",
            fontSize: 31,
            lineHeight: 1.35,
            fontWeight: 830,
            opacity: fade(frame, 178, 216),
          }}
        >
          三步走：找宾语 → 放到句首 → 根据原句时态选择 be，再接过去分词。
        </div>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

const SentenceCard: React.FC<{
  label: string;
  text: string;
  hint: string;
  delay: number;
}> = ({ label, text, hint, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = appear(frame, fps, delay);

  return (
    <div
      style={{
        ...card,
        padding: 34,
        minHeight: 260,
        opacity: pop,
        transform: `translateY(${interpolate(pop, [0, 1], [36, 0])}px)`,
      }}
    >
      <div
        style={{
          display: "inline-flex",
          padding: "8px 16px",
          borderRadius: 999,
          background: "rgba(20,184,166,0.14)",
          color: "#0f766e",
          fontSize: 24,
          fontWeight: 900,
          marginBottom: 28,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 36, lineHeight: 1.22, fontWeight: 880 }}>
        {text}
      </div>
      <div
        style={{
          marginTop: 20,
          color: "#64748b",
          fontSize: 27,
          fontWeight: 760,
        }}
      >
        {hint}
      </div>
    </div>
  );
};

const UsageScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const items = [
    {
      title: "不知道动作执行者",
      example: "My bike was stolen.",
    },
    {
      title: "执行者不重要",
      example: "The road is repaired every year.",
    },
    {
      title: "强调承受者",
      example: "This song was written by Jay Chou.",
    },
  ];

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <SceneHeader eyebrow="什么时候用" title="重点在结果或承受者" />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 22,
          }}
        >
          {items.map((item, index) => {
            const pop = appear(frame, fps, 24 + index * 36);
            return (
              <div
                key={item.title}
                style={{
                  ...card,
                  padding: 28,
                  minHeight: 250,
                  opacity: pop,
                  transform: `translateY(${interpolate(pop, [0, 1], [34, 0])}px)`,
                }}
              >
                <div
                  style={{
                    fontSize: 30,
                    lineHeight: 1.2,
                    fontWeight: 900,
                    color: "#0f766e",
                    marginBottom: 22,
                  }}
                >
                  {item.title}
                </div>
                <div
                  style={{ fontSize: 31, lineHeight: 1.25, fontWeight: 820 }}
                >
                  {item.example}
                </div>
              </div>
            );
          })}
        </div>
        <Narration>
          by + 人 可以说明动作执行者；如果不重要，经常可以省略。
        </Narration>
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
        <SceneHeader eyebrow="小测试" title="哪一句是正确的被动语态？" />
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
              background: "linear-gradient(90deg, #0f766e, #2563eb)",
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
                    : "rgba(255,255,255,0.9)",
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
          答案：B。room 是动作承受者，every day 用一般现在时，所以是 is
          cleaned。
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
    "被动语态关注动作的承受者。",
    "核心结构是 be + 过去分词。",
    "时态体现在 be 上，过去分词保持不变。",
  ];

  return (
    <AbsoluteFill style={container}>
      <div style={sceneInner}>
        <div />
        <div
          style={{
            ...card,
            padding: 46,
            opacity: pop,
            transform: `scale(${interpolate(pop, [0, 1], [0.94, 1])})`,
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
          看到 be + done，先问自己：主语是不是“被做某事”的对象？
        </Narration>
      </div>
      <ProgressBar />
    </AbsoluteFill>
  );
};

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

export const PassiveVoiceLesson: React.FC = () => (
  <>
    <SceneSequence name="title">
      <TitleScene />
    </SceneSequence>
    <SceneSequence name="definition">
      <DefinitionScene />
    </SceneSequence>
    <SceneSequence name="formula">
      <FormulaScene />
    </SceneSequence>
    <SceneSequence name="tenses">
      <TensesScene />
    </SceneSequence>
    <SceneSequence name="transform">
      <TransformScene />
    </SceneSequence>
    <SceneSequence name="usage">
      <UsageScene />
    </SceneSequence>
    <SceneSequence name="quiz">
      <QuizScene />
    </SceneSequence>
    <SceneSequence name="wrap">
      <WrapScene />
    </SceneSequence>
  </>
);
