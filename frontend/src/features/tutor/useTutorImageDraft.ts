import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { listModelConfigs } from "../../api/settings";
import { deleteTutorAttachment, uploadTutorAttachment, type TutorImageAttachment } from "../../api/tutor";

export type DraftTutorImage = {
  key: string;
  file: File;
  previewUrl: string;
  attachment: TutorImageAttachment | null;
  status: "uploading" | "ready" | "failed";
  error?: string;
};

export function useTutorImageDraft(ensureSession: () => Promise<string>, onNotice: (message: string) => void) {
  const [images, setImages] = useState<DraftTutorImage[]>([]);
  const settingsQuery = useQuery({ queryKey: ["settings", "model-configs"], queryFn: listModelConfigs, staleTime: 30_000 });
  const imagesRef = useRef<DraftTutorImage[]>([]);
  useEffect(() => { imagesRef.current = images; }, [images]);
  useEffect(() => () => imagesRef.current.forEach((image) => URL.revokeObjectURL(image.previewUrl)), []);

  async function addFiles(files: File[]) {
    const candidates = files.filter((file) => ["image/png", "image/jpeg"].includes(file.type));
    if (candidates.length !== files.length) onNotice("图片提问只接受 PNG 或 JPEG。");
    if (images.length + candidates.length > 3) { onNotice("每条消息最多添加 3 张图片。"); return; }
    if (candidates.length === 0) return;
    const drafts = candidates.map((file) => ({ key: crypto.randomUUID(), file, previewUrl: URL.createObjectURL(file), attachment: null, status: "uploading" as const }));
    setImages((current) => [...current, ...drafts]);
    try {
      const sessionId = await ensureSession();
      await Promise.all(drafts.map(async (draft) => {
        try {
          const response = await uploadTutorAttachment(sessionId, draft.file);
          setImages((current) => current.map((item) => item.key === draft.key ? { ...item, attachment: response.data, status: "ready" } : item));
        } catch (error) {
          setImages((current) => current.map((item) => item.key === draft.key ? { ...item, status: "failed", error: error instanceof Error ? error.message : "图片上传失败" } : item));
        }
      }));
    } catch {
      setImages((current) => current.map((item) => drafts.some((draft) => draft.key === item.key) ? { ...item, status: "failed", error: "会话创建失败" } : item));
    }
  }

  async function removeImage(key: string) {
    const image = images.find((item) => item.key === key);
    setImages((current) => current.filter((item) => item.key !== key));
    if (image) URL.revokeObjectURL(image.previewUrl);
    if (image?.attachment) await deleteTutorAttachment(image.attachment.id).catch(() => undefined);
  }

  function discardAll() {
    const pending = [...images];
    setImages([]);
    pending.forEach((image) => {
      URL.revokeObjectURL(image.previewUrl);
      if (image.attachment) void deleteTutorAttachment(image.attachment.id).catch(() => undefined);
    });
  }

  function clearAfterSend() { images.forEach((image) => URL.revokeObjectURL(image.previewUrl)); setImages([]); }

  return {
    images, addFiles, removeImage, clearAfterSend, discardAll,
    attachmentIds: images.flatMap((image) => image.status === "ready" && image.attachment ? [Number(image.attachment.id)] : []),
    uploading: images.some((image) => image.status === "uploading"),
    hasFailed: images.some((image) => image.status === "failed"),
    visionReady: Boolean(settingsQuery.data?.data.default_vision_config_id)
  };
}
