import { ImageSquare, SpinnerGap, Trash, X } from "@phosphor-icons/react";
import { type ChangeEvent, type ClipboardEvent, type DragEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { getTutorAttachmentBlob, type TutorImageAttachment } from "../../api/tutor";
import { PATHS } from "../../app/routePaths";
import { ModalFrame } from "../../components/primitives/Dialog";
import { type useTutorImageDraft } from "./useTutorImageDraft";

export function TutorImagePicker({
  draft,
  compact = false
}: {
  draft: ReturnType<typeof useTutorImageDraft>;
  compact?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
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
    <div className={compact ? "tutor-image-picker compact" : "tutor-image-picker"} onPaste={paste} onDrop={drop} onDragOver={(event) => event.preventDefault()}>
      <input ref={inputRef} className="visually-hidden" type="file" accept="image/png,image/jpeg" multiple onChange={select} />
      {draft.images.length ? (
        <div className="tutor-image-drafts" aria-label="待发送图片">
          {draft.images.map((image) => (
            <figure key={image.key} className={image.status}>
              <img src={image.previewUrl} alt={image.file.name} />
              {image.status === "uploading" ? <SpinnerGap className="spin" size={18} aria-label="正在上传" /> : null}
              {image.status === "failed" ? <span>{image.error}</span> : null}
              <button type="button" onClick={() => void draft.removeImage(image.key)} aria-label={`移除 ${image.file.name}`}><Trash size={14} /></button>
            </figure>
          ))}
        </div>
      ) : null}
      <button type="button" className="tutor-image-add" onClick={() => inputRef.current?.click()} disabled={draft.images.length >= 3}>
        <ImageSquare size={18} weight="duotone" /><span>图片提问</span>
      </button>
      <small>可选择、粘贴或拖入 PNG/JPEG，最多 3 张</small>
      {!draft.visionReady ? (
        <Link to={`${PATHS.settings}?section=model`} target="_blank" rel="noreferrer">
          配置图片理解模型
        </Link>
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
