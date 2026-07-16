import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getMasteryMap, listCourses } from "../api/courses";
import { createIdempotencyKey, createReportGenerationJob, type AiJob } from "../api/aiJobs";
import {
  createLearningDossierExportJob,
  downloadExportJob,
  getExportJob,
  type ExportFormat,
  type ExportJob
} from "../api/exports";
import { listRecentCompletedPracticeSessions } from "../api/practice";
import { getLatestReport } from "../api/reports";
import { PATHS } from "../app/routePaths";
import { CourseReturnLink } from "../components/course-space/CourseReturnLink";
import { ReportDashboard } from "../components/reports/ReportDashboard";
import { ReportDrawer, type ReportDetailTab, type ReportDrawerMode } from "../components/reports/ReportDrawer";
import { ReportWorkspaceToolbar } from "../components/reports/ReportWorkspaceToolbar";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";
import {
  buildCurrentTrendScores,
  calculateAverageMastery,
  calculateCurrentTrend,
  getReportFreshness,
  sortMasteryPoints
} from "../features/reports/reportViewModel";
import { useLearningNextAction } from "../features/learning-actions/learningActions";
import { PageFrame } from "./PageFrame";
import "../styles/reports.css";

function downloadDossierFile(filename: string, file: Blob, contentType: string) {
  const blob = file instanceof Blob ? file : new Blob([file], { type: contentType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 10_000);
}

function exportFormatLabel(format: ExportFormat) {
  if (format === "pdf") return "PDF";
  if (format === "docx") return "DOCX";
  return "Markdown";
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

const EXPORT_POLL_INTERVAL_MS = 1000;
const EXPORT_POLL_TIMEOUT_MS = 120_000;

class ExportPollingTimeoutError extends Error {}

async function waitForExportJob(initialJob: ExportJob) {
  let job = initialJob;
  const deadline = Date.now() + EXPORT_POLL_TIMEOUT_MS;
  while (job.status !== "completed" && job.status !== "failed") {
    if (Date.now() >= deadline) throw new ExportPollingTimeoutError("export job is still running");
    const refreshed = await getExportJob(job.job_id);
    job = refreshed.data;
    if (job.status !== "completed" && job.status !== "failed") await delay(EXPORT_POLL_INTERVAL_MS);
  }
  return job;
}

export function ReportsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [drawerMode, setDrawerMode] = useState<ReportDrawerMode>(null);
  const [detailTab, setDetailTab] = useState<ReportDetailTab>("summary");
  const [localError, setLocalError] = useState("");
  const [exportError, setExportError] = useState("");
  const [exportMessage, setExportMessage] = useState("");
  const [exportFormat, setExportFormat] = useState<ExportFormat>("markdown");
  const [reportJobId, setReportJobId] = useState<string | null>(null);
  const invalidatedReportJobRef = useRef<string | null>(null);
  const { jobs, trackJob } = useAiJobs();

  const coursesQuery = useQuery({ queryKey: ["report-courses"], queryFn: () => listCourses() });
  const courses = coursesQuery.data?.data ?? [];
  const effectiveCourseId = searchParams.get("course_id") || courses[0]?.id || "";
  const numericCourseId = Number(effectiveCourseId);
  const canUseCourse = Number.isFinite(numericCourseId) && numericCourseId > 0;

  const latestReportQuery = useQuery({
    queryKey: courseLoopQueryKeys.latestReport(numericCourseId),
    queryFn: () => getLatestReport(numericCourseId),
    enabled: canUseCourse
  });
  const masteryQuery = useQuery({
    queryKey: courseLoopQueryKeys.masteryMap(numericCourseId),
    queryFn: () => getMasteryMap(numericCourseId),
    enabled: canUseCourse
  });
  const recentPracticesQuery = useQuery({
    queryKey: courseLoopQueryKeys.recentPractices(numericCourseId),
    queryFn: () => listRecentCompletedPracticeSessions(numericCourseId, 5),
    enabled: canUseCourse
  });
  const nextActionQuery = useLearningNextAction(canUseCourse ? numericCourseId : null);
  const reportJob = jobs.find((job) => job.job_id === reportJobId)
    ?? jobs.find((job) => job.workflow === "report_generation" && Number(job.request.course_id) === numericCourseId);
  const reportJobRunning = reportJob?.status === "queued" || reportJob?.status === "running" || reportJob?.status === "cancelling";
  const reportJobError = reportJob?.status === "failed" || reportJob?.status === "cancelled"
    ? reportJob.error_message || "学习报告生成失败，可在任务托盘中重试。"
    : "";

  useEffect(() => {
    if (reportJob?.status !== "completed" || invalidatedReportJobRef.current === reportJob.job_id) return;
    invalidatedReportJobRef.current = reportJob.job_id;
    void invalidateCourseLearningLoop(queryClient, numericCourseId);
  }, [numericCourseId, queryClient, reportJob]);

  const generateMutation = useMutation({
    mutationFn: () => createReportGenerationJob(
      { course_id: numericCourseId },
      createIdempotencyKey(`report-${numericCourseId}`)
    ),
    onSuccess: (job: AiJob) => {
      setLocalError("");
      setExportMessage("");
      setReportJobId(job.job_id);
      trackJob(job);
    },
    onError: () => setLocalError("学习报告任务创建失败，请稍后重试。")
  });

  const exportMutation = useMutation({
    mutationFn: async () => {
      const created = await createLearningDossierExportJob({ course_id: numericCourseId, format: exportFormat });
      const job = await waitForExportJob(created.data);
      if (job.status !== "completed") throw new Error(job.error_message || "learning dossier export failed");
      const file = await downloadExportJob(job.job_id);
      return { job, file };
    },
    onSuccess: ({ job, file }: { job: ExportJob; file: Blob }) => {
      setExportError("");
      downloadDossierFile(job.filename ?? "edunova-learning-dossier", file, job.content_type ?? "application/octet-stream");
      setExportMessage(`已生成 ${exportFormatLabel(job.format)} 学习档案。`);
    },
    onError: (error) => {
      setExportMessage("");
      setExportError(error instanceof ExportPollingTimeoutError
        ? "学习档案仍在后台生成，请稍后再次尝试下载。"
        : "学习档案导出失败，请稍后重试。");
    }
  });

  const report = latestReportQuery.data?.data;
  const masteryMap = masteryQuery.data?.data;
  const recentPractices = recentPracticesQuery.data?.data;
  const latestPractice = recentPractices?.[0] ?? null;
  const freshness = latestReportQuery.isError
    ? "unavailable"
    : report?.status === "ready" && recentPracticesQuery.isError
      ? "unknown"
      : getReportFreshness(report, latestPractice);
  const averageMastery = calculateAverageMastery(masteryMap?.points ?? []);
  const trendScores = buildCurrentTrendScores(report, recentPractices);
  const currentTrend = calculateCurrentTrend(trendScores);
  const weakestPoints = sortMasteryPoints(masteryMap?.points ?? [])
    .filter((point) => point.status === "weak" || point.status === "recommended_review")
    .slice(0, 5);
  const primaryAction = nextActionQuery.data?.data ?? null;
  const readError = latestReportQuery.isError ? "学习报告读取失败，请稍后重试。" : "";
  const dataWarning = [masteryQuery, recentPracticesQuery, nextActionQuery].some((query) => query.isError)
    ? "部分实时学习状态暂未更新，已保留其余可用数据。"
    : "";
  const isLoading = canUseCourse && [latestReportQuery, masteryQuery, recentPracticesQuery].some((query) => query.isPending);

  const preservedContext = useMemo(() => {
    const context = new URLSearchParams();
    ["return_to", "course_session_id", "course_message_id"].forEach((key) => {
      const value = searchParams.get(key);
      if (value) context.set(key, value);
    });
    return context;
  }, [searchParams]);

  function buildContextHref(path: string, extras: Record<string, string>) {
    const params = new URLSearchParams(preservedContext);
    Object.entries(extras).forEach(([key, value]) => params.set(key, value));
    return `${path}?${params.toString()}`;
  }

  function handleCourseChange(courseId: string) {
    const next = new URLSearchParams(searchParams);
    next.set("course_id", courseId);
    setSearchParams(next);
    setLocalError("");
    setExportError("");
    setExportMessage("");
    setDrawerMode(null);
  }

  return (
    <>
      <PageFrame title="学习报告" titleMode="sr-only" variant="wide-workspace">
        <section className="report-workspace" aria-label="学习报告数据工作台">
          <ReportWorkspaceToolbar
            courses={courses}
            courseId={effectiveCourseId}
            freshness={freshness}
            createdAt={report?.created_at}
            isGenerating={generateMutation.isPending || reportJobRunning}
            isRefreshing={latestReportQuery.isFetching && !latestReportQuery.isPending}
            returnLink={<CourseReturnLink courseId={canUseCourse ? numericCourseId : null} />}
            onCourseChange={handleCourseChange}
            onGenerate={() => { if (!reportJobRunning) generateMutation.mutate(); }}
            onRetryRead={() => latestReportQuery.refetch()}
            onOpenDetails={() => setDrawerMode("details")}
            onOpenExport={() => setDrawerMode("export")}
          />

          {!canUseCourse && !coursesQuery.isPending ? (
            <main className="report-no-course"><FileTextFallback /><h2>还没有可生成报告的课程</h2><p>先从资料库创建课程并完成一次练习。</p><a href={PATHS.library}>进入资料库</a></main>
          ) : (
            <ReportDashboard
              report={report}
              masteryMap={masteryMap}
              latestPractice={latestPractice}
              freshness={freshness}
              averageMastery={averageMastery}
              trendScores={trendScores}
              trendDelta={currentTrend.delta}
              trendLabel={currentTrend.label}
              weakestPoints={weakestPoints}
              primaryAction={primaryAction}
              buildPracticeHref={(knowledgePointId) => buildContextHref(PATHS.practice, {
                course_id: effectiveCourseId,
                knowledge_point_id: knowledgePointId,
                new: "1"
              })}
              dataWarning={dataWarning}
              reportError={readError || localError || reportJobError}
              isLoading={isLoading}
              onGenerate={() => { if (!reportJobRunning) generateMutation.mutate(); }}
              onRetryReport={() => latestReportQuery.refetch()}
            />
          )}
        </section>
      </PageFrame>

      <ReportDrawer
        mode={drawerMode}
        detailTab={detailTab}
        report={report}
        reportUnavailable={latestReportQuery.isError}
        exportFormat={exportFormat}
        isExporting={exportMutation.isPending}
        exportMessage={exportMessage}
        exportError={exportError}
        canExport={canUseCourse}
        onClose={() => setDrawerMode(null)}
        onDetailTabChange={setDetailTab}
        onExportFormatChange={(format) => {
          setExportFormat(format);
          setExportError("");
          setExportMessage("");
        }}
        onExport={() => exportMutation.mutate()}
      />
    </>
  );
}

function FileTextFallback() {
  return <span className="report-empty-mark" aria-hidden="true">R</span>;
}
