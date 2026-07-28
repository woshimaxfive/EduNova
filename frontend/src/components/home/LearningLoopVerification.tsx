import { ArrowRight, BookOpen, CheckCircle, LinkSimple, Target } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import type { LearningNextAction } from "../../api/learning";
import { buildCoursePath, buildCoursePracticeWorkspacePath } from "../../app/routePaths";
import { learningActionButtonLabel, learningActionHref } from "../../features/learning-actions/learningActions";

type Props = {
  courseId: string | null;
  nextAction: LearningNextAction | null | undefined;
  onFocusQuestion: () => void;
  onOpenLibrary: () => void;
};

export function LearningLoopVerification({ courseId, nextAction, onFocusQuestion, onOpenLibrary }: Props) {
  return (
    <section className="learning-loop-verification" aria-label="快速验证学习闭环">
      <header>
        <span className="learning-loop-kicker">三分钟核验</span>
        <h2>沿着真实学习状态，走完一次闭环</h2>
        <p>不要只看一次回答。依次检查教材证据、学习行动、练习结果和下一步推荐。</p>
      </header>

      <ol>
        <li>
          <BookOpen size={21} weight="duotone" aria-hidden="true" />
          <span className="learning-loop-step">01</span>
          <strong>课程证据</strong>
          <p>查看教材目录、知识点与章节来源。</p>
          {courseId ? (
            <Link to={buildCoursePath(courseId)}>
              <span>查看课程</span>
              <ArrowRight size={15} weight="bold" aria-hidden="true" />
            </Link>
          ) : (
            <button type="button" onClick={onOpenLibrary}>
              <span>添加资料</span>
              <ArrowRight size={15} weight="bold" aria-hidden="true" />
            </button>
          )}
        </li>
        <li>
          <LinkSimple size={21} weight="duotone" aria-hidden="true" />
          <span className="learning-loop-step">02</span>
          <strong>回答转行动</strong>
          <p>围绕课程提问，再继续生成学习资源。</p>
          <button type="button" onClick={onFocusQuestion}>
            <span>定位提问入口</span>
            <ArrowRight size={15} weight="bold" aria-hidden="true" />
          </button>
        </li>
        <li>
          <CheckCircle size={21} weight="duotone" aria-hidden="true" />
          <span className="learning-loop-step">03</span>
          <strong>练习改状态</strong>
          <p>用真实作答更新掌握度和薄弱点。</p>
          {courseId ? (
            <Link to={buildCoursePracticeWorkspacePath(courseId)}>
              <span>进入练习</span>
              <ArrowRight size={15} weight="bold" aria-hidden="true" />
            </Link>
          ) : (
            <span className="learning-loop-unavailable">建立课程后可用</span>
          )}
        </li>
        <li>
          <Target size={21} weight="duotone" aria-hidden="true" />
          <span className="learning-loop-step">04</span>
          <strong>下一步有依据</strong>
          <p>核对推荐是否来自当前课程与学习证据。</p>
          {nextAction ? (
            <Link to={learningActionHref(nextAction)}>
              <span>{learningActionButtonLabel(nextAction)}</span>
              <ArrowRight size={15} weight="bold" aria-hidden="true" />
            </Link>
          ) : (
            <span className="learning-loop-unavailable">形成状态后可用</span>
          )}
        </li>
      </ol>
    </section>
  );
}
