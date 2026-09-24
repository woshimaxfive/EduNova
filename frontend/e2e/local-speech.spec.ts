import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { expect, test } from "@playwright/test";

test("local recognition and browser-only offline read aloud", async ({ page, request }) => {
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
  const retired = await request.post("/api/v1/speech/synthesis", { headers, data: { text: "测试" } });
  expect(retired.status()).toBe(410);
  await page.context().setOffline(true);
  const playback = await page.evaluate(async () => {
    const synthesis = window.speechSynthesis;
    const choose = () => synthesis.getVoices().find(v => v.localService && /^zh[-_]/i.test(v.lang));
    let voice = choose();
    if (!voice) {
      await new Promise<void>(resolve => {
        const done = () => { clearTimeout(timer); synthesis.removeEventListener("voiceschanged", done); resolve(); };
        const timer = setTimeout(done, 1500);
        synthesis.addEventListener("voiceschanged", done);
      });
      voice = choose();
    }
    if (!voice) return { available: false, completed: false };
    return await new Promise<{ available: boolean; completed: boolean }>((resolve, reject) => {
      const utterance = new SpeechSynthesisUtterance("数据结构是一门课程。");
      utterance.voice = voice!;
      utterance.lang = voice!.lang;
      Object.assign(window, { speechSmokeUtterance: utterance });
      utterance.onend = () => {
        Reflect.deleteProperty(window, "speechSmokeUtterance");
        resolve({ available: true, completed: true });
      };
      utterance.onerror = event => {
        Reflect.deleteProperty(window, "speechSmokeUtterance");
        reject(new Error(event.error));
      };
      synthesis.speak(utterance);
    });
  });
  await page.context().setOffline(false);
  console.info("Offline browser speech result:", playback);
  if (playback.available) expect(playback.completed).toBe(true);
  else test.info().annotations.push({ type: "browser-capability", description: "No installed local Chinese voice; rejection is covered by hook tests." });
});
