import { StudioDock } from "../components/studio/StudioDock";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { PageFrame } from "./PageFrame";

export function StudioPage() {
  return (
    <PageFrame kicker="Studio" title="把知识点生成可学习资源" description="讲解、练习、思维导图、复盘报告和 PPT 大纲会绑定引用与审核状态。">
      <StudioDock outputs={demoLearningSpace.studioOutputs} />
    </PageFrame>
  );
}
