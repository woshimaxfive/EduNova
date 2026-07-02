import { BookOpen, FileArrowUp, Image, MagnifyingGlass, SealCheck, Sparkle, X } from "@phosphor-icons/react";
import { type ChangeEvent, useMemo, useRef, useState } from "react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

type LibraryFilter = "all" | "document" | "image";

type LibraryFile = {
  id: string;
  title: string;
  category: Exclude<LibraryFilter, "all">;
  extension: string;
  detail: string;
  modified: string;
  size: string;
  parseStatus: "completed" | "processing";
};

const initialLibraryFiles: LibraryFile[] = [
  {
    id: "material-ai-notes",
    title: "AI 导论讲义",
    category: "document",
    extension: "DOCX",
    detail: "12 个知识点",
    modified: "今天",
    size: "1.2 MB",
    parseStatus: "completed"
  },
  {
    id: "material-final-review",
    title: "期末复习题样例",
    category: "document",
    extension: "MD",
    detail: "24 道练习",
    modified: "昨天",
    size: "68 KB",
    parseStatus: "completed"
  },
  {
    id: "material-nn-board",
    title: "神经网络课堂板书",
    category: "image",
    extension: "PNG",
    detail: "图片资料 · 等待提取说明",
    modified: "周一",
    size: "540 KB",
    parseStatus: "processing"
  }
];

function formatFileSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }

  if (size >= 1024) {
    return `${Math.ceil(size / 1024)} KB`;
  }

  return `${size} B`;
}

function inferLibraryFile(file: File): LibraryFile {
  const extension = file.name.split(".").pop()?.toUpperCase() ?? "FILE";
  const isImage = file.type.startsWith("image/") || ["PNG", "JPG", "JPEG", "WEBP"].includes(extension);

  return {
    id: `upload-${Date.now()}`,
    title: file.name,
    category: isImage ? "image" : "document",
    extension,
    detail: isImage ? "图片资料" : "等待解析",
    modified: "刚刚",
    size: formatFileSize(file.size),
    parseStatus: "processing"
  };
}

export function LibraryPage() {
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState(initialLibraryFiles);
  const [activeFilter, setActiveFilter] = useState<LibraryFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeMaterial, setActiveMaterial] = useState<LibraryFile | null>(null);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [courseMaterialIds, setCourseMaterialIds] = useState<string[]>(() => initialLibraryFiles.map((file) => file.id));
  const { notice, showNotice } = useActionNotice();
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
    showNotice(`已打开「${material.title}」的引用预览。`, "success");
  }

  function handleUploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    const uploadedFile = inferLibraryFile(file);
    setFiles((current) => [uploadedFile, ...current]);
    setCourseMaterialIds((current) => [uploadedFile.id, ...current]);
    showNotice(`${file.name} 已上传到资料库。`, "success");
    event.target.value = "";
  }

  function toggleCourseMaterial(materialId: string) {
    setCourseMaterialIds((current) => (current.includes(materialId) ? current.filter((id) => id !== materialId) : [...current, materialId]));
  }

  return (
    <>
      <PageFrame title="资料库" description="上传资料，搜索引用，也可以生成课程。">
        <section className="library-file-shell" role="region" aria-label="文件库">
          <div className="library-command-row">
            <input
              ref={uploadInputRef}
              className="visually-hidden"
              type="file"
              aria-label="上传资料文件"
              accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg,.webp"
              onChange={handleUploadFile}
            />
            <label className="file-search-field">
              <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
              <input aria-label="搜索资料" placeholder="搜索资料" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} />
            </label>
            <button className="library-action-button" type="button" onClick={() => uploadInputRef.current?.click()}>
              <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
              <span>上传资料</span>
            </button>
            <button className="library-action-button primary" type="button" onClick={() => setIsCourseDialogOpen(true)}>
              <Sparkle size={18} weight="duotone" aria-hidden="true" />
              <span>从资料生成课程</span>
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
                  showNotice(`已切换到${label}资料。`);
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
            {filteredFiles.map((material) => (
              <button className="library-file-row" key={material.id} type="button" onClick={() => showMaterialCitation(material)}>
                <span className="library-file-icon" data-category={material.category} aria-hidden="true">
                  {material.category === "image" ? <Image size={18} weight="duotone" /> : material.parseStatus === "completed" ? <SealCheck size={18} weight="duotone" /> : <BookOpen size={18} weight="duotone" />}
                </span>
                <span className="library-file-main">
                  <strong>{material.title}</strong>
                  <small>
                    {material.extension} · {material.detail} · {material.parseStatus === "completed" ? "已解析" : "解析中"}
                  </small>
                </span>
                <span>{material.modified}</span>
                <span>{material.size}</span>
              </button>
            ))}
            {filteredFiles.length === 0 ? <p className="library-file-empty">没有匹配的资料。</p> : null}
          </div>

          {activeMaterial ? (
            <section className="material-action-feedback" role="region" aria-label="资料动作反馈">
              <strong>{activeMaterial.title}</strong>
              <p>
                {activeMaterial.parseStatus === "completed" ? "已完成解析" : "正在处理"}。完成后可查看片段、页码和置信度。
              </p>
            </section>
          ) : null}

          <ActionNotice notice={notice} />
        </section>
      </PageFrame>

      {isCourseDialogOpen ? (
        <LibraryCourseDialog
          materials={files}
          selectedMaterialIds={courseMaterialIds}
          onToggleMaterial={toggleCourseMaterial}
          onClose={() => setIsCourseDialogOpen(false)}
          onCreate={() => {
            showNotice(courseMaterialIds.length > 0 ? `已用 ${courseMaterialIds.length} 份资料创建课程草案演示态。` : "先至少选择一份资料。", courseMaterialIds.length > 0 ? "success" : "warning");
            if (courseMaterialIds.length > 0) {
              setIsCourseDialogOpen(false);
            }
          }}
        />
      ) : null}
    </>
  );
}

type LibraryCourseDialogProps = {
  materials: LibraryFile[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  onClose: () => void;
  onCreate: () => void;
};

function LibraryCourseDialog({ materials, selectedMaterialIds, onToggleMaterial, onClose, onCreate }: LibraryCourseDialogProps) {
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
        <div className="library-course-materials">
          {materials.map((material) => (
            <button className={selectedMaterialIds.includes(material.id) ? "active" : ""} key={material.id} type="button" aria-pressed={selectedMaterialIds.includes(material.id)} onClick={() => onToggleMaterial(material.id)}>
              <span>{material.extension}</span>
              <strong>{material.title}</strong>
              <small>{material.detail}</small>
            </button>
          ))}
        </div>
        <button className="dialog-primary-button" type="button" onClick={onCreate}>
          创建课程草案
        </button>
      </section>
    </div>
  );
}
