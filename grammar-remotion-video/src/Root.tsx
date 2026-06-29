import "./index.css";
import { Composition } from "remotion";
import { GrammarMoodLesson } from "./Composition";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SubjunctiveMoodLesson"
        component={GrammarMoodLesson}
        durationInFrames={2700}
        fps={30}
        width={1280}
        height={720}
      />
    </>
  );
};
