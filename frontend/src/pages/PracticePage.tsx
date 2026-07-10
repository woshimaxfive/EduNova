import { CheckCircle, ListChecks, WarningCircle } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getKnowledgePoints, listCourses } from "../api/courses";
import {
  createPracticeSession,
  type PracticeQuestion,
  type PracticeSessionDetail,
  submitPracticeAnswers
} from "../api/practice";
import { PATHS } from "../app/routePaths";
import { AgentTraceDisclosure } from "../components/evidence/AgentTraceDisclosure";
import { PageFrame } from "./PageFrame";

type PracticeSessionEnvelope = PracticeSessionDetail | { data?: PracticeSessionDetail };

function resolvePracticeSession(response: PracticeSessionEnvelope): PracticeSessionDetail | null {
  if ("questions" in response) {
    return response;
  }
  return response.data ?? null;
}

export function PracticePage() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const initialCourseId = searchParams.get("course_id") ?? "";
  const [selectedCourseId, setSelectedCourseId] = useState(initialCourseId);
  const [selectedPointId, setSelectedPointId] = useState("");
  const [questionCount, setQuestionCount] = useState(5);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [currentSession, setCurrentSession] = useState<PracticeSessionDetail | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [localError, setLocalError] = useState("");

  const coursesQuery = useQuery({
    queryKey: ["practice-courses"],
    queryFn: () => listCourses()
  });
  const courses = coursesQuery.data?.data ?? [];
  const effectiveCourseId = selectedCourseId || courses[0]?.id || "";
  const numericCourseId = Number(effectiveCourseId);
  const canUseCourse = Number.isFinite(numericCourseId) && numericCourseId > 0;
  const pointsQuery = useQuery({
    queryKey: ["practice-knowledge-points", numericCourseId],
    queryFn: () => getKnowledgePoints(numericCourseId),
    enabled: canUseCourse
  });
  const knowledgePoints = pointsQuery.data?.data ?? [];
  const hasSelectedPoint = knowledgePoints.some((point) => point.id === selectedPointId);
  const effectivePointId = hasSelectedPoint ? selectedPointId : (knowledgePoints[0]?.id ?? "");
  const selectedPointIds = effectivePointId ? [Number(effectivePointId)] : [];

  const feedbackByQuestion = useMemo(() => {
    const result = new Map<string, PracticeSessionDetail["answers"][number]>();
    for (const answer of currentSession?.answers ?? []) {
      result.set(answer.question_id, answer);
    }
    return result;
  }, [currentSession]);

  const createMutation = useMutation({
    mutationFn: () =>
      createPracticeSession({
        course_id: numericCourseId,
        knowledge_point_ids: selectedPointIds,
        question_count: questionCount,
        difficulty
      }),
    onSuccess: (response) => {
      setLocalError("");
      setCurrentSession(resolvePracticeSession(response));
      setAnswers({});
    },
    onError: () => {
      setLocalError("练习生成失败，请稍后重试。");
    }
  });

  const submitMutation = useMutation({
    mutationFn: () => {
      if (!currentSession) {
        throw new Error("missing session");
      }
      return submitPracticeAnswers(Number(currentSession.id), {
        answers: currentSession.questions.map((question) => ({
          question_id: question.id,
          answer_text: answers[question.id] ?? ""
        }))
      });
    },
    onSuccess: (response) => {
      setLocalError("");
      setCurrentSession(resolvePracticeSession(response));
      void queryClient.invalidateQueries({ queryKey: ["courses", "learning-state", numericCourseId] });
      void queryClient.invalidateQueries({ queryKey: ["courses", "mastery-map", numericCourseId] });
      void queryClient.invalidateQueries({ queryKey: ["paths", "current", numericCourseId] });
      void queryClient.invalidateQueries({ queryKey: ["latest-report", numericCourseId] });
    },
    onError: () => {
      setLocalError("答案提交失败，请检查作答后重试。");
    }
  });

  function updateAnswer(questionId: string, value: string) {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  }

  function optionSelected(question: PracticeQuestion, option: string) {
    if (question.question_type !== "multiple_choice") {
      return answers[question.id] === option;
    }
    return (answers[question.id] ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
      .includes(option);
  }

  function updateOptionAnswer(question: PracticeQuestion, option: string) {
    if (question.question_type !== "multiple_choice") {
      updateAnswer(question.id, option);
      return;
    }
    const selected = (answers[question.id] ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const next = selected.includes(option)
      ? selected.filter((item) => item !== option)
      : [...selected, option];
    updateAnswer(question.id, next.join(", "));
  }

  return (
    <PageFrame title="练习">
      <div className="student-workspace practice-workspace">
        <section className="student-panel practice-question" role="region" aria-label="练习作答">
          <div className="student-panel-heading">
            <div>
              <h2>课程练习</h2>
            </div>
            <span className="panel-count">{currentSession?.score ?? "待评估"}</span>
          </div>

          <div className="path-generator practice-generator">
            <label>
              <span>课程</span>
              <select
                aria-label="选择课程"
                value={effectiveCourseId}
                onChange={(event) => {
                  setSelectedCourseId(event.target.value);
                  setSelectedPointId("");
                  setCurrentSession(null);
                  setAnswers({});
                }}
              >
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>知识点</span>
              <select aria-label="选择知识点" value={effectivePointId} onChange={(event) => setSelectedPointId(event.target.value)}>
                {knowledgePoints.map((point) => (
                  <option key={point.id} value={point.id}>
                    {point.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>题量</span>
              <select aria-label="题量" value={questionCount} onChange={(event) => setQuestionCount(Number(event.target.value))}>
                {[3, 5, 8, 10].map((count) => (
                  <option key={count} value={count}>
                    {count} 题
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>难度</span>
              <select aria-label="难度" value={difficulty} onChange={(event) => setDifficulty(event.target.value as typeof difficulty)}>
                <option value="easy">基础</option>
                <option value="medium">中等</option>
                <option value="hard">进阶</option>
              </select>
            </label>
            <button className="primary-action" type="button" disabled={!canUseCourse || createMutation.isPending} onClick={() => createMutation.mutate()}>
              生成练习
            </button>
          </div>

          {localError ? <p className="form-error">{localError}</p> : null}

          {currentSession ? (
            <div className="practice-question-list">
              {currentSession.questions.map((question, index) => {
                const feedback = feedbackByQuestion.get(question.id);
                return (
                  <article className="question-block" key={question.id}>
                    <strong>
                      <span>{index + 1}. </span>
                      <span>{question.prompt}</span>
                    </strong>
                    {question.options.length > 0 ? (
                      <div className="practice-options">
                        {question.options.map((option) => (
                          <button
                            key={option}
                            type="button"
                            className={optionSelected(question, option) ? "soft-button active" : "soft-button"}
                            onClick={() => updateOptionAnswer(question, option)}
                          >
                            {option}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    <label className="answer-box">
                      <span>作答区</span>
                      <textarea
                        rows={4}
                        aria-label={`${question.id} 作答区`}
                        value={answers[question.id] ?? feedback?.answer_text ?? ""}
                        onChange={(event) => updateAnswer(question.id, event.target.value)}
                        placeholder="写下你的答案或推导过程。"
                      />
                    </label>
                    {feedback ? (
                      <>
                        <div className={feedback.is_correct ? "feedback-status mastered" : "feedback-status"}>
                          {feedback.is_correct ? <CheckCircle size={22} weight="duotone" aria-hidden="true" /> : <WarningCircle size={22} weight="duotone" aria-hidden="true" />}
                          <span>
                            <strong>得分 {feedback.feedback.score}</strong>
                            <small>{feedback.feedback.message}</small>
                          </span>
                        </div>
                        {feedback.feedback.diagnosis ? (
                          <div className="practice-diagnosis" aria-label={`${question.id} 错因诊断`}>
                            <strong>错因诊断</strong>
                            <p>{feedback.feedback.diagnosis.misconception}</p>
                            {feedback.feedback.diagnosis.missing_concepts.length > 0 ? (
                              <div className="practice-diagnosis-concepts">
                                {feedback.feedback.diagnosis.missing_concepts.map((concept) => (
                                  <span key={concept}>{concept}</span>
                                ))}
                              </div>
                            ) : null}
                            <small>{feedback.feedback.diagnosis.recommended_action}</small>
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </article>
                );
              })}
              <button className="primary-action" type="button" disabled={submitMutation.isPending} onClick={() => submitMutation.mutate()}>
                提交答案
              </button>
            </div>
          ) : (
            <p className="empty-state">选择课程和知识点后生成练习。</p>
          )}
        </section>

        <aside className="practice-side-stack">
          <section className="student-panel feedback-panel" role="region" aria-label="批改反馈">
            <div className="feedback-status">
              <WarningCircle size={22} weight="duotone" aria-hidden="true" />
              <span>
                <strong>{currentSession?.status === "completed" ? "练习已完成" : "等待作答"}</strong>
                <small>{currentSession?.score !== null && currentSession?.score !== undefined ? `本次得分 ${currentSession.score}` : "提交后会生成即时反馈和复习线索。"}</small>
              </span>
            </div>
            <AgentTraceDisclosure traceId={currentSession?.agent_trace_id} label="查看 AssessmentGraph" />
            {currentSession?.closure_update ? (
              <div className="practice-closure-update">
                <strong>
                  {currentSession.closure_update.path_update_status === "replanned"
                    ? "已有路径已按本次练习重排"
                    : currentSession.closure_update.path_update_status === "failed"
                      ? "路径暂未更新，练习结果已保留"
                      : currentSession.closure_update.path_update_status === "not_started"
                        ? "课程还没有学习路径"
                        : "学习状态已更新"}
                </strong>
                <small>
                  新增 {currentSession.closure_update.weaknesses_added} 个弱点，更新 {currentSession.closure_update.weaknesses_updated} 个弱点
                </small>
                <Link className="soft-button" to={`${PATHS.path}?course_id=${numericCourseId}`}>
                  {currentSession.closure_update.path_update_status === "replanned" ? "查看更新后的路径" : "前往学习路径"}
                </Link>
                <AgentTraceDisclosure
                  traceId={currentSession.closure_update.path_agent_trace_id}
                  label="查看 PathPlanningGraph"
                />
              </div>
            ) : null}
          </section>

          <section className="student-panel review-queue" role="region" aria-label="薄弱点复习队列">
            <div className="student-panel-heading compact">
              <div>
                <h2>反馈线索</h2>
              </div>
            </div>
            <ol>
              {(currentSession?.answers ?? []).map((answer) => (
                <li className={answer.is_correct ? "" : "active"} key={answer.question_id}>
                  <ListChecks size={17} weight="duotone" aria-hidden="true" />
                  <span>{answer.feedback.message}</span>
                </li>
              ))}
              {!currentSession?.answers.length ? <li>完成练习后会形成真实复习线索。</li> : null}
            </ol>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
