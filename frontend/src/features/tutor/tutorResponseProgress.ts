export type TutorResponseProgressState = {
  startedAt: number;
  stages: string[];
};

export function appendTutorProgressStage(stages: string[], label: string) {
  const normalized = label.trim();
  if (!normalized || stages.at(-1) === normalized) return stages;
  return [...stages, normalized];
}
