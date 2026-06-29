import "./index.css";
import { Composition } from "remotion";
import { SubjunctiveMoodLesson } from "./SubjunctiveMoodLesson";
import { PassiveVoiceLesson } from "./PassiveVoiceLesson";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SubjunctiveMoodLesson"
        component={SubjunctiveMoodLesson}
        durationInFrames={2700}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="PassiveVoiceLesson"
        component={PassiveVoiceLesson}
        durationInFrames={2700}
        fps={30}
        width={1280}
        height={720}
      />
    </>
  );
};
