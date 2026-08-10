import type { QueryClient } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";

import { getAiJob } from "../../api/aiJobs";
import { uploadMaterial } from "../../api/materials";
import { createTutorSession } from "../../api/tutor";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { useTutorImageDraft } from "../tutor/useTutorImageDraft";

type CourseTutorAttachmentsParams = {
  courseId: number;
  enabled: boolean;
  selectedSessionId: string | null;
  queryClient: QueryClient;
  setActiveSessionId: Dispatch<SetStateAction<string | null>>;
  setFeedback: Dispatch<SetStateAction<string | null>>;
};

export function useCourseTutorAttachments({
  courseId,
  enabled,
  selectedSessionId,
  queryClient,
  setActiveSessionId,
  setFeedback
}: CourseTutorAttachmentsParams) {
  const { trackJob } = useAiJobs();

  async function ensureImageSession() {
    if (selectedSessionId) return selectedSessionId;
    if (!enabled) throw new Error("课程地址无效");
    const created = await createTutorSession({
      scope: "course",
      course_id: courseId,
      mode: "chat",
      title: "图片提问"
    });
    setActiveSessionId(created.data.id);
    return created.data.id;
  }

  async function uploadDocuments(files: File[]) {
    if (!enabled || files.length === 0) return;
    try {
      for (const file of files) {
        const response = await uploadMaterial({ file, courseId });
        if (response.data.ingestion_job_id) {
          trackJob(await getAiJob(response.data.ingestion_job_id));
        }
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["courses", "overview", courseId] })
      ]);
      setFeedback(null);
    } catch {
      setFeedback("资料上传失败，请稍后再试。");
    }
  }

  return useTutorImageDraft(ensureImageSession, setFeedback, uploadDocuments);
}
