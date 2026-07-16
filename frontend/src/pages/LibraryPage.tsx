import { BookOpen, ChatCircleText, Folders, Sparkle, X } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { buildCoursePath, PATHS } from "../app/routePaths";
import { createCourseBuilderJob, createIdempotencyKey, getAiJob, type AiJob } from "../api/aiJobs";
import { listCourses, type ApiCourseSummary } from "../api/courses";
import { getApiErrorMessage } from "../api/errors";
import {
  compareMaterials,
  confirmMaterialOutline,
  createMaterialIngestionJob,
  getLatestMaterialComparison,
  getMaterial,
  getMaterialOutline,
  listMaterials,
  type MaterialComparisonPoint,
  type MaterialComparisonResult,
  type MaterialDetail,
  type MaterialListItem,
  type MaterialOutline,
  type MaterialOutlineOperation,
  type MaterialOutlineSection,
  updateMaterialOutline,
  uploadMaterial
} from "../api/materials";
import { AgentTraceDisclosure } from "../components/evidence/AgentTraceDisclosure";
import { AiJobProgress } from "../components/feedback/AiJobProgress";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { ModalFrame } from "../components/primitives/Dialog";
import { LibraryDrawer } from "../components/library/LibraryDrawer";
import { LibraryFileTable } from "../components/library/LibraryFileTable";
import { isComparableMaterial } from "../components/library/libraryMaterialState";
import { LibraryWorkspaceToolbar, type LibraryFilter } from "../components/library/LibraryWorkspaceToolbar";
import { NextLearningAction } from "../components/learning/NextLearningAction";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";
import { invalidateLearningNextActions, useLearningNextAction } from "../features/learning-actions/learningActions";
import { PageFrame } from "./PageFrame";
import "../styles/library.css";

type DrawerMode = "detail" | "compare" | null;
type DetailTab = "overview" | "outline" | "chunks" | "courses";
type CompareTab = "common" | "exam" | "differences" | "sources";
type CompareView = "setup" | "result" | "recent";

function parsePositiveId(value: string | null) {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function asMaterialComparison(value: unknown): MaterialComparisonResult | null {
  if (!value || typeof value !== "object" || !("summary" in value) || !("citations" in value)) return null;
  return value as MaterialComparisonResult;
}

function asMaterialOutline(value: unknown): MaterialOutline | null {
  if (!value || typeof value !== "object") return null;
  const outline = value as Partial<MaterialOutline>;
  if (typeof outline.version !== "number" || !Array.isArray(outline.sections) || !Array.isArray(outline.chunks)) return null;
  return {
    ...outline,
    quality: outline.quality ?? {},
    warnings: outline.warnings ?? [],
    sections: outline.sections,
    chunks: outline.chunks
  } as MaterialOutline;
}

function stripExtension(title: string) {
  return title.replace(/\.[^.]+$/, "").trim() || title;
}

function buildSuggestedCourseTitle(materials: MaterialListItem[]) {
  if (materials.length === 0) return "资料生成课程";
  const firstTitle = stripExtension(materials[0].title);
  return materials.length === 1 ? `${firstTitle}课程` : `${firstTitle}等资料课程`;
}

function commonCourseIds(materials: MaterialListItem[]) {
  if (materials.length === 0) return [];
  return materials.slice(1).reduce(
    (common, material) => common.filter((courseId) => material.course_ids.includes(courseId)),
    [...materials[0].course_ids]
  );
}

function pointConfidenceLabel(confidence: string) {
  if (confidence === "high") return "高";
  if (confidence === "low") return "低";
  return "中";
}

function ComparisonPointList({ title, points }: { title: string; points: MaterialComparisonPoint[] }) {
  return (
    <section className="library-comparison-group" aria-label={title}>
      <h3>{title}</h3>
      {points.length === 0 ? <p>暂无结果。</p> : (
        <ul>
          {points.map((point) => (
            <li key={`${title}-${point.title}-${point.material_ids.join("-")}`}>
              <strong>{point.title}</strong>
              <span>{point.reason}</span>
              <small>依据 {point.support_count} 条 · 可信度 {pointConfidenceLabel(point.confidence)}</small>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function LibraryPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const initialMaterialId = parsePositiveId(searchParams.get("material_id"));
  const [activeFilter, setActiveFilter] = useState<LibraryFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(initialMaterialId ? "detail" : null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [compareTab, setCompareTab] = useState<CompareTab>("common");
  const [compareView, setCompareView] = useState<CompareView>("setup");
  const [compareCourseId, setCompareCourseId] = useState("");
  const [compareMaterialIds, setCompareMaterialIds] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<MaterialComparisonResult | null>(null);
  const [compareFeedback, setCompareFeedback] = useState<string | null>(null);
  const [isComparingMaterials, setIsComparingMaterials] = useState(false);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [courseMaterialIds, setCourseMaterialIds] = useState<string[]>([]);
  const [courseTitle, setCourseTitle] = useState("资料生成课程");
  const [courseTitleTouched, setCourseTitleTouched] = useState(false);
  const [courseJobId, setCourseJobId] = useState<string | null>(null);
  const [isUploadingMaterial, setIsUploadingMaterial] = useState(false);
  const [libraryFeedback, setLibraryFeedback] = useState<string | null>(null);
  const [outlineFeedback, setOutlineFeedback] = useState<string | null>(null);
  const [isUpdatingOutline, setIsUpdatingOutline] = useState(false);
  const [courseDialogFeedback, setCourseDialogFeedback] = useState<string | null>(null);
  const { jobs, trackJob, getJob, cancelJob, retryJob } = useAiJobs();
  const courseJob = getJob(courseJobId);
  const isCreatingCourse = Boolean(courseJob && ["queued", "running", "cancelling"].includes(courseJob.status));

  const materialsQuery = useQuery({ queryKey: ["materials", "list"], queryFn: () => listMaterials(), staleTime: 30_000 });
  const coursesQuery = useQuery({ queryKey: ["courses", "list"], queryFn: () => listCourses(), staleTime: 30_000 });
  const nextActionQuery = useLearningNextAction();
  const files = useMemo(() => asArray<MaterialListItem>(materialsQuery.data?.data), [materialsQuery.data?.data]);
  const courses = useMemo(() => asArray<ApiCourseSummary>(coursesQuery.data?.data), [coursesQuery.data?.data]);
  const courseTitles = useMemo(() => new Map(courses.map((course) => [course.id, course.title])), [courses]);
  const selectedMaterialId = parsePositiveId(searchParams.get("material_id"));
  const selectedMaterial = files.find((material) => Number(material.id) === selectedMaterialId) ?? null;
  const activeMaterialJob = jobs.find((job) => (
    job.workflow === "material_ingestion"
    && ["queued", "running", "cancelling"].includes(job.status)
    && Number(job.request.material_id) === selectedMaterialId
  )) ?? null;
  const materialDetailQuery = useQuery({
    queryKey: ["materials", "detail", selectedMaterialId],
    queryFn: () => getMaterial(selectedMaterialId ?? 0),
    enabled: drawerMode === "detail" && selectedMaterialId !== null,
    staleTime: 30_000
  });
  const materialDetail = materialDetailQuery.data?.data ?? null;
  const materialOutlineQuery = useQuery({
    queryKey: ["materials", "outline", selectedMaterialId],
    queryFn: () => getMaterialOutline(selectedMaterialId ?? 0),
    enabled: drawerMode === "detail" && selectedMaterialId !== null && materialDetail?.category === "document" && materialDetail.ingestion_status !== "legacy",
    staleTime: 10_000
  });
  const materialOutline = asMaterialOutline(materialOutlineQuery.data?.data);

  const selectedCompareMaterials = useMemo(
    () => compareMaterialIds.map((id) => files.find((file) => file.id === id)).filter((material): material is MaterialListItem => Boolean(material)),
    [compareMaterialIds, files]
  );
  const sharedCourseIds = useMemo(() => commonCourseIds(selectedCompareMaterials), [selectedCompareMaterials]);
  const sharedCourses = courses.filter((course) => sharedCourseIds.includes(course.id));
  const effectiveCompareCourseId = sharedCourseIds.includes(compareCourseId)
    ? compareCourseId
    : sharedCourseIds.length === 1
      ? sharedCourseIds[0]
      : "";
  const recentComparisonCourseId = compareCourseId || courses[0]?.id || "";

  function handleNextAction(action: NonNullable<typeof nextActionQuery.data>["data"]) {
    if (action.kind === "upload_material") {
      uploadInputRef.current?.click();
      return;
    }
    if (action.kind === "create_course" && action.material_id) {
      openCourseDialog([action.material_id]);
      return;
    }
    const material = files.find((item) => item.id === action.material_id);
    if (material) openMaterial(material);
  }
  const latestComparisonQuery = useQuery({
    queryKey: ["materials", "comparison", "latest", parsePositiveId(recentComparisonCourseId)],
    queryFn: () => getLatestMaterialComparison(parsePositiveId(recentComparisonCourseId) ?? 0),
    enabled: drawerMode === "compare" && compareView === "recent" && parsePositiveId(recentComparisonCourseId) !== null,
    staleTime: 10_000
  });
  const displayedComparison = compareView === "recent"
    ? asMaterialComparison(latestComparisonQuery.data?.data)
    : compareResult;

  const filteredFiles = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return files.filter((file) => {
      const matchesFilter = activeFilter === "all" || file.category === activeFilter;
      const matchesSearch = !normalizedSearch || file.title.toLowerCase().includes(normalizedSearch) || file.extension.toLowerCase().includes(normalizedSearch);
      return matchesFilter && matchesSearch;
    });
  }, [activeFilter, files, searchTerm]);

  useEffect(() => {
    if (courseJobId) return;
    const restored = jobs.find((job) => job.workflow === "course_builder" && ["queued", "running", "cancelling", "failed"].includes(job.status));
    if (!restored) return;
    // Restore durable server state after navigation or refresh.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCourseMaterialIds(Array.isArray(restored.request.material_ids) ? restored.request.material_ids.map(String) : []);
    if (typeof restored.request.course_title === "string") setCourseTitle(restored.request.course_title);
    setCourseTitleTouched(true);
    setCourseJobId(restored.job_id);
    setIsCourseDialogOpen(true);
  }, [courseJobId, jobs]);

  useEffect(() => {
    if (!courseJob) return;
    if (courseJob.status === "failed") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCourseDialogFeedback(courseJob.error_message ?? "课程生成失败，请稍后重试。");
      return;
    }
    const courseId = courseJob.result.course_id;
    if (courseJob.status === "completed" && (typeof courseId === "string" || typeof courseId === "number")) {
      setCourseJobId(null);
      setIsCourseDialogOpen(false);
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["courses", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
        invalidateLearningNextActions(queryClient)
      ]);
      navigate(buildCoursePath(String(courseId)));
    }
  }, [courseJob, navigate, queryClient]);

  const removeMaterialParam = useCallback(() => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("material_id");
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  const closeDrawer = useCallback(() => {
    setDrawerMode(null);
    setCompareMaterialIds([]);
    setCompareResult(null);
    setCompareFeedback(null);
    removeMaterialParam();
  }, [removeMaterialParam]);

  function openMaterial(material: MaterialListItem) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("material_id", material.id);
      return next;
    }, { replace: true });
    setDetailTab("overview");
    setDrawerMode("detail");
  }

  function startCompare(initialIds: string[] = []) {
    removeMaterialParam();
    setCompareMaterialIds(initialIds);
    setCompareCourseId("");
    setCompareResult(null);
    setCompareFeedback(null);
    setCompareTab("common");
    setCompareView("setup");
    setDrawerMode("compare");
  }

  function openRecentComparison() {
    removeMaterialParam();
    setCompareMaterialIds([]);
    setCompareCourseId(courses[0]?.id ?? "");
    setCompareResult(null);
    setCompareFeedback(null);
    setCompareTab("common");
    setCompareView("recent");
    setDrawerMode("compare");
  }

  function openCourseDialog(materialIds: string[] = []) {
    const selected = materialIds.map((id) => files.find((file) => file.id === id)).filter((material): material is MaterialListItem => Boolean(material));
    if (drawerMode === "detail") {
      setDrawerMode(null);
      removeMaterialParam();
    }
    setCourseMaterialIds(materialIds);
    setCourseTitle(buildSuggestedCourseTitle(selected));
    setCourseTitleTouched(false);
    setCourseDialogFeedback(null);
    setIsCourseDialogOpen(true);
  }

  async function handleUploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUploadingMaterial(true);
    try {
      const response = await uploadMaterial({ file });
      const uploaded = response.data;
      if (uploaded.ingestion_job_id) {
        trackJob(await getAiJob(uploaded.ingestion_job_id));
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
        invalidateLearningNextActions(queryClient)
      ]);
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set("material_id", String(uploaded.material_id));
        return next;
      }, { replace: true });
      setDrawerMode("detail");
      setDetailTab("overview");
      setLibraryFeedback(uploaded.ingestion_job_id ? "资料已上传，正在后台识别页码、目录和正文切片。" : null);
    } catch (error) {
      setLibraryFeedback(getApiErrorMessage(error, "资料上传失败，请稍后再试。"));
    } finally {
      setIsUploadingMaterial(false);
      event.target.value = "";
    }
  }

  async function applyOutlineOperations(operations: MaterialOutlineOperation[]) {
    if (!selectedMaterialId || !materialOutline || isUpdatingOutline) return;
    setIsUpdatingOutline(true);
    setOutlineFeedback(null);
    try {
      const result = await updateMaterialOutline(selectedMaterialId, materialOutline.version, operations);
      queryClient.setQueryData(["materials", "outline", selectedMaterialId], result);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "detail", selectedMaterialId] }),
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] })
      ]);
    } catch (error) {
      setOutlineFeedback(getApiErrorMessage(error, "目录调整失败，请刷新后重试。"));
    } finally {
      setIsUpdatingOutline(false);
    }
  }

  async function handleConfirmOutline() {
    if (!selectedMaterialId || !materialOutline || isUpdatingOutline) return;
    setIsUpdatingOutline(true);
    setOutlineFeedback(null);
    try {
      const result = await confirmMaterialOutline(selectedMaterialId, materialOutline.version);
      queryClient.setQueryData(["materials", "outline", selectedMaterialId], result);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "detail", selectedMaterialId] }),
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
        invalidateLearningNextActions(queryClient)
      ]);
      setOutlineFeedback("目录已确认，这份资料现在可以用于问答、对比和智能建课。");
    } catch (error) {
      setOutlineFeedback(getApiErrorMessage(error, "目录确认失败，请检查解析质量后重试。"));
    } finally {
      setIsUpdatingOutline(false);
    }
  }

  async function handleReingestMaterial() {
    if (!selectedMaterialId || isUpdatingOutline) return;
    setIsUpdatingOutline(true);
    setOutlineFeedback(null);
    try {
      const job = await createMaterialIngestionJob(selectedMaterialId, true, createIdempotencyKey("material-ingestion"));
      trackJob(job);
      setOutlineFeedback("已开始重新解析，任务会在离开页面后继续运行。");
      await queryClient.invalidateQueries({ queryKey: ["materials", "list"] });
    } catch (error) {
      setOutlineFeedback(getApiErrorMessage(error, "重新解析任务创建失败，请稍后重试。"));
    } finally {
      setIsUpdatingOutline(false);
    }
  }

  function toggleCompareMaterial(material: MaterialListItem) {
    if (!isComparableMaterial(material)) return;
    setCompareMaterialIds((current) => current.includes(material.id) ? current.filter((id) => id !== material.id) : [...current, material.id]);
    setCompareResult(null);
    setCompareFeedback(null);
  }

  async function handleCompareMaterials() {
    const courseId = parsePositiveId(effectiveCompareCourseId);
    const materialIds = compareMaterialIds.map(Number).filter(Number.isFinite);
    if (courseId === null || materialIds.length < 2 || isComparingMaterials) {
      setCompareFeedback("至少选择两份属于同一课程的已解析资料。");
      return;
    }
    setIsComparingMaterials(true);
    setCompareFeedback(null);
    try {
      const result = await compareMaterials({ course_id: courseId, material_ids: materialIds });
      setCompareResult(result.data);
      setCompareView("result");
      setCompareTab("common");
      queryClient.setQueryData(["materials", "comparison", "latest", courseId], result);
    } catch (error) {
      setCompareFeedback(getApiErrorMessage(error, "资料对比失败，请稍后重试。"));
    } finally {
      setIsComparingMaterials(false);
    }
  }

  function toggleCourseMaterial(materialId: string) {
    const next = courseMaterialIds.includes(materialId)
      ? courseMaterialIds.filter((id) => id !== materialId)
      : [...courseMaterialIds, materialId];
    setCourseMaterialIds(next);
    if (!courseTitleTouched) {
      const selected = next.map((id) => files.find((file) => file.id === id)).filter((material): material is MaterialListItem => Boolean(material));
      setCourseTitle(buildSuggestedCourseTitle(selected));
    }
  }

  async function handleCreateCourse() {
    const materialIds = courseMaterialIds.map(Number).filter(Number.isFinite);
    if (materialIds.length === 0) {
      setCourseDialogFeedback("先至少选择一份已解析资料。");
      return;
    }
    if (isCreatingCourse) return;
    setCourseDialogFeedback(null);
    try {
      const job = await createCourseBuilderJob(
        { material_ids: materialIds, course_title: courseTitle.trim() },
        createIdempotencyKey("library-course")
      );
      setCourseJobId(job.job_id);
      trackJob(job);
    } catch (error) {
      setCourseDialogFeedback(getApiErrorMessage(error, "课程生成失败，请确认选择的是已解析资料。"));
    }
  }

  const detailState = materialDetail ?? selectedMaterial;
  const detailCanUse = Boolean(detailState && detailState.category === "document" && detailState.ingestion_status === "confirmed");
  const parsedCount = files.filter((file) => file.ingestion_status === "confirmed").length;
  const compareFooter = compareView === "setup" ? (
    <>
      <p>{compareMaterialIds.length} 份资料 · {effectiveCompareCourseId ? courseTitles.get(effectiveCompareCourseId) : "等待共同课程"}</p>
      <button className="primary-action" type="button" disabled={compareMaterialIds.length < 2 || !effectiveCompareCourseId || isComparingMaterials} onClick={() => void handleCompareMaterials()}>
        {isComparingMaterials ? "对比中" : "生成资料对比"}
      </button>
    </>
  ) : undefined;

  return (
    <>
      <PageFrame title="资料库" titleMode="sr-only" variant="wide-workspace">
        <section className="library-workspace" aria-label="资料工作台">
          <input
            ref={uploadInputRef}
            className="visually-hidden"
            type="file"
            aria-label="上传资料文件"
            accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg,.webp"
            onChange={(event) => void handleUploadFile(event)}
          />
          <LibraryWorkspaceToolbar
            search={searchTerm}
            filter={activeFilter}
            materialCount={files.length}
            parsedCount={parsedCount}
            isUploading={isUploadingMaterial}
            hasCourses={courses.length > 0}
            onSearchChange={setSearchTerm}
            onFilterChange={setActiveFilter}
            onUpload={() => uploadInputRef.current?.click()}
            onGenerateCourse={() => openCourseDialog()}
            onStartCompare={() => startCompare()}
            onOpenRecentComparison={openRecentComparison}
          />
          <NextLearningAction
            action={nextActionQuery.data?.data}
            isLoading={nextActionQuery.isPending}
            error={nextActionQuery.isError}
            compact
            onAction={handleNextAction}
          />
          <InlineFeedback message={libraryFeedback} tone="warning" className="library-workspace-feedback" />
          {drawerMode === "compare" && compareView === "setup" ? (
            <div className="library-compare-mode-note">
              <strong>正在选择对比资料</strong>
              <span>选择至少两份已解析且属于同一课程的文档。</span>
              <button type="button" onClick={closeDrawer}>退出选择</button>
            </div>
          ) : null}
          <LibraryFileTable
            materials={filteredFiles}
            courseTitles={courseTitles}
            compareMode={drawerMode === "compare" && compareView === "setup"}
            selectedMaterialIds={compareMaterialIds}
            isLoading={materialsQuery.isLoading}
            isError={materialsQuery.isError}
            onOpenMaterial={openMaterial}
            onToggleCompare={toggleCompareMaterial}
          />
        </section>
      </PageFrame>

      {drawerMode === "detail" ? (
        <LibraryDrawer
          title={selectedMaterial?.title ?? "资料详情"}
          onClose={closeDrawer}
          footer={detailState ? (
            <div className="library-detail-actions">
              {!activeMaterialJob && ["legacy", "failed", "awaiting_confirmation"].includes(detailState.ingestion_status ?? "") ? (
                <button className="soft-button" type="button" disabled={isUpdatingOutline} onClick={() => void handleReingestMaterial()}>重新精细解析</button>
              ) : null}
              {materialOutline && !materialOutline.confirmed ? (
                <button className="primary-action" type="button" disabled={Boolean(activeMaterialJob) || isUpdatingOutline || !materialOutline.quality.passed} onClick={() => void handleConfirmOutline()}>
                  {isUpdatingOutline ? "保存中" : "确认目录"}
                </button>
              ) : null}
              <button className="soft-button" type="button" disabled={!detailCanUse} onClick={() => navigate(PATHS.app, { state: { selectedMaterialIds: [detailState.id] } })}>
                <ChatCircleText size={16} aria-hidden="true" />
                <span>带到主页提问</span>
              </button>
              <button className="soft-button" type="button" disabled={!detailCanUse} onClick={() => openCourseDialog([detailState.id])}>
                <Sparkle size={16} aria-hidden="true" />
                <span>生成课程</span>
              </button>
              <button className="soft-button" type="button" disabled={!isComparableMaterial(detailState)} onClick={() => startCompare([detailState.id])}>
                加入对比
              </button>
            </div>
          ) : undefined}
        >
          <MaterialDetailPanel
            material={materialDetail}
            fallbackMaterial={selectedMaterial}
            activeJob={activeMaterialJob}
            outline={materialOutline}
            tab={detailTab}
            isLoading={materialDetailQuery.isLoading}
            isError={materialDetailQuery.isError}
            isOutlineLoading={materialOutlineQuery.isLoading}
            isUpdatingOutline={isUpdatingOutline}
            outlineFeedback={outlineFeedback}
            onTabChange={setDetailTab}
            onApplyOutline={(operations) => void applyOutlineOperations(operations)}
            onOpenCourse={(courseId) => navigate(buildCoursePath(courseId))}
          />
        </LibraryDrawer>
      ) : null}

      {drawerMode === "compare" ? (
        <LibraryDrawer
          title={compareView === "setup" ? "资料对比" : "对比结果"}
          workspaceInteractive={compareView === "setup"}
          onClose={closeDrawer}
          footer={compareFooter}
        >
          <ComparisonPanel
            view={compareView}
            tab={compareTab}
            selectedMaterials={selectedCompareMaterials}
            sharedCourses={compareView === "recent" ? courses : sharedCourses}
            selectedCourseId={compareView === "recent" ? recentComparisonCourseId : effectiveCompareCourseId}
            result={displayedComparison}
            feedback={compareFeedback}
            isLoading={compareView === "recent" && latestComparisonQuery.isLoading}
            isError={compareView === "recent" && latestComparisonQuery.isError}
            onCourseChange={setCompareCourseId}
            onTabChange={setCompareTab}
            onBackToSetup={() => startCompare()}
          />
        </LibraryDrawer>
      ) : null}

      {isCourseDialogOpen ? (
        <LibraryCourseDialog
          materials={files}
          selectedMaterialIds={courseMaterialIds}
          courseTitle={courseTitle}
          isCreatingCourse={isCreatingCourse}
          job={courseJob}
          onCancelJob={() => courseJob && void cancelJob(courseJob.job_id)}
          onRetryJob={() => courseJob && void retryJob(courseJob.job_id).then((job) => setCourseJobId(job.job_id))}
          onCourseTitleChange={(value) => {
            setCourseTitle(value);
            setCourseTitleTouched(true);
          }}
          onToggleMaterial={toggleCourseMaterial}
          feedback={courseDialogFeedback}
          onClose={() => setIsCourseDialogOpen(false)}
          onCreate={() => void handleCreateCourse()}
        />
      ) : null}
    </>
  );
}

function MaterialDetailPanel(props: {
  material: MaterialDetail | null;
  fallbackMaterial: MaterialListItem | null;
  activeJob: AiJob | null;
  outline: MaterialOutline | null;
  tab: DetailTab;
  isLoading: boolean;
  isError: boolean;
  isOutlineLoading: boolean;
  isUpdatingOutline: boolean;
  outlineFeedback: string | null;
  onTabChange: (tab: DetailTab) => void;
  onApplyOutline: (operations: MaterialOutlineOperation[]) => void;
  onOpenCourse: (courseId: string) => void;
}) {
  const tabs: Array<{ id: DetailTab; label: string }> = [
    { id: "overview", label: "概览" },
    { id: "outline", label: "目录" },
    { id: "chunks", label: "切片" },
    { id: "courses", label: "关联课程" }
  ];
  if (props.isLoading) return <p className="library-drawer-state">正在读取资料详情。</p>;
  if (props.isError || !props.material) return <InlineFeedback message="资料详情读取失败，请稍后重试。" tone="warning" />;
  const material = props.material;
  const quality = material.quality_summary ?? {};
  return (
    <>
      <div className="library-drawer-tabs" role="tablist" aria-label="资料详情分类">
        {tabs.map((tab) => <button key={tab.id} role="tab" type="button" aria-selected={props.tab === tab.id} onClick={() => props.onTabChange(tab.id)}>{tab.label}</button>)}
      </div>
      {props.tab === "overview" ? (
        <section className="library-detail-overview" role="tabpanel" aria-label="资料概览">
          {props.activeJob ? (
            <InlineFeedback
              message={`${props.activeJob.label}（${props.activeJob.progress_percent}%）`}
              tone="warning"
            />
          ) : null}
          <div className="library-detail-metrics">
            <div><span>结构状态</span><strong>{props.activeJob?.label ?? (material.outline_confirmed ? "目录已确认" : material.ingestion_status === "awaiting_confirmation" ? "等待确认" : props.fallbackMaterial?.detail ?? material.detail)}</strong></div>
            <div><span>解析质量</span><strong>{props.activeJob ? `重新解析中（上次${quality.passed ? "通过" : "未通过"}）` : quality.passed ? "通过" : material.ingestion_status === "legacy" ? "旧版待重建" : "未通过或处理中"}</strong></div>
            <div><span>章节</span><strong>{quality.section_count ?? material.section_count ?? 0}</strong></div>
            <div><span>切片</span><strong>{quality.chunk_count ?? material.chunk_count ?? 0}</strong></div>
            <div><span>页数</span><strong>{quality.page_count ?? material.page_count ?? "—"}</strong></div>
            <div><span>可读页面</span><strong>{typeof quality.readable_page_ratio === "number" ? `${Math.round(quality.readable_page_ratio * 100)}%` : "—"}</strong></div>
          </div>
          {!props.activeJob ? (quality.warnings ?? []).map((warning) => <InlineFeedback key={warning} message={warning} tone="warning" />) : null}
          {!props.activeJob && (quality.risk_flags ?? []).length > 0 ? <InlineFeedback message={`质量门禁未通过：${quality.risk_flags?.join("、")}`} tone="warning" /> : null}
          <section className="library-preview-block">
            <h3>内容短预览</h3>
            <p>{material.extracted_text_preview || "当前资料没有可展示的文本预览。"}</p>
          </section>
          {material.agent_trace_id ? <AgentTraceDisclosure traceId={material.agent_trace_id} label="查看资料处理轨迹" /> : null}
        </section>
      ) : null}
      {props.tab === "outline" ? (
        <section className="library-outline-editor" role="tabpanel" aria-label="资料目录">
          {props.isOutlineLoading ? <p className="library-drawer-state">正在读取目录结构。</p> : null}
          {!props.isOutlineLoading && !props.outline ? <p className="library-drawer-state">这份资料尚未生成精细目录，可先执行重新解析。</p> : null}
          <InlineFeedback message={props.outlineFeedback} tone={props.outline?.confirmed ? "success" : "warning"} />
          {props.outline ? (
            <>
              <div className="library-outline-summary">
                <span>版本 {props.outline.version}</span>
                <span>{props.outline.sections.filter((section) => section.included).length} 个章节纳入课程</span>
                <span>{props.outline.confirmed ? "已确认" : "修改后需要重新确认"}</span>
              </div>
              {props.outline.sections.map((section, index) => (
                <OutlineSectionEditor
                  key={`${props.outline?.material_id}-${props.outline?.version}-${section.id}`}
                  section={section}
                  previousSection={props.outline?.sections[index - 1] ?? null}
                  disabled={props.isUpdatingOutline}
                  onApply={props.onApplyOutline}
                />
              ))}
            </>
          ) : null}
        </section>
      ) : null}
      {props.tab === "chunks" ? (
        <MaterialChunkInspector
          outline={props.outline}
          isLoading={props.isOutlineLoading}
          disabled={props.isUpdatingOutline}
          onApply={props.onApplyOutline}
        />
      ) : null}
      {props.tab === "courses" ? (
        <section className="library-linked-courses" role="tabpanel" aria-label="关联课程">
          {(material.linked_courses ?? []).length === 0 ? <p className="library-drawer-state">这份资料尚未关联课程。</p> : null}
          {(material.linked_courses ?? []).map((course) => (
            <button key={course.id} type="button" onClick={() => props.onOpenCourse(course.id)}>
              <BookOpen size={18} weight="duotone" aria-hidden="true" />
              <span><strong>{course.title}</strong><small>{course.usage_type === "reference" ? "课程参考资料" : course.usage_type}</small></span>
            </button>
          ))}
        </section>
      ) : null}
    </>
  );
}

function OutlineSectionEditor({ section, previousSection, disabled, onApply }: {
  section: MaterialOutlineSection;
  previousSection: MaterialOutlineSection | null;
  disabled: boolean;
  onApply: (operations: MaterialOutlineOperation[]) => void;
}) {
  const [title, setTitle] = useState(section.title);
  const pageLabel = section.start_page
    ? `第 ${section.start_page}${section.end_page && section.end_page !== section.start_page ? `–${section.end_page}` : ""} 页`
    : "未标注页码";
  return (
    <article className={section.included ? "library-outline-row" : "library-outline-row excluded"}>
      <label className="library-outline-toggle">
        <input
          type="checkbox"
          checked={section.included}
          disabled={disabled}
          onChange={(event) => onApply([{ type: "include", section_id: section.id, included: event.target.checked }])}
        />
        <span>{section.included ? "纳入" : "排除"}</span>
      </label>
      <div className="library-outline-main" style={{ paddingInlineStart: `${Math.min(5, Math.max(0, section.level - 1)) * 14}px` }}>
        <input aria-label={`${section.title}章节名称`} value={title} disabled={disabled} onChange={(event) => setTitle(event.target.value)} />
        <small>{pageLabel} · {section.chunk_indexes.length} 个切片 · 识别可信度 {Math.round(section.confidence * 100)}%</small>
      </div>
      <div className="library-outline-actions">
        <button type="button" disabled={disabled || title.trim() === section.title || !title.trim()} onClick={() => onApply([{ type: "rename", section_id: section.id, title: title.trim() }])}>保存名称</button>
        {previousSection ? (
          <button type="button" disabled={disabled} onClick={() => onApply([{ type: "merge", section_ids: [previousSection.id, section.id], title: previousSection.title }])}>并入上一节</button>
        ) : null}
      </div>
    </article>
  );
}

function MaterialChunkInspector({ outline, isLoading, disabled, onApply }: {
  outline: MaterialOutline | null;
  isLoading: boolean;
  disabled: boolean;
  onApply: (operations: MaterialOutlineOperation[]) => void;
}) {
  const [splitChunkId, setSplitChunkId] = useState<string | null>(null);
  const [splitTitle, setSplitTitle] = useState("");
  if (isLoading) return <p className="library-drawer-state">正在读取正文切片。</p>;
  if (!outline) return <p className="library-drawer-state">完成精细解析后可检查真实切片。</p>;
  return (
    <section className="library-chunk-inspector" role="tabpanel" aria-label="资料切片">
      {outline.chunks.length === 0 ? <p className="library-drawer-state">当前目录没有正文切片。</p> : null}
      {outline.chunks.map((chunk) => {
        const section = outline.sections.find((item) => item.id === chunk.section_id);
        const firstChunk = section?.chunk_indexes[0] === chunk.chunk_index;
        const pageLabel = chunk.start_page
          ? `第 ${chunk.start_page}${chunk.end_page && chunk.end_page !== chunk.start_page ? `–${chunk.end_page}` : ""} 页`
          : "未标注页码";
        return (
          <article key={chunk.id}>
            <header><strong>{chunk.section_path.join(" / ") || section?.title || "正文"}</strong><span>{pageLabel} · 切片 {chunk.chunk_index + 1}</span></header>
            <p>{chunk.content}</p>
            {!firstChunk ? (
              splitChunkId === chunk.id ? (
                <div className="library-chunk-split">
                  <input aria-label="新章节名称" placeholder="输入拆分后的新章节名称" value={splitTitle} onChange={(event) => setSplitTitle(event.target.value)} />
                  <button type="button" disabled={disabled || !splitTitle.trim()} onClick={() => {
                    if (!section) return;
                    onApply([{ type: "split", section_id: section.id, chunk_index: chunk.chunk_index, title: splitTitle.trim() }]);
                    setSplitChunkId(null);
                    setSplitTitle("");
                  }}>确认拆分</button>
                  <button type="button" onClick={() => setSplitChunkId(null)}>取消</button>
                </div>
              ) : <button className="library-chunk-split-trigger" type="button" disabled={disabled} onClick={() => setSplitChunkId(chunk.id)}>从此处拆分章节</button>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}

function ComparisonPanel(props: {
  view: CompareView;
  tab: CompareTab;
  selectedMaterials: MaterialListItem[];
  sharedCourses: ApiCourseSummary[];
  selectedCourseId: string;
  result: MaterialComparisonResult | null;
  feedback: string | null;
  isLoading: boolean;
  isError: boolean;
  onCourseChange: (courseId: string) => void;
  onTabChange: (tab: CompareTab) => void;
  onBackToSetup: () => void;
}) {
  if (props.view === "setup") {
    return (
      <section className="library-compare-setup">
        <div className="library-selected-materials">
          <h3>已选资料</h3>
          {props.selectedMaterials.length === 0 ? <p>在左侧文件列表中选择资料。</p> : props.selectedMaterials.map((material) => (
            <div key={material.id}><span>{material.extension}</span><strong>{material.title}</strong></div>
          ))}
        </div>
        <label className="library-drawer-field">
          <span>共同课程</span>
          <select aria-label="对比课程" value={props.selectedCourseId} disabled={props.sharedCourses.length === 0} onChange={(event) => props.onCourseChange(event.target.value)}>
            {props.sharedCourses.length === 0 ? <option value="">等待共同课程</option> : null}
            {props.sharedCourses.length > 1 ? <option value="">请选择课程</option> : null}
            {props.sharedCourses.map((course) => <option key={course.id} value={course.id}>{course.title}</option>)}
          </select>
        </label>
        {props.selectedMaterials.length >= 2 && props.sharedCourses.length === 0 ? <InlineFeedback message="所选资料不属于同一课程，请调整选择。" tone="warning" /> : null}
        <InlineFeedback message={props.feedback} tone="warning" />
      </section>
    );
  }

  if (props.view === "recent") {
    return (
      <>
        <label className="library-drawer-field recent-course-select">
          <span>查看课程</span>
          <select aria-label="最近对比课程" value={props.selectedCourseId} onChange={(event) => props.onCourseChange(event.target.value)}>
            {props.sharedCourses.map((course) => <option key={course.id} value={course.id}>{course.title}</option>)}
          </select>
        </label>
        {props.isLoading ? <p className="library-drawer-state">正在读取最近对比。</p> : null}
        {props.isError ? <InlineFeedback message="最近对比读取失败，请稍后重试。" tone="warning" /> : null}
        {!props.isLoading && !props.isError && !props.result ? (
          <div className="library-recent-empty"><Folders size={28} weight="duotone" /><strong>这门课程还没有资料对比</strong><button type="button" onClick={props.onBackToSetup}>选择资料开始对比</button></div>
        ) : null}
        {props.result ? <ComparisonResult result={props.result} tab={props.tab} onTabChange={props.onTabChange} onBackToSetup={props.onBackToSetup} /> : null}
      </>
    );
  }

  return props.result ? <ComparisonResult result={props.result} tab={props.tab} onTabChange={props.onTabChange} onBackToSetup={props.onBackToSetup} /> : null;
}

function ComparisonResult({ result, tab, onTabChange, onBackToSetup }: {
  result: MaterialComparisonResult;
  tab: CompareTab;
  onTabChange: (tab: CompareTab) => void;
  onBackToSetup: () => void;
}) {
  const tabs: Array<{ id: CompareTab; label: string }> = [
    { id: "common", label: "共同重点" },
    { id: "exam", label: "考点" },
    { id: "differences", label: "差异遗漏" },
    { id: "sources", label: "来源与轨迹" }
  ];
  return (
    <section className="library-comparison-result">
      <header>
        <strong>{result.summary.message}</strong>
        <span>{result.summary.comparable_material_count} 份可比较 · {result.summary.matched_concept_count} 个命中点 · {result.summary.citation_count} 条引用</span>
        <small>{result.generation_mode === "model_enhanced" ? "模型增强" : "规则底稿"} · {result.review_mode === "model_and_rules" ? "模型与规则审核" : "规则审核"}</small>
      </header>
      {(result.warnings ?? []).map((warning) => <InlineFeedback key={warning} message={warning} tone="warning" />)}
      <div className="library-drawer-tabs" role="tablist" aria-label="资料对比结果分类">
        {tabs.map((item) => <button key={item.id} role="tab" type="button" aria-selected={tab === item.id} onClick={() => onTabChange(item.id)}>{item.label}</button>)}
      </div>
      {tab === "common" ? <><ComparisonPointList title="重复重点" points={result.repeated_concepts} /><ComparisonPointList title="优先复习顺序" points={result.priority_order} /></> : null}
      {tab === "exam" ? <ComparisonPointList title="疑似考点" points={result.exam_likely_points} /> : null}
      {tab === "differences" ? <><ComparisonPointList title="单资料独有点" points={result.materials_only_points} /><ComparisonPointList title="试题独有点" points={result.questions_only_points} /><ComparisonPointList title="遗漏复习点" points={result.missing_review_points} /></> : null}
      {tab === "sources" ? (
        <section className="library-comparison-sources" role="tabpanel" aria-label="对比来源与轨迹">
          {result.citations.length === 0 ? <p className="library-drawer-state">暂无引用。</p> : result.citations.map((citation) => (
            <article key={citation.id}><strong>{citation.source_title}</strong><small>{citation.section_title ?? "未标注章节"}{citation.page_number ? ` · 第 ${citation.page_number} 页` : ""}</small><p>{citation.excerpt}</p></article>
          ))}
          <AgentTraceDisclosure traceId={result.agent_trace_id} label="查看 MaterialComparisonGraph" />
        </section>
      ) : null}
      <button className="library-compare-again" type="button" onClick={onBackToSetup}>选择其他资料重新对比</button>
    </section>
  );
}

type LibraryCourseDialogProps = {
  materials: MaterialListItem[];
  selectedMaterialIds: string[];
  courseTitle: string;
  isCreatingCourse: boolean;
  job?: AiJob;
  feedback: string | null;
  onCourseTitleChange: (courseTitle: string) => void;
  onToggleMaterial: (materialId: string) => void;
  onClose: () => void;
  onCreate: () => void;
  onCancelJob: () => void;
  onRetryJob: () => void;
};

function LibraryCourseDialog(props: LibraryCourseDialogProps) {
  const selectedCount = props.selectedMaterialIds.length;
  return (
    <ModalFrame title="从资料生成课程" layerClassName="course-dialog-backdrop" onClose={props.onClose} dismissible={!props.isCreatingCourse}>
      <section className="course-dialog library-course-dialog" aria-labelledby="library-course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={props.onClose}><X size={18} aria-hidden="true" /></button>
        <div className="dialog-copy"><h2 id="library-course-dialog-title">从资料生成课程</h2><p>选择已解析资料，生成目录、知识点和复习任务。</p></div>
        <label className="dialog-field"><span>课程名称</span><input aria-label="课程名称" value={props.courseTitle} onChange={(event) => props.onCourseTitleChange(event.target.value)} /></label>
        <div className="library-course-materials">
          {props.materials.length === 0 ? <p className="library-table-state">还没有可生成课程的资料。</p> : null}
          {props.materials.map((material) => {
            const available = material.category === "document" && material.ingestion_status === "confirmed";
            return (
              <button className={props.selectedMaterialIds.includes(material.id) ? "active" : ""} key={material.id} type="button" disabled={!available} aria-pressed={props.selectedMaterialIds.includes(material.id)} onClick={() => props.onToggleMaterial(material.id)}>
                <span>{material.extension}</span><strong>{material.title}</strong><small>{available ? material.detail : "需要先完成精细解析并确认目录"}</small>
              </button>
            );
          })}
        </div>
        <InlineFeedback message={props.feedback} tone="warning" className="dialog-inline-feedback" />
        {props.job ? <AiJobProgress job={props.job} onCancel={props.onCancelJob} onRetry={props.onRetryJob} /> : null}
        <button className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button disabled"} type="button" disabled={selectedCount === 0 || props.isCreatingCourse} onClick={props.onCreate}>
          {props.isCreatingCourse ? "生成中" : "生成课程"}
        </button>
      </section>
    </ModalFrame>
  );
}
