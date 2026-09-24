import axios from "axios";

import { apiClient, MODEL_OPERATION_TIMEOUT_MS } from "./client";

export type SpeechTranscription = {
  transcript: string;
  provider: string;
  duration_ms: number;
};

export class SpeechRequestError extends Error {
  constructor(message: string, readonly code = "SPEECH_PROVIDER_ERROR") {
    super(message);
    this.name = "SpeechRequestError";
  }
}

export async function transcribeSpeech(audio: Blob): Promise<SpeechTranscription> {
  const form = new FormData();
  form.append("file", audio, "speech.pcm");
  try {
    const response = await apiClient.post<{ data: SpeechTranscription }>("/speech/transcriptions", form, {
      timeout: MODEL_OPERATION_TIMEOUT_MS
    });
    return response.data.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const body = error.response?.data as { error?: { code?: string; message?: string } } | undefined;
      throw new SpeechRequestError(
        body?.error?.message ?? "本地语音识别暂时不可用。",
        body?.error?.code
      );
    }
    throw error;
  }
}

export async function synthesizeSpeech(text: string): Promise<Blob> {
  const response = await apiClient.post<Blob>("/speech/synthesis", { text }, {
    responseType: "blob",
    timeout: MODEL_OPERATION_TIMEOUT_MS
  });
  return response.data;
}
