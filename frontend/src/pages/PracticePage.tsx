import { CheckCircle, ListChecks, WarningCircle } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getKnowledgePoints, listCourses } from "../api/courses";
import {
  createPracticeSession,
  getLatestPracticeSession,
  getPracticeSession,
  savePracticeDraft,
  type PracticeQuestion,
  type PracticeSessionDetail,
  submitPracticeAnswers
} from "../api/practice";
import { PATHS } from "../app/routePaths";
import { AgentTraceDisclosure } from "../components/evidence/AgentTraceDisclosure";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { PageFrame } from "./PageFrame";
import { invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";

type PracticeSessionEnvelope = PracticeSessionDetail | { data?: PracticeSessionDetail };

function resolvePracticeSession(response: PracticeSessionEnvelope): PracticeSessionDetail | null {
  if ("questions" in response) {
    return response;
  }
  return response.data ?? null;
}

export function PracticePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const initialCourseId = searchParams.get("course_id") ?? "";
  const initialKnowledgePointId = searchParams.get("knowledge_point_id") ?? "";
  const sprintPlanId = Number(searchParams.get("sprint_plan_id") ?? "");
  const sprintTaskId = Number(searchParams.get("sprint_task_id") ?? "");
  const hasSprintSource = Number.isFinite(sprintPlanId) && sprintPlanId > 0 && Number.isFinite(sprintTaskId) && sprintTaskId > 0;
  const [selectedCourseId, setSelectedCourseId] = useState(initialCourseId);
  const [selectedPointId, setSelectedPointId] = useState(initialKnowledgePointId);
  const [questionCount, setQuestionCount] = useState(5);
  const [difficulty, setDifficulty] = useState<"adaptive" | "easy" | "medium" | "hard">("adaptive");
  const [currentSession, setCurrentSession] = useState<PracticeSessionDetail | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [localError, setLocalError] = useState("");
  const [draftStatus, setDraftStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const lastSavedDraftRef = useRef("");
  const activeDraftSessionRef = useRef("");
  const requestedSessionId = Number(searchParams.get("session_id") ?? "");
  const hasRequestedSession = Number.isFinite(requestedSessionId) && requestedSessionId > 0;
  const wantsNewPractice = searchParams.get("new") === "1";

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
  const requestedSessionQuery = useQuery({
    queryKey: ["practice-session", requestedSessionId],
    queryFn: () => getPracticeSession(requestedSessionId),
    enabled: hasRequestedSession
  });
  const latestSessionQuery = useQuery({
    queryKey: ["practice-latest", numericCourseId],
    queryFn: () => getLatestPracticeSession(numericCourseId),
    enabled: canUseCourse && !hasRequestedSession && !wantsNewPractice
  });
  const restoredCandidate = hasRequestedSession ? requestedSessionQuery.data?.data : latestSessionQuery.data?.data;
  const restoredSession = restoredCandidate && Array.isArray(restoredCandidate.questions) ? restoredCandidate : null;
  const activeSession = currentSession ?? restoredSession ?? null;
  const effectiveAnswers = useMemo(
    () => ({
      ...Object.fromEntries((activeSession?.answers ?? []).map((answer) => [answer.question_id, answer.answer_text ?? ""])),
      ...answers
    }),
    [activeSession?.answers, answers]
  );

  useEffect(() => {
    if (restoredSession && !hasRequestedSession) {
      setSearchParams({ course_id: restoredSession.course_id, session_id: restoredSession.id }, { replace: true });
    }
  }, [hasRequestedSession, restoredSession, setSearchParams]);

  useEffect(() => {
    if (!activeSession || activeSession.status !== "in_progress") {
      return;
    }
    const snapshot = JSON.stringify(effectiveAnswers);
    if (activeDraftSessionRef.current !== activeSession.id) {
      activeDraftSessionRef.current = activeSession.id;
      lastSavedDraftRef.current = snapshot;
      return;
    }
    if (snapshot === lastSavedDraftRef.current) {
      return;
    }
    const timeout = window.setTimeout(() => {
      setDraftStatus("saving");
      void savePracticeDraft(Number(activeSession.id), {
        answers: activeSession.questions.map((question) => ({
          question_id: question.id,
          answer_text: effectiveAnswers[question.id] ?? ""
        }))
      })
        .then(() => {
          lastSavedDraftRef.current = snapshot;
          setDraftStatus("saved");
        })
        .catch(() => setDraftStatus("error"));
    }, 650);
    return () => window.clearTimeout(timeout);
  }, [activeSession, effectiveAnswers]);

  const feedbackByQuestion = useMemo(() => {
    const result = new Map<string, PracticeSessionDetail["answers"][number]>();
    for (const answer of activeSession?.answers ?? []) {
      result.set(answer.question_id, answer);
    }
    return result;
  }, [activeSession]);

  const createMutation = useMutation({
    mutationFn: () =>
      createPracticeSession({
        course_id: numericCourseId,
        knowledge_point_ids: selectedPointIds,
        question_count: questionCount,
        difficulty,
        sprint_plan_id: hasSprintSource ? sprintPlanId : undefined,
        sprint_task_id: hasSprintSource ? sprintTaskId : undefined
      }),
    onSuccess: (response) => {
      setLocalError("");
      const created = resolvePracticeSession(response);
      setCurrentSession(created);
      setAnswers({});
      lastSavedDraftRef.current = "{}";
      setDraftStatus("idle");
      if (created) {
        setSearchParams({ course_id: created.course_id, session_id: created.id }, { replace: true });
      }
    },
    onError: () => {
      setLocalError("练习生成失败，请稍后重试。");
    }
  });

  const submitMutation = useMutation({
    mutationFn: () => {
      if (!activeSession) {
        throw new Error("missing session");
      }
      return submitPracticeAnswers(Number(activeSession.id), {
        answers: activeSession.questions.map((question) => ({
          question_id: question.id,
          answer_text: effectiveAnswers[question.id] ?? ""
        }))
      });
    },
    onSuccess: (response) => {
      setLocalError("");
      setCurrentSession(resolvePracticeSession(response));
      lastSavedDraftRef.current = JSON.stringify(answers);
      setDraftStatus("saved");
      void invalidateCourseLearningLoop(queryClient, numericCourseId);
      void queryClient.invalidateQueries({ queryKey: ["exam-sprint", "current", numericCourseId] });
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
            <span className="panel-count">{activeSession?.score ?? "待评估"}</span>
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
                  lastSavedDraftRef.current = "";
                  setDraftStatus("idle");
                  setSearchParams({ course_id: event.target.value }, { replace: true });
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
                <option value="adaptive">智能适配</option>
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
          {requestedSessionQuery.isError || latestSessionQuery.isError ? <p className="form-error">练习恢复失败，请稍后重试。</p> : null}
          {activeSession?.status === "in_progress" && draftStatus !== "idle" ? (
            <p className={`practice-draft-status ${draftStatus}`} role="status">
              {draftStatus === "saving" ? "正在保存草稿" : draftStatus === "saved" ? "草稿已保存" : "草稿保存失败，将继续保留当前输入"}
            </p>
          ) : null}

          {activeSession ? (
            <div className="practice-question-list">
              {activeSession.questions.map((question, index) => {
                const feedback = feedbackByQuestion.get(question.id);
                const evaluatedFeedback = feedback?.is_correct === null || feedback?.is_correct === undefined ? null : feedback;
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
                            disabled={activeSession.status === "completed"}
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
                        value={effectiveAnswers[question.id] ?? feedback?.answer_text ?? ""}
                        onChange={(event) => updateAnswer(question.id, event.target.value)}
                        placeholder="写下你的答案或推导过程。"
                        disabled={activeSession.status === "completed"}
                      />
                    </label>
                    {evaluatedFeedback ? (
                      <>
                        <div className={evaluatedFeedback.is_correct ? "feedback-status mastered" : "feedback-status"}>
                          {evaluatedFeedback.is_correct ? <CheckCircle size={22} weight="duotone" aria-hidden="true" /> : <WarningCircle size={22} weight="duotone" aria-hidden="true" />}
                          <span>
                            <strong>得分 {evaluatedFeedback.feedback.score}</strong>
                            <small>{evaluatedFeedback.feedback.message}</small>
                          </span>
                        </div>
                        {evaluatedFeedback.feedback.diagnosis ? (
                          <div className="practice-diagnosis" aria-label={`${question.id} 错因诊断`}>
                            <strong>错因诊断</strong>
                            <p>{evaluatedFeedback.feedback.diagnosis.misconception}</p>
                            {evaluatedFeedback.feedback.diagnosis.missing_concepts.length > 0 ? (
                              <div className="practice-diagnosis-concepts">
                                {evaluatedFeedback.feedback.diagnosis.missing_concepts.map((concept) => (
                                  <span key={concept}>{concept}</span>
                                ))}
                              </div>
                            ) : null}
                            <small>{evaluatedFeedback.feedback.diagnosis.recommended_action}</small>
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </article>
                );
              })}
              {activeSession.status === "completed" ? (
                <button
                  className="primary-action"
                  type="button"
                  onClick={() => {
                    setCurrentSession(null);
                    setAnswers({});
                    lastSavedDraftRef.current = "";
                    setDraftStatus("idle");
                    setSearchParams({ course_id: activeSession.course_id, new: "1" }, { replace: true });
                  }}
                >
                  开始新练习
                </button>
              ) : (
                <button className="primary-action" type="button" disabled={submitMutation.isPending} onClick={() => submitMutation.mutate()}>
                  提交答案
                </button>
              )}
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
                <strong>{activeSession?.status === "completed" ? "练习已完成" : "等待作答"}</strong>
                <small>
                  {activeSession?.score !== null && activeSession?.score !== undefined
                    ? `本次得分 ${activeSession.score}${activeSession.requested_difficulty === "adaptive" ? ` · 智能适配为${activeSession.effective_difficulty === "easy" ? "基础" : activeSession.effective_difficulty === "hard" ? "进阶" : "中等"}` : ""}`
                    : activeSession
                      ? `实际难度：${activeSession.effective_difficulty === "easy" ? "基础" : activeSession.effective_difficulty === "hard" ? "进阶" : "中等"}`
                      : "提交后会生成即时反馈和复习线索。"}
                </small>
              </span>
            </div>
            <AgentTraceDisclosure traceId={activeSession?.agent_trace_id} label="查看 AssessmentGraph" />
            {activeSession?.closure_update ? (
              <div className="practice-closure-update">
                <strong>
                  {activeSession.closure_update.path_update_status === "replanned"
                    ? "已有路径已按本次练习重排"
                    : activeSession.closure_update.path_update_status === "failed"
                      ? "路径暂未更新，练习结果已保留"
                      : activeSession.closure_update.path_update_status === "not_started"
                        ? "课程还没有学习路径"
                        : "学习状态已更新"}
                </strong>
                <small>
                  新增 {activeSession.closure_update.weaknesses_added} 个弱点，更新 {activeSession.closure_update.weaknesses_updated} 个弱点
                </small>
                <Link className="soft-button" to={`${PATHS.path}?course_id=${numericCourseId}`}>
                  {activeSession.closure_update.path_update_status === "replanned" ? "查看更新后的路径" : "前往学习路径"}
                </Link>
                <AgentTraceDisclosure
                  traceId={activeSession.closure_update.path_agent_trace_id}
                  label="查看 PathPlanningGraph"
                />
                {activeSession.closure_update.sprint_update_status === "replanned" && activeSession.closure_update.sprint_plan_id ? (
                  <>
                    <strong>期末冲刺计划已根据本次必刷题重排</strong>
                    <Link className="soft-button" to={`${PATHS.path}?course_id=${numericCourseId}&sprint_plan_id=${activeSession.closure_update.sprint_plan_id}`}>
                      查看更新后的冲刺计划
                    </Link>
                    <AgentTraceDisclosure
                      traceId={activeSession.closure_update.sprint_agent_trace_id}
                      label="查看 ExamSprintGraph"
                    />
                  </>
                ) : activeSession.closure_update.sprint_update_status === "failed" ? (
                  <InlineFeedback message="冲刺计划暂未更新，练习结果和弱点已保留。" tone="warning" />
                ) : null}
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
              {(activeSession?.answers ?? []).map((answer) => (
                <li className={answer.is_correct ? "" : "active"} key={answer.question_id}>
                  <ListChecks size={17} weight="duotone" aria-hidden="true" />
                  <span>{answer.feedback.message}</span>
                </li>
              ))}
              {!activeSession?.answers.length ? <li>完成练习后会形成真实复习线索。</li> : null}
            </ol>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
