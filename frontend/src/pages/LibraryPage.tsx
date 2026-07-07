import { BookOpen, FileArrowUp, Image, MagnifyingGlass, SealCheck, Sparkle, X } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { buildCoursePath } from "../app/routePaths";
import { createCourseFromMaterials, listCourses, type ApiCourseSummary } from "../api/courses";
import { getApiErrorMessage } from "../api/errors";
import {
  compareMaterials,
  listMaterials,
  type MaterialComparisonPoint,
  type MaterialComparisonResult,
  type MaterialListItem,
  uploadMaterial
} from "../api/materials";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { PageFrame } from "./PageFrame";

type LibraryFilter = "all" | "document" | "image";
type LibraryFile = MaterialListItem;

function buildStatusLabel(material: LibraryFile) {
  if (material.parse_status === "completed") {
    return "已解析";
  }

  if (material.category === "image" || material.parse_status === "uploaded") {
    return "已入库";
  }

  if (material.parse_status === "failed") {
    return "解析失败";
  }

  return "解析中";
}

function parseNumericId(value: string | null) {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function pointConfidenceLabel(confidence: string) {
  if (confidence === "high") {
    return "高";
  }
  if (confidence === "low") {
    return "低";
  }
  return "中";
}

function renderComparisonPointList(title: string, points: MaterialComparisonPoint[]) {
  return (
    <section className="material-compare-result-group" aria-label={title}>
      <h3>{title}</h3>
      {points.length === 0 ? <p className="library-file-empty">暂无结果。</p> : null}
      {points.length > 0 ? (
        <ul>
          {points.map((point) => (
            <li key={`${title}-${point.title}-${point.material_ids.join("-")}`}>
              <strong>{point.title}</strong>
              <small>
                {point.reason} · 依据 {point.support_count} 条 · 可信度 {pointConfidenceLabel(point.confidence)}
              </small>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function LibraryPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [activeFilter, setActiveFilter] = useState<LibraryFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeMaterial, setActiveMaterial] = useState<LibraryFile | null>(null);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [courseMaterialIds, setCourseMaterialIds] = useState<string[]>([]);
  const [courseTitle, setCourseTitle] = useState("资料生成课程");
  const [isCreatingCourse, setIsCreatingCourse] = useState(false);
  const [isUploadingMaterial, setIsUploadingMaterial] = useState(false);
  const [libraryFeedback, setLibraryFeedback] = useState<string | null>(null);
  const [courseDialogFeedback, setCourseDialogFeedback] = useState<string | null>(null);
  const [compareCourseId, setCompareCourseId] = useState<string>("");
  const [compareMaterialIds, setCompareMaterialIds] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<MaterialComparisonResult | null>(null);
  const [compareFeedback, setCompareFeedback] = useState<string | null>(null);
  const [isComparingMaterials, setIsComparingMaterials] = useState(false);
  const materialsQuery = useQuery({
    queryKey: ["materials", "list"],
    queryFn: () => listMaterials(),
    staleTime: 30_000
  });
  const coursesQuery = useQuery({
    queryKey: ["courses", "list"],
    queryFn: () => listCourses(),
    staleTime: 30_000
  });
  const files = useMemo(() => asArray<MaterialListItem>(materialsQuery.data?.data), [materialsQuery.data?.data]);
  const courses = useMemo(() => asArray<ApiCourseSummary>(coursesQuery.data?.data), [coursesQuery.data?.data]);
  const effectiveCompareCourseId = compareCourseId || courses[0]?.id || "";
  const compareCourseMaterials = useMemo(
    () =>
      files.filter(
        (file) =>
          effectiveCompareCourseId &&
          file.category === "document" &&
          file.parse_status === "completed" &&
          file.course_ids.includes(effectiveCompareCourseId)
      ),
    [effectiveCompareCourseId, files]
  );
  const selectedComparableCount = compareMaterialIds.filter((materialId) =>
    compareCourseMaterials.some((material) => material.id === materialId)
  ).length;
  const filteredFiles = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    return files.filter((file) => {
      const matchesFilter = activeFilter === "all" || file.category === activeFilter;
      const matchesSearch = !normalizedSearch || file.title.toLowerCase().includes(normalizedSearch) || file.extension.toLowerCase().includes(normalizedSearch);

      return matchesFilter && matchesSearch;
    });
  }, [activeFilter, files, searchTerm]);

  function showMaterialCitation(material: LibraryFile) {
    setActiveMaterial(material);
  }

  async function handleUploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setIsUploadingMaterial(true);

    try {
      await uploadMaterial({ file });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] })
      ]);
      setLibraryFeedback(null);
    } catch (error) {
      void error;
      setLibraryFeedback("资料上传失败，请稍后再试。");
    } finally {
      setIsUploadingMaterial(false);
      event.target.value = "";
    }
  }

  function toggleCourseMaterial(materialId: string) {
    setCourseMaterialIds((current) => (current.includes(materialId) ? current.filter((id) => id !== materialId) : [...current, materialId]));
  }

  function handleCompareCourseChange(event: ChangeEvent<HTMLSelectElement>) {
    setCompareCourseId(event.target.value);
    setCompareMaterialIds([]);
    setCompareResult(null);
    setCompareFeedback(null);
  }

  function toggleCompareMaterial(materialId: string) {
    setCompareMaterialIds((current) => (current.includes(materialId) ? current.filter((id) => id !== materialId) : [...current, materialId]));
    setCompareFeedback(null);
  }

  async function handleCompareMaterials() {
    const courseId = parseNumericId(effectiveCompareCourseId);
    const selectedMaterialIds = compareMaterialIds
      .map((materialId) => Number.parseInt(materialId, 10))
      .filter((materialId) => Number.isFinite(materialId));

    if (courseId === null || selectedMaterialIds.length < 2 || isComparingMaterials) {
      setCompareFeedback("至少选择两份同课程资料。");
      return;
    }

    setIsComparingMaterials(true);
    setCompareFeedback(null);

    try {
      const result = await compareMaterials({ course_id: courseId, material_ids: selectedMaterialIds });
      setCompareResult(result.data);
    } catch (error) {
      setCompareFeedback(getApiErrorMessage(error, "资料对比失败，请稍后重试。"));
    } finally {
      setIsComparingMaterials(false);
    }
  }

  async function handleCreateCourse() {
    const selectedMaterialIdsAsNumbers = courseMaterialIds
      .map((materialId) => Number.parseInt(materialId, 10))
      .filter((materialId) => Number.isFinite(materialId));

    if (selectedMaterialIdsAsNumbers.length === 0) {
      setCourseDialogFeedback("先至少选择一份资料。");
      return;
    }

    if (isCreatingCourse) {
      return;
    }

    setIsCreatingCourse(true);
    setCourseDialogFeedback(null);

    try {
      const created = await createCourseFromMaterials({
        material_ids: selectedMaterialIdsAsNumbers,
        course_title: courseTitle.trim()
      });

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] })
      ]);
      setIsCourseDialogOpen(false);
      navigate(buildCoursePath(created.data.course.id));
    } catch (error) {
      setCourseDialogFeedback(getApiErrorMessage(error, "课程生成失败，请确认选择的是已解析资料。"));
    } finally {
      setIsCreatingCourse(false);
    }
  }

  return (
    <>
      <PageFrame title="资料库">
        <section className="library-file-shell" role="region" aria-label="文件库">
          <div className="library-command-row">
            <input
              ref={uploadInputRef}
              className="visually-hidden"
              type="file"
              aria-label="上传资料文件"
              accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg,.webp"
              onChange={(event) => void handleUploadFile(event)}
            />
            <label className="file-search-field">
              <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
              <input aria-label="搜索资料" placeholder="搜索资料" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} />
            </label>
            <button className="library-action-button" type="button" disabled={isUploadingMaterial} onClick={() => uploadInputRef.current?.click()}>
              <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
              <span>上传资料</span>
            </button>
            <button className="library-action-button primary" type="button" onClick={() => setIsCourseDialogOpen(true)}>
              <Sparkle size={18} weight="duotone" aria-hidden="true" />
              <span>生成课程</span>
            </button>
          </div>
          <InlineFeedback message={libraryFeedback} tone="warning" className="library-inline-feedback" />

          <div className="library-filter-row" aria-label="资料类型">
            {[
              ["all", "全部"],
              ["document", "文档"],
              ["image", "图片"]
            ].map(([filter, label]) => (
              <button
                className={activeFilter === filter ? "active" : ""}
                key={filter}
                type="button"
                aria-pressed={activeFilter === filter}
                onClick={() => {
                  setActiveFilter(filter as LibraryFilter);
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="library-file-table">
            <div className="library-file-header" aria-hidden="true">
              <span>名称</span>
              <span>修改时间</span>
              <span>大小</span>
            </div>
            {materialsQuery.isLoading ? <p className="library-file-empty">正在读取资料库。</p> : null}
            {!materialsQuery.isLoading && materialsQuery.isError ? <p className="library-file-empty">资料库暂时没有读取成功。</p> : null}
            {!materialsQuery.isLoading && !materialsQuery.isError
              ? filteredFiles.map((material) => (
                  <button className="library-file-row" key={material.id} type="button" onClick={() => showMaterialCitation(material)}>
                    <span className="library-file-icon" data-category={material.category} aria-hidden="true">
                      {material.category === "image" ? <Image size={18} weight="duotone" /> : material.parse_status === "completed" ? <SealCheck size={18} weight="duotone" /> : <BookOpen size={18} weight="duotone" />}
                    </span>
                    <span className="library-file-main">
                      <strong>{material.title}</strong>
                      <small>
                        {material.extension} · {material.detail} · {buildStatusLabel(material)}
                      </small>
                    </span>
                    <span>{material.modified}</span>
                    <span>{material.size}</span>
                  </button>
                ))
              : null}
            {!materialsQuery.isLoading && !materialsQuery.isError && filteredFiles.length === 0 ? <p className="library-file-empty">没有匹配的资料。</p> : null}
          </div>

          {activeMaterial ? (
            <section className="material-action-feedback" role="region" aria-label="资料动作反馈">
              <strong>{activeMaterial.title}</strong>
              <p>
                {activeMaterial.category === "image"
                  ? "已入库。第一版不做图片 OCR，可作为资料附件保存。"
                  : `${activeMaterial.parse_status === "completed" ? "已完成解析" : "正在处理"}。完成后可查看片段、页码和置信度。`}
              </p>
            </section>
          ) : null}

          <section className="material-compare-panel" role="region" aria-label="资料对比">
            <div className="student-panel-heading compact">
              <div>
                <h2>资料对比</h2>
              </div>
              <span className="panel-count">{selectedComparableCount} 已选</span>
            </div>

            <div className="material-compare-controls">
              <label>
                <span>对比课程</span>
                <select value={effectiveCompareCourseId} onChange={handleCompareCourseChange} disabled={courses.length === 0}>
                  {courses.length === 0 ? (
                    <option value="">暂无课程</option>
                  ) : (
                    courses.map((course: ApiCourseSummary) => (
                      <option key={course.id} value={course.id}>
                        {course.title}
                      </option>
                    ))
                  )}
                </select>
              </label>
              <button
                className="library-action-button primary"
                type="button"
                disabled={selectedComparableCount < 2 || isComparingMaterials}
                onClick={() => void handleCompareMaterials()}
              >
                {isComparingMaterials ? "对比中" : "生成资料对比"}
              </button>
            </div>

            <div className="material-compare-list">
              {coursesQuery.isLoading ? <p className="library-file-empty">正在读取课程。</p> : null}
              {!coursesQuery.isLoading && coursesQuery.isError ? <p className="library-file-empty">课程列表暂时没有读取成功。</p> : null}
              {!coursesQuery.isLoading && !coursesQuery.isError && compareCourseMaterials.length === 0 ? (
                <p className="library-file-empty">至少选择两份同课程资料。</p>
              ) : null}
              {compareCourseMaterials.map((material) => (
                <button
                  className={compareMaterialIds.includes(material.id) ? "active" : ""}
                  key={material.id}
                  type="button"
                  aria-pressed={compareMaterialIds.includes(material.id)}
                  onClick={() => toggleCompareMaterial(material.id)}
                >
                  <span>{material.extension}</span>
                  <strong>{material.title}</strong>
                  <small>{material.detail}</small>
                </button>
              ))}
            </div>

            {selectedComparableCount < 2 ? <p className="material-compare-note">至少选择两份同课程资料。</p> : null}
            <InlineFeedback message={compareFeedback} tone="warning" className="library-inline-feedback" />

            {compareResult ? (
              <div className="material-compare-result">
                <div className="material-compare-summary">
                  <strong>{compareResult.summary.message}</strong>
                  <span>
                    {compareResult.summary.comparable_material_count} 份可比较 · {compareResult.summary.matched_concept_count} 个命中点 · {compareResult.summary.citation_count} 条引用
                  </span>
                </div>
                <div className="material-compare-grid">
                  {renderComparisonPointList("重复重点", compareResult.repeated_concepts)}
                  {renderComparisonPointList("疑似考点", compareResult.exam_likely_points)}
                  {renderComparisonPointList("单资料独有点", compareResult.materials_only_points)}
                  {renderComparisonPointList("试题独有点", compareResult.questions_only_points)}
                  {renderComparisonPointList("遗漏复习点", compareResult.missing_review_points)}
                  {renderComparisonPointList("优先复习顺序", compareResult.priority_order)}
                </div>
                <section className="material-compare-citations" aria-label="对比引用">
                  <h3>引用摘要</h3>
                  {compareResult.citations.length === 0 ? <p className="library-file-empty">暂无引用。</p> : null}
                  <ul>
                    {compareResult.citations.map((citation) => (
                      <li key={citation.id}>
                        <strong>{citation.source_title}</strong>
                        <small>{citation.section_title ?? "未标注章节"}</small>
                        <span>{citation.excerpt}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>
            ) : null}
          </section>
        </section>
      </PageFrame>

      {isCourseDialogOpen ? (
        <LibraryCourseDialog
          materials={files}
          selectedMaterialIds={courseMaterialIds}
          courseTitle={courseTitle}
          isCreatingCourse={isCreatingCourse}
          onCourseTitleChange={setCourseTitle}
          onToggleMaterial={toggleCourseMaterial}
          feedback={courseDialogFeedback}
          onClose={() => setIsCourseDialogOpen(false)}
          onCreate={() => void handleCreateCourse()}
        />
      ) : null}
    </>
  );
}

type LibraryCourseDialogProps = {
  materials: LibraryFile[];
  selectedMaterialIds: string[];
  courseTitle: string;
  isCreatingCourse: boolean;
  feedback: string | null;
  onCourseTitleChange: (courseTitle: string) => void;
  onToggleMaterial: (materialId: string) => void;
  onClose: () => void;
  onCreate: () => void;
};

function LibraryCourseDialog({
  materials,
  selectedMaterialIds,
  courseTitle,
  isCreatingCourse,
  feedback,
  onCourseTitleChange,
  onToggleMaterial,
  onClose,
  onCreate
}: LibraryCourseDialogProps) {
  const selectedCount = selectedMaterialIds.length;

  return (
    <div className="course-dialog-backdrop">
      <section className="course-dialog library-course-dialog" role="dialog" aria-modal="true" aria-labelledby="library-course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <h2 id="library-course-dialog-title">从资料生成课程</h2>
          <p>选择资料，生成目录、知识点和复习任务。</p>
        </div>
        <label className="dialog-field">
          <span>课程名称</span>
          <input aria-label="课程名称" value={courseTitle} onChange={(event) => onCourseTitleChange(event.target.value)} />
        </label>
        <div className="library-course-materials">
          {materials.length === 0 ? <p className="library-file-empty">还没有可生成课程的资料。</p> : null}
          {materials.map((material) => (
            <button className={selectedMaterialIds.includes(material.id) ? "active" : ""} key={material.id} type="button" aria-pressed={selectedMaterialIds.includes(material.id)} onClick={() => onToggleMaterial(material.id)}>
              <span>{material.extension}</span>
              <strong>{material.title}</strong>
              <small>{material.detail}</small>
            </button>
          ))}
        </div>
        <InlineFeedback message={feedback} tone="warning" className="dialog-inline-feedback" />
        <button
          className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button disabled"}
          type="button"
          disabled={selectedCount === 0 || isCreatingCourse}
          onClick={onCreate}
        >
          {isCreatingCourse ? "生成中" : "生成课程"}
        </button>
      </section>
    </div>
  );
}
