import { ArrowLeft, ArrowRight, CheckCircle, ClipboardText, SlidersHorizontal, WarningCircle } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { getKnowledgePoints, listCourses } from "../api/courses";
import { createIdempotencyKey, createPracticeGenerationJob, type AiJob } from "../api/aiJobs";
import {
  getLatestPracticeSession,
  getPracticeSession,
  regradePracticeAnswers,
  savePracticeDraft,
  type PracticeSessionDetail,
  submitPracticeAnswers
} from "../api/practice";
import { listResources } from "../api/resources";
import { CourseReturnLink } from "../components/course-space/CourseReturnLink";
import { PracticeDrawer, type PracticeDrawerMode } from "../components/practice/PracticeDrawer";
import { PracticeQuestionCanvas } from "../components/practice/PracticeQuestionCanvas";
import { PracticeQuestionRail } from "../components/practice/PracticeQuestionRail";
import { PracticeResultSummary } from "../components/practice/PracticeResultSummary";
import { PracticeToolbar } from "../components/practice/PracticeToolbar";
import { ConfirmDialog } from "../components/primitives/Dialog";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";
import {
  isAnswered,
  practiceResultSummary
} from "../features/practice/practiceViewModel";
import { selectResumablePracticeJob } from "../features/practice/practiceJobSelection";
import { useLearningNextAction } from "../features/learning-actions/learningActions";
import { PageFrame } from "./PageFrame";
import { buildCoursePracticeWorkspacePath } from "../app/routePaths";
import "../styles/practice.css";

type PracticeSessionEnvelope = PracticeSessionDetail | { data?: PracticeSessionDetail };

function resolvePracticeSession(response: PracticeSessionEnvelope): PracticeSessionDetail | null {
  if ("questions" in response) return response;
  return response.data ?? null;
}

function draftLabel(status: "idle" | "saving" | "saved" | "error") {
  if (status === "saving") return "正在保存草稿";
  if (status === "saved") return "草稿已保存";
  if (status === "error") return "草稿保存失败，当前输入仍保留";
  return null;
}

export function PracticePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { courseId: routeCourseId } = useParams();
  const queryClient = useQueryClient();
  const initialCourseId = searchParams.get("course_id") ?? "";
  const lockedCourseId = routeCourseId ?? "";
  const initialKnowledgePointId = searchParams.get("knowledge_point_id") ?? "";
  const initialWeaknessItemId = Number(searchParams.get("weakness_item_id") ?? "");
  const [selectedCourseId, setSelectedCourseId] = useState(lockedCourseId || initialCourseId);
  const [selectedPointId, setSelectedPointId] = useState(initialKnowledgePointId);
  const requestedQuestionCount = Number(searchParams.get("question_count") ?? 5);
  const [questionCount, setQuestionCount] = useState(
    Number.isFinite(requestedQuestionCount) ? Math.min(10, Math.max(1, Math.round(requestedQuestionCount))) : 5
  );
  const [difficulty, setDifficulty] = useState<"adaptive" | "easy" | "medium" | "hard">("adaptive");
  const [currentSession, setCurrentSession] = useState<PracticeSessionDetail | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [localError, setLocalError] = useState("");
  const [draftStatus, setDraftStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [drawerMode, setDrawerMode] = useState<PracticeDrawerMode | null>(null);
  const [confirmIncomplete, setConfirmIncomplete] = useState(false);
  const [reviewExpansionOverrides, setReviewExpansionOverrides] = useState<Record<string, boolean>>({});
  const [practiceJobId, setPracticeJobId] = useState<string | null>(null);
  const lastSavedDraftRef = useRef("");
  const activeDraftSessionRef = useRef("");
  const handledPracticeJobRef = useRef<string | null>(null);
  const { jobs, trackJob } = useAiJobs();
  const requestedSessionId = Number(searchParams.get("session_id") ?? "");
  const hasRequestedSession = Number.isFinite(requestedSessionId) && requestedSessionId > 0;
  const requestedQuestionId = searchParams.get("question_id");
  const wantsNewPractice = searchParams.get("new") === "1";

  useEffect(() => {
    if (!searchParams.has("sprint_plan_id") && !searchParams.has("sprint_task_id")) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("sprint_plan_id");
    nextParams.delete("sprint_task_id");
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  const coursesQuery = useQuery({ queryKey: ["practice-courses"], queryFn: () => listCourses() });
  const courses = Array.isArray(coursesQuery.data?.data) ? coursesQuery.data.data : [];
  const effectiveCourseId = lockedCourseId || selectedCourseId || courses.find((course) => course.is_current)?.id || "";
  const numericCourseId = Number(effectiveCourseId);
  const canUseCourse = Number.isFinite(numericCourseId) && numericCourseId > 0;
  useEffect(() => {
    if (lockedCourseId || !canUseCourse) return;
    const next = new URLSearchParams(searchParams);
    next.delete("course_id");
    navigate(`${buildCoursePracticeWorkspacePath(numericCourseId)}${next.size ? `?${next.toString()}` : ""}`, { replace: true });
  }, [canUseCourse, lockedCourseId, navigate, numericCourseId, searchParams]);

  const pointsQuery = useQuery({
    queryKey: ["practice-knowledge-points", numericCourseId],
    queryFn: () => getKnowledgePoints(numericCourseId),
    enabled: canUseCourse
  });
  const knowledgePoints = Array.isArray(pointsQuery.data?.data) ? pointsQuery.data.data : [];
  const hasSelectedPoint = knowledgePoints.some((point) => point.id === selectedPointId);
  const effectivePointId = hasSelectedPoint ? selectedPointId : (knowledgePoints[0]?.id ?? "");
  const selectedPointIds = effectivePointId ? [Number(effectivePointId)] : [];
  const requestedSessionQuery = useQuery({
    queryKey: ["practice-session", requestedSessionId],
    queryFn: () => getPracticeSession(requestedSessionId),
    enabled: hasRequestedSession
  });
  const latestSessionQuery = useQuery({
    queryKey: courseLoopQueryKeys.latestPractice(numericCourseId),
    queryFn: () => getLatestPracticeSession(numericCourseId),
    enabled: canUseCourse && !hasRequestedSession && !wantsNewPractice
  });
  const resourcesQuery = useQuery({
    queryKey: courseLoopQueryKeys.resources(numericCourseId),
    queryFn: () => listResources({ courseId: numericCourseId }),
    enabled: canUseCourse,
    staleTime: 10_000
  });
  const restoredCandidate = hasRequestedSession
    ? requestedSessionQuery.data?.data
    : (wantsNewPractice ? null : latestSessionQuery.data?.data);
  const restoredSession = restoredCandidate && Array.isArray(restoredCandidate.questions) ? restoredCandidate : null;
  const activeSession = currentSession ?? restoredSession ?? null;
  const activeQuestion = activeSession?.questions.find((question) => question.id === requestedQuestionId)
    ?? activeSession?.questions[0]
    ?? null;
  const activeQuestionIndex = activeQuestion
    ? activeSession?.questions.findIndex((question) => question.id === activeQuestion.id) ?? 0
    : 0;
  const effectiveAnswers = useMemo(
    () => ({
      ...Object.fromEntries((activeSession?.answers ?? []).map((answer) => [answer.question_id, answer.answer_text ?? ""])),
      ...answers
    }),
    [activeSession?.answers, answers]
  );
  const feedbackByQuestion = useMemo(
    () => new Map((activeSession?.answers ?? []).map((answer) => [answer.question_id, answer])),
    [activeSession?.answers]
  );
  const unansweredQuestions = activeSession?.questions.filter((question) => !isAnswered(effectiveAnswers[question.id])) ?? [];
  const answeredCount = (activeSession?.questions.length ?? 0) - unansweredQuestions.length;
  const completed = activeSession?.status === "completed";
  const resultSummary = practiceResultSummary(activeSession?.questions ?? [], activeSession?.answers ?? []);
  const nextActionQuery = useLearningNextAction(canUseCourse ? numericCourseId : null);
  const recommendedResourceIdSet = new Set(activeSession?.closure_update?.recommended_resource_ids ?? []);
  const courseResources = Array.isArray(resourcesQuery.data?.data) ? resourcesQuery.data.data : [];
  const recommendedResources = courseResources.filter((resource) => recommendedResourceIdSet.has(resource.id));
  const selectedCourseTitle = courses.find((course) => course.id === effectiveCourseId)?.title ?? "";
  const selectedPointTitle = knowledgePoints.find((point) => point.id === effectivePointId)?.title ?? "";
  const requestedWeaknessItemId = Number.isFinite(initialWeaknessItemId) && initialWeaknessItemId > 0
    ? initialWeaknessItemId
    : null;
  const resumablePracticeJob = selectResumablePracticeJob(jobs, numericCourseId, requestedWeaknessItemId);
  const practiceJob = jobs.find((job) => job.job_id === practiceJobId) ?? resumablePracticeJob;
  const practiceJobRunning = practiceJob?.status === "queued" || practiceJob?.status === "running" || practiceJob?.status === "cancelling";
  const practiceJobError = practiceJob?.status === "failed" || practiceJob?.status === "cancelled"
    ? practiceJob.error_message || "练习生成失败，可在任务托盘中重试。"
    : "";

  useEffect(() => {
    if (practiceJobId || !resumablePracticeJob) return;
    const timeoutId = window.setTimeout(() => setPracticeJobId(resumablePracticeJob.job_id), 0);
    return () => window.clearTimeout(timeoutId);
  }, [practiceJobId, resumablePracticeJob]);

  useEffect(() => {
    if (!practiceJob || handledPracticeJobRef.current === practiceJob.job_id) return;
    if (practiceJob.status !== "completed") return;
    const sessionId = Number(practiceJob.result.session_id);
    if (!Number.isFinite(sessionId) || sessionId <= 0) {
      handledPracticeJobRef.current = practiceJob.job_id;
      return;
    }
    handledPracticeJobRef.current = practiceJob.job_id;
    void getPracticeSession(sessionId).then((response) => {
      const created = resolvePracticeSession(response.data);
      if (!created) throw new Error("missing practice session");
      setLocalError("");
      setCurrentSession(created);
      setAnswers({});
      setReviewExpansionOverrides({});
      lastSavedDraftRef.current = "{}";
      setDraftStatus("idle");
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("course_id", created.course_id);
      nextParams.set("session_id", created.id);
      if (created.questions[0]) nextParams.set("question_id", created.questions[0].id);
      nextParams.delete("new");
      setSearchParams(nextParams, { replace: true });
    }).catch(() => setLocalError("练习已生成，请刷新页面恢复。"));
  }, [practiceJob, searchParams, setSearchParams]);

  useEffect(() => {
    if (!restoredSession || hasRequestedSession) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("course_id", restoredSession.course_id);
    nextParams.set("session_id", restoredSession.id);
    if (restoredSession.questions[0]) nextParams.set("question_id", restoredSession.questions[0].id);
    nextParams.delete("new");
    setSearchParams(nextParams, { replace: true });
  }, [hasRequestedSession, restoredSession, searchParams, setSearchParams]);

  useEffect(() => {
    if (!activeSession?.questions.length || activeSession.questions.some((question) => question.id === requestedQuestionId)) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("course_id", activeSession.course_id);
    nextParams.set("session_id", activeSession.id);
    nextParams.set("question_id", activeSession.questions[0].id);
    nextParams.delete("new");
    setSearchParams(nextParams, { replace: true });
  }, [activeSession, requestedQuestionId, searchParams, setSearchParams]);

  useEffect(() => {
    if (!activeSession || activeSession.status !== "in_progress") return;
    const snapshot = JSON.stringify(effectiveAnswers);
    if (activeDraftSessionRef.current !== activeSession.id) {
      activeDraftSessionRef.current = activeSession.id;
      lastSavedDraftRef.current = snapshot;
      return;
    }
    if (snapshot === lastSavedDraftRef.current) return;
    const timeout = window.setTimeout(() => {
      setDraftStatus("saving");
      void savePracticeDraft(Number(activeSession.id), {
        answers: activeSession.questions.map((question) => ({ question_id: question.id, answer_text: effectiveAnswers[question.id] ?? "" }))
      }).then(() => {
        lastSavedDraftRef.current = snapshot;
        setDraftStatus("saved");
      }).catch(() => setDraftStatus("error"));
    }, 650);
    return () => window.clearTimeout(timeout);
  }, [activeSession, effectiveAnswers]);

  const createMutation = useMutation({
    mutationFn: () => createPracticeGenerationJob({
      course_id: numericCourseId,
      knowledge_point_ids: selectedPointIds,
      ...(Number.isFinite(initialWeaknessItemId) && initialWeaknessItemId > 0 ? { weakness_item_id: initialWeaknessItemId } : {}),
      question_count: questionCount,
      difficulty
    }, createIdempotencyKey(`practice-${numericCourseId}`)),
    onSuccess: (job: AiJob) => {
      setLocalError("");
      handledPracticeJobRef.current = null;
      setPracticeJobId(job.job_id);
      trackJob(job);
      setDrawerMode(null);
    },
    onError: () => setLocalError("练习任务创建失败，请稍后重试。")
  });

  const submitMutation = useMutation({
    mutationFn: () => {
      if (!activeSession) throw new Error("missing session");
      return submitPracticeAnswers(Number(activeSession.id), {
        answers: activeSession.questions.map((question) => ({
          question_id: question.id,
          answer_text: isAnswered(effectiveAnswers[question.id]) ? effectiveAnswers[question.id] : "未作答"
        }))
      });
    },
    onSuccess: (response) => {
      const evaluated = resolvePracticeSession(response);
      if (!evaluated) {
        setLocalError("答案提交失败，请检查作答后重试。");
        return;
      }
      setLocalError("");
      setCurrentSession(evaluated);
      lastSavedDraftRef.current = JSON.stringify(answers);
      setDraftStatus("saved");
      setConfirmIncomplete(false);
      const firstWrongId = evaluated.answers.find((answer) => answer.is_correct === false)?.question_id;
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("question_id", firstWrongId ?? evaluated.questions[0]?.id ?? "");
      setSearchParams(nextParams, { replace: true });
      void invalidateCourseLearningLoop(queryClient, numericCourseId);
    },
    onError: () => {
      setConfirmIncomplete(false);
      setLocalError("答案提交失败，请检查作答后重试。");
    }
  });

  const regradeMutation = useMutation({
    mutationFn: () => {
      if (!activeSession) throw new Error("missing session");
      return regradePracticeAnswers(Number(activeSession.id));
    },
    onSuccess: (response) => {
      const evaluated = resolvePracticeSession(response);
      if (evaluated) {
        setCurrentSession(evaluated);
        setLocalError(evaluated.grading_status === "complete" ? "" : "简答题仍暂未评分，请检查模型配置后重试。");
        void invalidateCourseLearningLoop(queryClient, numericCourseId);
      }
    },
    onError: () => setLocalError("简答题重评失败，原有评分结果已保留。")
  });

  function selectQuestion(questionId: string) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("question_id", questionId);
    setSearchParams(nextParams, { replace: true });
  }

  function updateAnswer(questionId: string, value: string) {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  }

  function changeCourse(courseId: string) {
    setSelectedCourseId(courseId);
    setSelectedPointId("");
    setCurrentSession(null);
    setAnswers({});
    setDraftStatus("idle");
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("course_id", courseId);
    nextParams.delete("knowledge_point_id");
    nextParams.delete("weakness_item_id");
    nextParams.delete("session_id");
    nextParams.delete("question_id");
    nextParams.set("new", "1");
    setSearchParams(nextParams, { replace: true });
  }

  function startNewPractice() {
    setCurrentSession(null);
    setAnswers({});
    setReviewExpansionOverrides({});
    setDraftStatus("idle");
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("course_id", activeSession?.course_id ?? effectiveCourseId);
    nextParams.set("new", "1");
    nextParams.delete("session_id");
    nextParams.delete("question_id");
    nextParams.delete("weakness_item_id");
    setSearchParams(nextParams, { replace: true });
    setDrawerMode("settings");
  }

  function requestSubmit() {
    if (unansweredQuestions.length > 0) {
      setConfirmIncomplete(true);
      return;
    }
    submitMutation.mutate();
  }

  function cancelIncompleteSubmit() {
    setConfirmIncomplete(false);
    if (unansweredQuestions[0]) selectQuestion(unansweredQuestions[0].id);
  }

  const loadingSession = hasRequestedSession
    ? requestedSessionQuery.isPending
    : practiceJobRunning || (canUseCourse && !wantsNewPractice && latestSessionQuery.isPending);
  const restoreError = requestedSessionQuery.isError || latestSessionQuery.isError;

  return (
    <>
      <PageFrame title="练习" titleMode="sr-only" variant="wide-workspace" courseId={numericCourseId || null}>
        <div className="practice-focus-workspace">
        <PracticeToolbar
          courseTitle={selectedCourseTitle}
          pointTitle={activeQuestion?.knowledge_point_title || selectedPointTitle}
          session={activeSession}
          activeIndex={activeQuestionIndex}
          answeredCount={answeredCount}
          draftLabel={activeSession?.status === "in_progress" ? draftLabel(draftStatus) : null}
          returnLink={<CourseReturnLink courseId={canUseCourse ? numericCourseId : null} compact alwaysShow={Boolean(lockedCourseId)} />}
          onOpenSettings={() => setDrawerMode("settings")}
          onOpenResults={() => setDrawerMode("results")}
        />

        {activeSession && activeQuestion ? (
          <div className="practice-session-layout">
            <PracticeQuestionRail
              questions={activeSession.questions}
              answers={effectiveAnswers}
              evaluatedAnswers={activeSession.answers}
              activeQuestionId={activeQuestion.id}
              completed={completed}
              onSelect={selectQuestion}
            />
            <main className="practice-session-main">
              <div className="practice-session-scroll">
              {completed ? (
                <PracticeResultSummary
                  score={activeSession.score}
                  gradingStatus={activeSession.grading_status}
                  correctCount={resultSummary.correctCount}
                  gradedCount={resultSummary.gradedCount}
                  totalCount={resultSummary.totalCount}
                  effectiveDifficulty={activeSession.effective_difficulty}
                  nextAction={nextActionQuery.data?.data ?? null}
                  onStartNew={startNewPractice}
                  onOpenResults={() => setDrawerMode("results")}
                  onRegrade={() => regradeMutation.mutate()}
                  isRegrading={regradeMutation.isPending}
                />
              ) : null}
              {localError || practiceJobError ? <p className="practice-local-error" role="alert">{localError || practiceJobError}</p> : null}
              <PracticeQuestionCanvas
                question={activeQuestion}
                index={activeQuestionIndex}
                total={activeSession.questions.length}
                value={effectiveAnswers[activeQuestion.id] ?? ""}
                feedback={feedbackByQuestion.get(activeQuestion.id) ?? null}
                completed={completed}
                reviewExpanded={reviewExpansionOverrides[activeQuestion.id]
                  ?? (feedbackByQuestion.get(activeQuestion.id)?.is_correct === false)}
                onAnswer={(value) => updateAnswer(activeQuestion.id, value)}
                onToggleReview={() => setReviewExpansionOverrides((current) => ({
                  ...current,
                  [activeQuestion.id]: !(current[activeQuestion.id]
                    ?? (feedbackByQuestion.get(activeQuestion.id)?.is_correct === false))
                }))}
              />
              </div>
              <footer className="practice-session-actions">
                <button type="button" disabled={activeQuestionIndex <= 0} onClick={() => selectQuestion(activeSession.questions[activeQuestionIndex - 1].id)}>
                  <ArrowLeft size={17} weight="bold" aria-hidden="true" />上一题
                </button>
                <span>{completed ? "逐题回看批改结果" : `还有 ${unansweredQuestions.length} 题未答`}</span>
                <button type="button" disabled={activeQuestionIndex >= activeSession.questions.length - 1} onClick={() => selectQuestion(activeSession.questions[activeQuestionIndex + 1].id)}>
                  下一题<ArrowRight size={17} weight="bold" aria-hidden="true" />
                </button>
                {completed ? (
                  <button className="primary" type="button" onClick={startNewPractice}>开始新练习</button>
                ) : (
                  <button className="primary" type="button" disabled={submitMutation.isPending} onClick={requestSubmit}>
                    <CheckCircle size={18} weight="bold" aria-hidden="true" />{submitMutation.isPending ? "正在提交" : "提交练习"}
                  </button>
                )}
              </footer>
            </main>
          </div>
        ) : (
          <main className="practice-empty-canvas">
            {loadingSession ? (
              <div className="practice-loading-state" role="status"><span /><span /><span /></div>
            ) : (
              <>
                {restoreError ? <WarningCircle size={34} weight="duotone" aria-hidden="true" /> : <ClipboardText size={38} weight="duotone" aria-hidden="true" />}
                <h2>{restoreError ? "暂时无法恢复上次练习" : selectedPointTitle ? "开始针对性练习" : "选择知识点开始练习"}</h2>
                <p>{restoreError ? "当前选择和返回上下文仍然保留，可以重试恢复或创建新练习。" : selectedPointTitle ? "练习难度会根据当前学习状态自动调整。" : "在练习设置中选择课程和知识点。"}</p>
                <button type="button" disabled={!canUseCourse || knowledgePoints.length === 0} onClick={() => setDrawerMode("settings")}>
                  <SlidersHorizontal size={18} weight="bold" aria-hidden="true" />
                  {restoreError ? "调整并重新开始" : "开始针对性练习"}
                </button>
                {!canUseCourse ? <Link to="/app/library">先到资料库创建课程</Link> : null}
                {canUseCourse && knowledgePoints.length === 0 ? <small>这门课程还没有可练习的知识点。</small> : null}
              </>
            )}
          </main>
        )}

        </div>
      </PageFrame>

      {drawerMode ? (
          <PracticeDrawer
            mode={drawerMode}
            courses={courses}
            courseLocked={Boolean(lockedCourseId)}
            points={knowledgePoints}
            courseId={effectiveCourseId}
            pointId={effectivePointId}
            questionCount={questionCount}
            difficulty={difficulty}
            session={activeSession}
            recommendedResources={recommendedResources}
            isGenerating={createMutation.isPending || practiceJobRunning}
            canGenerate={canUseCourse && selectedPointIds.length > 0}
            error={localError || practiceJobError}
            onCourseChange={changeCourse}
            onPointChange={setSelectedPointId}
            onQuestionCountChange={setQuestionCount}
            onDifficultyChange={setDifficulty}
            onGenerate={() => { if (!practiceJobRunning) createMutation.mutate(); }}
            onClose={() => setDrawerMode(null)}
          />
        ) : null}

      {confirmIncomplete ? (
        <ConfirmDialog
          open
          title={`还有 ${unansweredQuestions.length} 题未作答`}
          description="确认提交后，未答题会按未作答参与本次学习诊断。"
          confirmLabel="仍然提交"
          layerClassName="practice-confirm-layer"
          onOpenChange={(open) => { if (!open) cancelIncompleteSubmit(); }}
          onConfirm={() => submitMutation.mutate()}
        >
            <section aria-labelledby="practice-confirm-title">
              <WarningCircle size={28} weight="duotone" aria-hidden="true" />
              <h2 id="practice-confirm-title">还有 {unansweredQuestions.length} 题未作答</h2>
              <p>确认提交后，未答题会按未作答参与本次学习诊断。</p>
              <div>
                <button type="button" onClick={cancelIncompleteSubmit}>返回未答题</button>
                <button className="primary" type="button" onClick={() => submitMutation.mutate()}>仍然提交</button>
              </div>
            </section>
        </ConfirmDialog>
      ) : null}
    </>
  );
}
