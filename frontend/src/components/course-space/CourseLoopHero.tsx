import { ArrowRight, Graph, ShieldCheck } from "@phosphor-icons/react";

import { type CourseLoopSummary } from "../../features/course-space/a3Loop";

type CourseLoopHeroProps = {
  summary: CourseLoopSummary;
};

export function CourseLoopHero({ summary }: CourseLoopHeroProps) {
  return (
    <section className="course-loop-hero" aria-label="课程学习闭环">
      <div className="course-loop-copy">
        <span className="course-loop-kicker">
          <Graph size={16} weight="duotone" aria-hidden="true" />
          A3 个性化学习闭环
        </span>
        <h1>{summary.title}</h1>
        <p>{summary.currentGoal}</p>
        <div className="course-loop-evidence" aria-label="课程闭环依据">
          <span>{summary.evidenceLine}</span>
          {summary.traceLabel ? (
            <span>
              <ShieldCheck size={15} weight="duotone" aria-hidden="true" />
              {summary.traceLabel}
            </span>
          ) : null}
        </div>
      </div>
      <div className="course-loop-next">
        <span>下一步</span>
        <strong>{summary.nextAction}</strong>
        <em>闭环 {summary.progressLabel}</em>
        <ArrowRight size={18} weight="bold" aria-hidden="true" />
      </div>
    </section>
  );
}
