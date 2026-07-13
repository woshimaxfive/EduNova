import { BookOpen, ChatCircleText, Folders, Sparkle, X } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { buildCoursePath, PATHS } from "../app/routePaths";
import { createCourseBuilderJob, createIdempotencyKey, type AiJob } from "../api/aiJobs";
import { listCourses, type ApiCourseSummary } from "../api/courses";
import { getApiErrorMessage } from "../api/errors";
import {
  compareMaterials,
  getLatestMaterialComparison,
  getMaterial,
  listMaterials,
  type MaterialComparisonPoint,
  type MaterialComparisonResult,
  type MaterialDetail,
  type MaterialListItem,
  uploadMaterial
} from "../api/materials";
import { AgentTraceDisclosure } from "../components/evidence/AgentTraceDisclosure";
import { AiJobProgress } from "../components/feedback/AiJobProgress";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { LibraryDrawer } from "../components/library/LibraryDrawer";
import { LibraryFileTable } from "../components/library/LibraryFileTable";
import { isComparableMaterial } from "../components/library/libraryMaterialState";
import { LibraryWorkspaceToolbar, type LibraryFilter } from "../components/library/LibraryWorkspaceToolbar";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";
import { PageFrame } from "./PageFrame";
import "../styles/library.css";

type DrawerMode = "detail" | "compare" | null;
type DetailTab = "overview" | "sections" | "courses";
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
  const [courseDialogFeedback, setCourseDialogFeedback] = useState<string | null>(null);
  const { jobs, trackJob, getJob, cancelJob, retryJob } = useAiJobs();
  const courseJob = getJob(courseJobId);
  const isCreatingCourse = Boolean(courseJob && ["queued", "running", "cancelling"].includes(courseJob.status));

  const materialsQuery = useQuery({ queryKey: ["materials", "list"], queryFn: () => listMaterials(), staleTime: 30_000 });
  const coursesQuery = useQuery({ queryKey: ["courses", "list"], queryFn: () => listCourses(), staleTime: 30_000 });
  const files = useMemo(() => asArray<MaterialListItem>(materialsQuery.data?.data), [materialsQuery.data?.data]);
  const courses = useMemo(() => asArray<ApiCourseSummary>(coursesQuery.data?.data), [coursesQuery.data?.data]);
  const courseTitles = useMemo(() => new Map(courses.map((course) => [course.id, course.title])), [courses]);
  const selectedMaterialId = parsePositiveId(searchParams.get("material_id"));
  const selectedMaterial = files.find((material) => Number(material.id) === selectedMaterialId) ?? null;
  const materialDetailQuery = useQuery({
    queryKey: ["materials", "detail", selectedMaterialId],
    queryFn: () => getMaterial(selectedMaterialId ?? 0),
    enabled: drawerMode === "detail" && selectedMaterialId !== null,
    staleTime: 30_000
  });
  const materialDetail = materialDetailQuery.data?.data ?? null;

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
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] })
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
      await uploadMaterial({ file });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] })
      ]);
      setLibraryFeedback(null);
    } catch {
      setLibraryFeedback("资料上传失败，请稍后再试。");
    } finally {
      setIsUploadingMaterial(false);
      event.target.value = "";
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

  const detailCanUse = Boolean(selectedMaterial && selectedMaterial.category === "document" && selectedMaterial.parse_status === "completed");
  const parsedCount = files.filter((file) => file.parse_status === "completed").length;
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
          eyebrow="资料库"
          onClose={closeDrawer}
          footer={selectedMaterial ? (
            <div className="library-detail-actions">
              <button className="soft-button" type="button" disabled={!detailCanUse} onClick={() => navigate(PATHS.app, { state: { selectedMaterialIds: [selectedMaterial.id] } })}>
                <ChatCircleText size={16} aria-hidden="true" />
                <span>带到主页提问</span>
              </button>
              <button className="soft-button" type="button" disabled={!detailCanUse} onClick={() => openCourseDialog([selectedMaterial.id])}>
                <Sparkle size={16} aria-hidden="true" />
                <span>生成课程</span>
              </button>
              <button className="primary-action" type="button" disabled={!isComparableMaterial(selectedMaterial)} onClick={() => startCompare([selectedMaterial.id])}>
                加入对比
              </button>
            </div>
          ) : undefined}
        >
          <MaterialDetailPanel
            material={materialDetail}
            fallbackMaterial={selectedMaterial}
            tab={detailTab}
            isLoading={materialDetailQuery.isLoading}
            isError={materialDetailQuery.isError}
            onTabChange={setDetailTab}
            onOpenCourse={(courseId) => navigate(buildCoursePath(courseId))}
          />
        </LibraryDrawer>
      ) : null}

      {drawerMode === "compare" ? (
        <LibraryDrawer
          title={compareView === "setup" ? "资料对比" : "对比结果"}
          eyebrow="MaterialComparisonGraph"
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
  tab: DetailTab;
  isLoading: boolean;
  isError: boolean;
  onTabChange: (tab: DetailTab) => void;
  onOpenCourse: (courseId: string) => void;
}) {
  const tabs: Array<{ id: DetailTab; label: string }> = [
    { id: "overview", label: "概览" },
    { id: "sections", label: "章节" },
    { id: "courses", label: "关联课程" }
  ];
  if (props.isLoading) return <p className="library-drawer-state">正在读取资料详情。</p>;
  if (props.isError || !props.material) return <InlineFeedback message="资料详情读取失败，请稍后重试。" tone="warning" />;
  const material = props.material;
  return (
    <>
      <div className="library-drawer-tabs" role="tablist" aria-label="资料详情分类">
        {tabs.map((tab) => <button key={tab.id} role="tab" type="button" aria-selected={props.tab === tab.id} onClick={() => props.onTabChange(tab.id)}>{tab.label}</button>)}
      </div>
      {props.tab === "overview" ? (
        <section className="library-detail-overview" role="tabpanel" aria-label="资料概览">
          <div className="library-detail-metrics">
            <div><span>状态</span><strong>{props.fallbackMaterial?.detail ?? material.detail}</strong></div>
            <div><span>格式</span><strong>{material.extension}</strong></div>
            <div><span>分块</span><strong>{material.chunk_count ?? 0}</strong></div>
            <div><span>页数</span><strong>{material.page_count ?? "—"}</strong></div>
          </div>
          <section className="library-preview-block">
            <h3>内容短预览</h3>
            <p>{material.extracted_text_preview || "当前资料没有可展示的文本预览。"}</p>
          </section>
          {material.agent_trace_id ? <AgentTraceDisclosure traceId={material.agent_trace_id} label="查看资料处理轨迹" /> : null}
        </section>
      ) : null}
      {props.tab === "sections" ? (
        <section className="library-section-list" role="tabpanel" aria-label="资料章节">
          {(material.sections ?? []).length === 0 ? <p className="library-drawer-state">当前资料没有章节摘要。</p> : null}
          {(material.sections ?? []).map((section, index) => (
            <article key={`${section.section_title}-${section.page_number ?? "none"}-${index}`}>
              <div><strong>{section.section_title}</strong><span>{section.page_number ? `第 ${section.page_number} 页` : "未标注页码"}</span></div>
              <p>{section.preview || "该章节暂无短预览。"}</p>
              <small>{section.chunk_count} 个资料分块</small>
            </article>
          ))}
          {(material.section_count ?? 0) > (material.sections ?? []).length ? <p className="library-section-more">仅展示前 20 个章节，共 {material.section_count} 个。</p> : null}
        </section>
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
    <div className="course-dialog-backdrop">
      <section className="course-dialog library-course-dialog" role="dialog" aria-modal="true" aria-labelledby="library-course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={props.onClose}><X size={18} aria-hidden="true" /></button>
        <div className="dialog-copy"><h2 id="library-course-dialog-title">从资料生成课程</h2><p>选择已解析资料，生成目录、知识点和复习任务。</p></div>
        <label className="dialog-field"><span>课程名称</span><input aria-label="课程名称" value={props.courseTitle} onChange={(event) => props.onCourseTitleChange(event.target.value)} /></label>
        <div className="library-course-materials">
          {props.materials.length === 0 ? <p className="library-table-state">还没有可生成课程的资料。</p> : null}
          {props.materials.map((material) => {
            const available = material.category === "document" && material.parse_status === "completed";
            return (
              <button className={props.selectedMaterialIds.includes(material.id) ? "active" : ""} key={material.id} type="button" disabled={!available} aria-pressed={props.selectedMaterialIds.includes(material.id)} onClick={() => props.onToggleMaterial(material.id)}>
                <span>{material.extension}</span><strong>{material.title}</strong><small>{available ? material.detail : "需要已解析文档"}</small>
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
    </div>
  );
}
