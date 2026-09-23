import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { listMaterials, type MaterialListItem } from "../../api/materials";
import { getModelSettings, type ModelSettingsSummary } from "../../api/settings";
import {
  attachTutorMaterial,
  deleteTutorAttachment,
  getTutorAttachmentBlob,
  uploadTutorAttachment,
  type TutorImageAttachment
} from "../../api/tutor";

export type DraftTutorImage = {
  key: string;
  filename: string;
  previewUrl: string;
  attachment: TutorImageAttachment | null;
  status: "uploading" | "ready" | "failed";
  error?: string;
};

export function hasUsableVisionModel(settings?: ModelSettingsSummary): boolean {
  return Boolean(settings?.can_use_vision_model);
}

export function useTutorImageDraft(
  ensureSession: () => Promise<string>,
  onNotice: (message: string) => void,
  onDocumentFiles?: (files: File[]) => Promise<void>
) {
  const queryClient = useQueryClient();
  const [images, setImages] = useState<DraftTutorImage[]>([]);
  const settingsQuery = useQuery({ queryKey: ["settings", "model"], queryFn: getModelSettings, staleTime: 30_000 });
  const materialsQuery = useQuery({ queryKey: ["materials", "list"], queryFn: () => listMaterials(), staleTime: 30_000 });
  const imagesRef = useRef<DraftTutorImage[]>([]);
  useEffect(() => { imagesRef.current = images; }, [images]);
  useEffect(() => () => imagesRef.current.forEach((image) => URL.revokeObjectURL(image.previewUrl)), []);

  async function addFiles(files: File[]) {
    const isSupportedImage = (file: File) => (
      ["image/png", "image/jpeg"].includes(file.type)
      || /\.(?:png|jpe?g)$/i.test(file.name)
    );
    const imageFiles = files.filter(isSupportedImage);
    const unsupportedImages = files.filter((file) => file.type.startsWith("image/") && !isSupportedImage(file));
    const documentFiles = files.filter((file) => !isSupportedImage(file) && !file.type.startsWith("image/"));
    if (unsupportedImages.length > 0) onNotice("图片提问只接受 PNG 或 JPEG。");
    if (documentFiles.length > 0 && onDocumentFiles) await onDocumentFiles(documentFiles);
    if (images.length + imageFiles.length > 3) { onNotice("每条消息最多添加 3 张图片。"); return; }
    if (imageFiles.length === 0) return;
    if (!hasUsableVisionModel(settingsQuery.data?.data)) { onNotice("请先在设置中验证主模型的图片能力；普通文档仍可上传。"); return; }
    const drafts = imageFiles.map((file) => ({
      key: crypto.randomUUID(), filename: file.name, previewUrl: URL.createObjectURL(file),
      attachment: null, status: "uploading" as const
    }));
    setImages((current) => [...current, ...drafts]);
    try {
      const sessionId = await ensureSession();
      await Promise.all(drafts.map(async (draft, index) => {
        try {
          const response = await uploadTutorAttachment(sessionId, imageFiles[index]);
          setImages((current) => current.map((item) => item.key === draft.key ? { ...item, attachment: response.data, status: "ready" } : item));
        } catch (error) {
          setImages((current) => current.map((item) => item.key === draft.key ? { ...item, status: "failed", error: error instanceof Error ? error.message : "图片上传失败" } : item));
        }
      }));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] })
      ]);
    } catch {
      setImages((current) => current.map((item) => drafts.some((draft) => draft.key === item.key) ? { ...item, status: "failed", error: "会话创建失败" } : item));
    }
  }

  async function addMaterial(material: MaterialListItem) {
    if (!hasUsableVisionModel(settingsQuery.data?.data)) { onNotice("请先在设置中验证主模型的图片能力。"); return; }
    if (images.some((image) => image.attachment?.material_id === material.id)) return;
    if (images.length >= 3) { onNotice("每条消息最多添加 3 张图片。"); return; }
    const key = crypto.randomUUID();
    setImages((current) => [...current, { key, filename: material.title, previewUrl: "", attachment: null, status: "uploading" }]);
    try {
      const sessionId = await ensureSession();
      const response = await attachTutorMaterial(sessionId, material.id);
      const blob = await getTutorAttachmentBlob(response.data.id);
      const previewUrl = URL.createObjectURL(blob);
      setImages((current) => current.map((item) => item.key === key ? { ...item, previewUrl, attachment: response.data, status: "ready" } : item));
    } catch (error) {
      setImages((current) => current.map((item) => item.key === key ? { ...item, status: "failed", error: error instanceof Error ? error.message : "图片添加失败" } : item));
    }
  }

  async function removeImage(key: string) {
    const image = images.find((item) => item.key === key);
    setImages((current) => current.filter((item) => item.key !== key));
    if (image?.previewUrl) URL.revokeObjectURL(image.previewUrl);
    if (image?.attachment) await deleteTutorAttachment(image.attachment.id).catch(() => undefined);
  }

  function discardAll() {
    const pending = [...images];
    setImages([]);
    pending.forEach((image) => {
      if (image.previewUrl) URL.revokeObjectURL(image.previewUrl);
      if (image.attachment) void deleteTutorAttachment(image.attachment.id).catch(() => undefined);
    });
  }

  function clearAfterSend() {
    images.forEach((image) => { if (image.previewUrl) URL.revokeObjectURL(image.previewUrl); });
    setImages([]);
  }

  return {
    images, addFiles, addMaterial, removeImage, clearAfterSend, discardAll,
    libraryImages: (Array.isArray(materialsQuery.data?.data) ? materialsQuery.data.data : []).filter((material) => material.category === "image"),
    attachmentIds: images.flatMap((image) => image.status === "ready" && image.attachment ? [Number(image.attachment.id)] : []),
    uploading: images.some((image) => image.status === "uploading"),
    hasFailed: images.some((image) => image.status === "failed"),
    visionReady: hasUsableVisionModel(settingsQuery.data?.data)
  };
}
