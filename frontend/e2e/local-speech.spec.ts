import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { expect, test } from "@playwright/test";

test("authenticated local speech transcribes public PCM and plays generated WAV", async ({ page, request }) => {
  test.setTimeout(120_000);
  const login = await request.post("/api/v1/auth/login", {
    data: { account: "e2e_evidence_loop", password: "SyntheticLoop2026" }
  });
  expect(login.ok()).toBeTruthy();
  const token: string = (await login.json()).data.access_token;
  const headers = { Authorization: `Bearer ${token}` };
  await page.goto("/login");
  await page.getByLabel("账号").click(); // User gesture permits audio playback.
  const source = await readFile(resolve("../storage/models/speech/sensevoice/test_wavs/zh.wav"));
  let pcm: Buffer | undefined;
  for (let offset = 12; offset + 8 <= source.length;) {
    const size = source.readUInt32LE(offset + 4);
    if (source.toString("ascii", offset, offset + 4) === "data") {
      pcm = source.subarray(offset + 8, offset + 8 + size);
      break;
    }
    offset += 8 + size + (size % 2);
  }
  expect(pcm).toBeDefined();
  const transcript = await request.post("/api/v1/speech/transcriptions", {
    headers, multipart: { file: { name: "public-sample.pcm", mimeType: "audio/pcm", buffer: pcm! } }
  });
  expect(transcript.ok()).toBeTruthy();
  const data = (await transcript.json()).data;
  expect(data.provider).toBe("sherpa_onnx");
  expect(data.transcript).toContain("九点");
  const playback = await page.evaluate(async (token) => {
    const response = await fetch("/api/v1/speech/synthesis", {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text: "数据结构是一门课程。" })
    });
    if (!response.ok) throw new Error(`Local speech returned ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    try {
      await audio.play();
      await new Promise<void>((resolve, reject) => {
        audio.onended = () => resolve();
        audio.onerror = () => reject(new Error("WAV playback failed"));
      });
      return { type: blob.type, seconds: audio.currentTime };
    } finally { audio.pause(); URL.revokeObjectURL(url); }
  }, token);
  expect(playback.type).toBe("audio/wav");
  expect(playback.seconds).toBeGreaterThan(1);
});
