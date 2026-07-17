import { ImageSquare, Paperclip, SpinnerGap, Trash, X } from "@phosphor-icons/react";
import { type ChangeEvent, type ClipboardEvent, type DragEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { getTutorAttachmentBlob, type TutorImageAttachment } from "../../api/tutor";
import { PATHS } from "../../app/routePaths";
import { ModalFrame } from "../../components/primitives/Dialog";
import { type useTutorImageDraft } from "./useTutorImageDraft";

export function TutorImagePicker({
  draft,
  compact = false,
  display = "all"
}: {
  draft: ReturnType<typeof useTutorImageDraft>;
  compact?: boolean;
  display?: "all" | "previews" | "controls";
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const showPreviews = display !== "controls";
  const showControls = display !== "previews";
  function select(event: ChangeEvent<HTMLInputElement>) {
    void draft.addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }
  function paste(event: ClipboardEvent<HTMLDivElement>) {
    const files = Array.from(event.clipboardData.files).filter((file) => file.type.startsWith("image/"));
    if (files.length) { event.preventDefault(); void draft.addFiles(files); }
  }
  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    void draft.addFiles(Array.from(event.dataTransfer.files));
  }
  return (
    <div className={["tutor-image-picker", compact ? "compact" : "", `tutor-image-${display}`].filter(Boolean).join(" ")} onPaste={paste} onDrop={drop} onDragOver={(event) => event.preventDefault()}>
      {showControls ? <input ref={inputRef} className="visually-hidden" type="file" aria-label="上传资料文件" accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg" multiple onChange={select} /> : null}
      {showPreviews && draft.images.length ? (
        <div className="tutor-image-drafts" aria-label="待发送图片">
          {draft.images.map((image) => (
            <figure key={image.key} className={image.status}>
              {image.previewUrl ? <img src={image.previewUrl} alt={image.filename} /> : <ImageSquare size={24} aria-hidden="true" />}
              {image.status === "uploading" ? <SpinnerGap className="spin" size={18} aria-label="正在上传" /> : null}
              {image.status === "failed" ? <span>{image.error}</span> : null}
              <button type="button" onClick={() => void draft.removeImage(image.key)} aria-label={`移除 ${image.filename}`}><Trash size={14} /></button>
            </figure>
          ))}
        </div>
      ) : null}
      {showControls ? <button type="button" className="tutor-image-add" title="添加资料" onClick={() => setIsPickerOpen(true)}>
        <Paperclip size={18} weight="duotone" />
      </button> : null}
      {showControls && !draft.visionReady ? (
        <Link to={`${PATHS.settings}?section=model`} target="_blank" rel="noreferrer">
          配置图片理解模型
        </Link>
      ) : null}
      {showControls && isPickerOpen ? (
        <ModalFrame title="添加图片资料" layerClassName="tutor-attachment-dialog" onClose={() => setIsPickerOpen(false)}>
          <section className="tutor-attachment-panel" aria-label="添加图片资料">
            <header>
              <h2>添加图片资料</h2>
              <button type="button" aria-label="关闭添加图片资料" onClick={() => setIsPickerOpen(false)}><X size={20} /></button>
            </header>
            <button type="button" className="tutor-attachment-upload" onClick={() => inputRef.current?.click()}>
              上传文件或图片
            </button>
            <div className="tutor-library-images" aria-label="资料库图片">
              {draft.libraryImages.length ? draft.libraryImages.map((image) => (
                <button
                  type="button"
                  key={image.id}
                  onClick={() => {
                    void draft.addMaterial(image);
                    setIsPickerOpen(false);
                  }}
                >
                  <ImageSquare size={19} weight="duotone" aria-hidden="true" />
                  <span><strong>{image.title}</strong><small>{image.size}</small></span>
                </button>
              )) : <p>资料库中还没有可添加的图片。</p>}
            </div>
          </section>
        </ModalFrame>
      ) : null}
    </div>
  );
}

export function SecureTutorImages({ attachments }: { attachments: TutorImageAttachment[] }) {
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const created: string[] = [];
    void Promise.all(attachments.filter((item) => item.status !== "deleted").map(async (item) => {
      const blob = await getTutorAttachmentBlob(item.id);
      const url = URL.createObjectURL(blob); created.push(url);
      if (alive) setUrls((current) => ({ ...current, [item.id]: url }));
    }));
    return () => { alive = false; created.forEach(URL.revokeObjectURL); };
  }, [attachments]);
  if (!attachments.length) return null;
  const selected = attachments.find((item) => item.id === active);
  return (
    <>
      <div className="tutor-message-images">
        {attachments.map((item) => item.status === "deleted" ? <span key={item.id}>图片已删除</span> : (
          <button type="button" key={item.id} onClick={() => setActive(item.id)} aria-label={`查看图片 ${item.filename}`}>
            {urls[item.id] ? <img src={urls[item.id]} alt={item.filename} /> : <SpinnerGap className="spin" size={20} />}
          </button>
        ))}
      </div>
      {active && selected && urls[active] ? (
        <ModalFrame title={`查看 ${selected.filename}`} layerClassName="tutor-image-dialog" onClose={() => setActive(null)}>
          <section><button type="button" onClick={() => setActive(null)} aria-label="关闭图片"><X size={20} /></button><img src={urls[active]} alt={selected.filename} /></section>
        </ModalFrame>
      ) : null}
    </>
  );
}
