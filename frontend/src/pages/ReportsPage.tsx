import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getMasteryMap, listCourses } from "../api/courses";
import {
  createLearningDossierExportJob,
  downloadExportJob,
  getExportJob,
  type ExportFormat,
  type ExportJob
} from "../api/exports";
import { getCurrentPath } from "../api/paths";
import { getLatestPracticeSession } from "../api/practice";
import { generateReport, getLatestReport } from "../api/reports";
import { PATHS, buildCoursePath } from "../app/routePaths";
import { CourseReturnLink } from "../components/course-space/CourseReturnLink";
import { buildCourseReturnHref } from "../components/course-space/courseReturn";
import { ReportDashboard } from "../components/reports/ReportDashboard";
import { ReportDrawer, type ReportDetailTab, type ReportDrawerMode } from "../components/reports/ReportDrawer";
import { ReportWorkspaceToolbar } from "../components/reports/ReportWorkspaceToolbar";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";
import {
  buildCurrentTrendScores,
  buildReportPrimaryAction,
  calculateAverageMastery,
  calculateCurrentTrend,
  getReportFreshness,
  sortMasteryPoints
} from "../features/reports/reportViewModel";
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
  window.URL.revokeObjectURL(url);
}

function exportFormatLabel(format: ExportFormat) {
  if (format === "pdf") return "PDF";
  if (format === "docx") return "DOCX";
  return "Markdown";
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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

  useEffect(() => {
    if (!drawerMode) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setDrawerMode(null);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [drawerMode]);

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
  const latestPracticeQuery = useQuery({
    queryKey: courseLoopQueryKeys.latestPractice(numericCourseId),
    queryFn: () => getLatestPracticeSession(numericCourseId),
    enabled: canUseCourse
  });
  const currentPathQuery = useQuery({
    queryKey: courseLoopQueryKeys.currentPath(numericCourseId),
    queryFn: () => getCurrentPath(numericCourseId),
    enabled: canUseCourse
  });

  const generateMutation = useMutation({
    mutationFn: () => generateReport({ course_id: numericCourseId }),
    onSuccess: async () => {
      setLocalError("");
      setExportMessage("");
      await invalidateCourseLearningLoop(queryClient, numericCourseId);
    },
    onError: () => setLocalError("学习报告生成失败，请稍后重试。")
  });

  const exportMutation = useMutation({
    mutationFn: async () => {
      const created = await createLearningDossierExportJob({ course_id: numericCourseId, format: exportFormat });
      let job = created.data;
      for (let attempt = 0; attempt < 20 && job.status !== "completed" && job.status !== "failed"; attempt += 1) {
        const refreshed = await getExportJob(job.job_id);
        job = refreshed.data;
        if (job.status !== "completed" && job.status !== "failed") await delay(800);
      }
      if (job.status !== "completed") throw new Error(job.error_message || "learning dossier export failed");
      const file = await downloadExportJob(job.job_id);
      return { job, file };
    },
    onSuccess: ({ job, file }: { job: ExportJob; file: Blob }) => {
      setExportError("");
      downloadDossierFile(job.filename ?? "edunova-learning-dossier", file, job.content_type ?? "application/octet-stream");
      setExportMessage(`已生成 ${exportFormatLabel(job.format)} 学习档案。`);
    },
    onError: () => {
      setExportMessage("");
      setExportError("学习档案导出失败，请稍后重试。");
    }
  });

  const report = latestReportQuery.data?.data;
  const masteryMap = masteryQuery.data?.data;
  const latestPractice = latestPracticeQuery.data?.data;
  const currentPath = currentPathQuery.data?.data;
  const freshness = getReportFreshness(report, latestPractice);
  const averageMastery = calculateAverageMastery(masteryMap?.points ?? []);
  const trendScores = buildCurrentTrendScores(report, latestPractice);
  const currentTrend = calculateCurrentTrend(trendScores);
  const weakestPoints = sortMasteryPoints(masteryMap?.points ?? [])
    .filter((point) => point.status === "weak" || point.status === "recommended_review")
    .slice(0, 5);
  const primaryAction = buildReportPrimaryAction({ freshness, masteryMap, currentPath });
  const readError = latestReportQuery.isError && report?.status !== "empty" ? "学习报告读取失败，请稍后重试。" : "";
  const dataWarning = [masteryQuery, latestPracticeQuery, currentPathQuery].some((query) => query.isError)
    ? "部分实时学习状态暂未更新，已保留其余可用数据。"
    : "";
  const isLoading = canUseCourse && [latestReportQuery, masteryQuery, latestPracticeQuery].some((query) => query.isPending);

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

  const primaryActionHref = primaryAction.type === "practice"
    ? buildContextHref(PATHS.practice, { course_id: effectiveCourseId, knowledge_point_id: primaryAction.knowledgePoint.id, new: "1" })
    : primaryAction.type === "path"
      ? buildContextHref(PATHS.path, { course_id: effectiveCourseId })
      : primaryAction.type === "course"
        ? buildCourseReturnHref(searchParams, numericCourseId) || buildCoursePath(effectiveCourseId)
        : null;

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
      <PageFrame title="学习报告" variant="wide-workspace">
        <section className="report-workspace" aria-label="学习报告数据工作台">
          <ReportWorkspaceToolbar
            courses={courses}
            courseId={effectiveCourseId}
            freshness={freshness}
            createdAt={report?.created_at}
            isGenerating={generateMutation.isPending}
            returnLink={<CourseReturnLink courseId={canUseCourse ? numericCourseId : null} />}
            onCourseChange={handleCourseChange}
            onGenerate={() => generateMutation.mutate()}
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
              primaryActionHref={primaryActionHref}
              buildPracticeHref={(knowledgePointId) => buildContextHref(PATHS.practice, {
                course_id: effectiveCourseId,
                knowledge_point_id: knowledgePointId,
                new: "1"
              })}
              dataWarning={dataWarning}
              reportError={readError || localError}
              isLoading={isLoading}
              onGenerate={() => generateMutation.mutate()}
            />
          )}
        </section>
      </PageFrame>

      <ReportDrawer
        mode={drawerMode}
        detailTab={detailTab}
        report={report}
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
