import { BookOpen, FileArrowUp, Image, MagnifyingGlass, SealCheck, Sparkle, X } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { buildCoursePath } from "../app/routePaths";
import { createCourseFromMaterials } from "../api/courses";
import { listMaterials, type MaterialListItem, uploadMaterial } from "../api/materials";
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
  const materialsQuery = useQuery({
    queryKey: ["materials", "list"],
    queryFn: () => listMaterials(),
    staleTime: 30_000
  });
  const files = useMemo(() => materialsQuery.data?.data ?? [], [materialsQuery.data?.data]);
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
    } catch (error) {
      void error;
    } finally {
      setIsUploadingMaterial(false);
      event.target.value = "";
    }
  }

  function toggleCourseMaterial(materialId: string) {
    setCourseMaterialIds((current) => (current.includes(materialId) ? current.filter((id) => id !== materialId) : [...current, materialId]));
  }

  async function handleCreateCourse() {
    const selectedMaterialIdsAsNumbers = courseMaterialIds
      .map((materialId) => Number.parseInt(materialId, 10))
      .filter((materialId) => Number.isFinite(materialId));

    if (selectedMaterialIdsAsNumbers.length === 0) {
      return;
    }

    if (isCreatingCourse) {
      return;
    }

    setIsCreatingCourse(true);

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
      void error;
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
