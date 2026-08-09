import { LearningSpaceView } from "../components/home/LearningSpaceView";
import { useLearningSpaceController } from "../features/home/useLearningSpaceController";


export function LearningSpacePage() {
  const controller = useLearningSpaceController();
  return <LearningSpaceView controller={controller} />;
}
