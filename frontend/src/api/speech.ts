import { apiClient, MODEL_OPERATION_TIMEOUT_MS } from "./client";

export type SpeechTranscription = {
  transcript: string;
  provider: string;
  duration_ms: number;
};

export async function transcribeSpeech(audio: Blob): Promise<SpeechTranscription> {
  const form = new FormData();
  form.append("file", audio, "speech.pcm");
  const response = await apiClient.post<{ data: SpeechTranscription }>("/speech/transcriptions", form, {
    timeout: MODEL_OPERATION_TIMEOUT_MS
  });
  return response.data.data;
}

export async function synthesizeSpeech(text: string): Promise<Blob> {
  const response = await apiClient.post<Blob>("/speech/synthesis", { text }, {
    responseType: "blob",
    timeout: MODEL_OPERATION_TIMEOUT_MS
  });
  return response.data;
}
