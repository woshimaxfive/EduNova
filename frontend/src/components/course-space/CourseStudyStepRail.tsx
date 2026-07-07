import { CheckCircle, Circle, Sparkle } from "@phosphor-icons/react";

import { type StudyStep } from "../../features/course-space/a3Loop";
import { studyStepStatusLabels } from "./courseSpaceLabels";

type CourseStudyStepRailProps = {
  steps: StudyStep[];
};

export function CourseStudyStepRail({ steps }: CourseStudyStepRailProps) {
  return (
    <section className="course-study-step-rail" aria-label="A3 学习步骤">
      {steps.map((step) => {
        const Icon = step.status === "done" ? CheckCircle : step.status === "next" ? Sparkle : Circle;

        return (
          <article
            className={`course-study-step ${step.status}`}
            key={step.key}
            aria-label={`${step.label}，${studyStepStatusLabels[step.status]}，${step.description}`}
          >
            <Icon size={18} weight={step.status === "empty" ? "regular" : "duotone"} aria-hidden="true" />
            <div>
              <span>{studyStepStatusLabels[step.status]}</span>
              <strong>{step.label}</strong>
              <p>{step.description}</p>
            </div>
          </article>
        );
      })}
    </section>
  );
}
