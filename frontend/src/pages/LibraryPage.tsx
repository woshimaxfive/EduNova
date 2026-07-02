import { BookOpen, FileArrowUp, MagnifyingGlass, SealCheck, Sparkle, X } from "@phosphor-icons/react";
import { useState } from "react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { type MaterialSource } from "../types/api";
import { PageFrame } from "./PageFrame";

const fileMeta = {
  builtin: { type: "DOC", modified: "今天", size: "1.2 MB" },
  markdown: { type: "MD", modified: "昨天", size: "68 KB" }
} as const;

export function LibraryPage() {
  const [activeMaterial, setActiveMaterial] = useState<MaterialSource | null>(null);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const { notice, showNotice } = useActionNotice();

  function showMaterialCitation(material: MaterialSource) {
    setActiveMaterial(material);
    showNotice(`已打开「${material.title}」的引用预览。`, "success");
  }

  return (
    <>
      <PageFrame kicker="资料库" title="资料库" description="课件、电子书、期末题和课程资料都先进入这里，再决定用于对话、加入课程或生成新课程。">
        <section className="library-file-shell" role="region" aria-label="文件库">
          <div className="library-command-row">
            <label className="file-search-field">
              <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
              <input aria-label="搜索资料" placeholder="搜索资料" />
            </label>
            <button className="library-action-button" type="button" onClick={() => showNotice("真实上传会在资料解析接口接入后开放。")}>
              <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
              <span>上传资料</span>
            </button>
            <button className="library-action-button primary" type="button" onClick={() => setIsCourseDialogOpen(true)}>
              <Sparkle size={18} weight="duotone" aria-hidden="true" />
              <span>从资料生成课程</span>
            </button>
          </div>

          <div className="library-filter-row" aria-label="资料类型">
            <button className="active" type="button">
              全部
            </button>
            <button type="button">文档</button>
            <button type="button">题目</button>
            <button type="button">课程内置</button>
          </div>

          <div className="library-file-table">
            <div className="library-file-header" aria-hidden="true">
              <span>名称</span>
              <span>修改时间</span>
              <span>大小</span>
            </div>
            {demoLearningSpace.materials.map((material) => {
              const meta = fileMeta[material.type as keyof typeof fileMeta] ?? { type: "FILE", modified: "最近", size: "未知" };

              return (
                <button className="library-file-row" key={material.id} type="button" onClick={() => showMaterialCitation(material)}>
                  <span className="library-file-icon" aria-hidden="true">
                    {material.parseStatus === "completed" ? <SealCheck size={18} weight="duotone" /> : <BookOpen size={18} weight="duotone" />}
                  </span>
                  <span className="library-file-main">
                    <strong>{material.title}</strong>
                    <small>
                      {meta.type} · {material.coverageLabel} · {material.parseStatus === "completed" ? "已解析" : "解析中"}
                    </small>
                  </span>
                  <span>{meta.modified}</span>
                  <span>{meta.size}</span>
                </button>
              );
            })}
          </div>

          {activeMaterial ? (
            <section className="material-action-feedback" role="region" aria-label="资料动作反馈">
              <strong>{activeMaterial.title}</strong>
              <p>
                {activeMaterial.coverageLabel}，当前状态：
                {activeMaterial.parseStatus === "completed" ? "已完成解析" : "正在处理"}。后续接入真实引用接口后会显示片段、页码和置信度。
              </p>
            </section>
          ) : null}

          <ActionNotice notice={notice} />
        </section>
      </PageFrame>

      {isCourseDialogOpen ? (
        <LibraryCourseDialog
          onClose={() => setIsCourseDialogOpen(false)}
          onCreate={() => showNotice("已创建课程草案演示态，真实创建会接入课程 API。", "success")}
        />
      ) : null}
    </>
  );
}

type LibraryCourseDialogProps = {
  onClose: () => void;
  onCreate: () => void;
};

function LibraryCourseDialog({ onClose, onCreate }: LibraryCourseDialogProps) {
  return (
    <div className="course-dialog-backdrop">
      <section className="course-dialog library-course-dialog" role="dialog" aria-modal="true" aria-labelledby="library-course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <p className="section-kicker">Course builder</p>
          <h2 id="library-course-dialog-title">从资料生成课程</h2>
          <p>这个浮层不会替换资料库。先选择资料，再让 EduNova 生成课程目录、知识点和第一轮复习任务。</p>
        </div>
        <div className="library-course-materials">
          {demoLearningSpace.materials.map((material) => (
            <button key={material.id} type="button" aria-pressed="false">
              <span>{material.type === "builtin" ? "DOC" : "MD"}</span>
              <strong>{material.title}</strong>
              <small>{material.coverageLabel}</small>
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
