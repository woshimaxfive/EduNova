import { type TutorResponseProgressState } from "../../features/tutor/tutorResponseProgress";
import { AiCollaborationPanel } from "../evidence/AiCollaborationPanel";

type TutorResponseProgressProps = {
  state: TutorResponseProgressState;
  completed?: boolean;
  durationMs?: number;
  storageKey?: string;
};

export function TutorResponseProgress({ state, completed = false, durationMs, storageKey }: TutorResponseProgressProps) {
  return (
    <AiCollaborationPanel
      running={!completed}
      completed={completed}
      stages={state.stages}
      startedAt={state.startedAt}
      durationMs={durationMs}
      storageKey={storageKey}
    />
  );
}
