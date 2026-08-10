import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";

import { getAiJob } from "../../api/aiJobs";
import { uploadMaterial } from "../../api/materials";
import { renameTutorSession } from "../../api/tutor";
import type { FeedbackTone } from "../../components/feedback/InlineFeedback";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { invalidateLearningNextActions } from "../learning-actions/learningActions";
import type { LibraryMaterial } from "./homeLearningModel";

type HomeMaterialSelectionParams = {
  activeThreadId: string | null;
  initialMaterialIds: string[];
  materials: LibraryMaterial[];
  onComposerFeedback: (feedback: { message: string; tone: FeedbackTone }) => void;
};

export function useHomeMaterialSelection({
  activeThreadId,
  initialMaterialIds,
  materials,
  onComposerFeedback
}: HomeMaterialSelectionParams) {
  const queryClient = useQueryClient();
  const { trackJob } = useAiJobs();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [draftIds, setDraftIds] = useState<string[]>(() => initialMaterialIds);
  const [dialogOpen, setDialogOpen] = useState(() => initialMaterialIds.length > 0);
  const [feedback, setFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const effectiveIds = useMemo(
    () => selectedIds.filter((materialId) => materials.some((material) => material.id === materialId)),
    [materials, selectedIds]
  );
  const closeDialog = useCallback(() => setDialogOpen(false), []);

  function openDialog() {
    setDraftIds(effectiveIds);
    setFeedback(null);
    setDialogOpen(true);
  }

  function toggleDraft(materialId: string) {
    setDraftIds((current) => {
      if (!current.includes(materialId) && current.length >= 10) {
        setFeedback({ message: "单个会话最多选择 10 份参考资料。", tone: "warning" });
        return current;
      }
      setFeedback(null);
      return current.includes(materialId)
        ? current.filter((id) => id !== materialId)
        : [...current, materialId];
    });
  }

  async function confirmSelection() {
    const nextIds = draftIds.filter((materialId) => materials.some((material) => material.id === materialId));
    if (activeThreadId) {
      try {
        await renameTutorSession(activeThreadId, { selected_material_ids: nextIds.map(Number) });
      } catch {
        setFeedback({ message: "参考资料保存失败，请稍后重试。", tone: "warning" });
        return;
      }
    }
    setSelectedIds(nextIds);
    setFeedback(null);
    closeDialog();
    void queryClient.invalidateQueries({ queryKey: ["tutor", "home-history"] });
  }

  async function uploadDocuments(files: File[]) {
    if (files.length === 0) return;
    try {
      for (const file of files) {
        const response = await uploadMaterial({ file });
        if (response.data.ingestion_job_id) {
          trackJob(await getAiJob(response.data.ingestion_job_id));
        }
      }
      await queryClient.invalidateQueries({ queryKey: ["materials", "list"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      await invalidateLearningNextActions(queryClient);
      onComposerFeedback({ message: `${files.length} 份资料已上传，正在后台识别目录和正文切片。`, tone: "success" });
    } catch {
      onComposerFeedback({ message: "资料上传失败，请稍后再试。", tone: "warning" });
    }
  }

  const restoreSelection = useCallback((materialIds: string[]) => {
    setSelectedIds(materialIds);
    setDraftIds(materialIds);
  }, []);

  function resetSelection() {
    setSelectedIds([]);
    setDraftIds([]);
    setFeedback(null);
    closeDialog();
  }

  return {
    closeDialog,
    confirmSelection,
    dialogOpen,
    draftIds,
    effectiveIds,
    feedback,
    openDialog,
    resetSelection,
    restoreSelection,
    toggleDraft,
    uploadDocuments
  };
}
