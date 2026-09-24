import { expect, test } from "@playwright/test";
import type { ResourceArtifact, ResourceType } from "../src/api/resources";

test("production chunks render real diagrams and execute browser Python", async ({ page, request }) => {
  test.setTimeout(180_000);
  const login = await request.post("/api/v1/auth/login", { data: { account: "e2e_evidence_loop", password: "SyntheticLoop2026" } });
  expect(login.ok()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await login.json()).data.access_token}` };
  const courses = await request.get("/api/v1/courses", { headers });
  const course = (await courses.json()).data.find((item: { title: string }) => item.title === "受控 A* 学习闭环");
  const resources = await request.get(`/api/v1/resources?course_id=${course.id}`, { headers });
  const resource = (await resources.json()).data.find((item: { resource_type: string }) => item.resource_type === "doc");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login");
  await page.getByLabel("账号").fill("e2e_evidence_loop");
  await page.getByLabel("密码", { exact: true }).fill("SyntheticLoop2026");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);

  // Replace only the resource payload. Libraries and production chunks remain real.
  // Fixtures are not persisted and make no model-quality or scoring claims.
  let kind: ResourceType = "mindmap";
  let artifact: ResourceArtifact = {
    kind: "mindmap", markmap_markdown: "# 队列\n## 先进先出\n## 队尾入队",
    tree: { id: "root", title: "队列", children: [] }, citation_refs: []
  };
  await page.route(`**/api/v1/resources/${resource.id}`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.data.resource_type = kind;
    body.data.content_json = { schema_version: 2, artifact };
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/v1/resources?**", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.data = body.data.map((item: { id: string }) => item.id === resource.id
      ? { ...item, resource_type: kind, content_json: { schema_version: 2, artifact } }
      : item);
    await route.fulfill({ response, json: body });
  });
  const open = () => page.goto(`/app/studio?course_id=${course.id}&resource_id=${resource.id}`);
  await open();
  const nodes = page.locator(".resource-markmap-canvas .markmap-node");
  await expect(nodes).toHaveCount(3);
  await expect(page.locator(".resource-markmap-canvas .markmap-link")).toHaveCount(2);
  await page.getByRole("button", { name: "放大思维导图", exact: true }).click();

  kind = "animation";
  artifact = { kind: "animation", scenes: [
    { id: "a1", title: "入队", narration: "进入队尾", duration_ms: 3000, diagram: "flowchart LR\n A[新元素] --> B[队尾]" },
    { id: "a2", title: "出队", narration: "离开队头", duration_ms: 3000, diagram: "flowchart LR\n A[队头] --> B[取出元素]" }
  ], default_scene_duration_ms: 3000, citation_refs: [] };
  await open();
  await expect(page.locator(".resource-mermaid-canvas svg")).toBeVisible();
  await page.getByRole("button", { name: "下一个动画场景" }).click();
  await expect(page.locator(".resource-mermaid-canvas svg")).toContainText("取出元素");

  kind = "code";
  artifact = { kind: "code_lab", language: "python", runtime: "pyodide", entry_file: "main.py",
    files: [{ path: "main.py", content: "print(6 * 7)" }], instructions: [], expected_output: "42", tasks: [], citation_refs: [] };
  await open();
  await expect(page.locator(".cm-content")).toContainText("print(6 * 7)");
  await page.getByRole("button", { name: "运行 Python 代码" }).click();
  await expect(page.locator(".resource-code-output.completed pre")).toHaveText("42", { timeout: 90_000 });
  expect(errors).toEqual([]);

  // Opt-in live platform check, excluded from deterministic/offline CI.
  // Uses the real resource page and iframe, but never persists the video fixture.
  if (process.env.EDUNOVA_LIVE_VIDEO === "1") {
    kind = "video";
    artifact = { kind: "external_video", platform: "bilibili", video_id: "BV1b54y117KG",
      title: "Python基本语法：列表推导式", watch_url: "https://www.bilibili.com/video/BV1b54y117KG",
      fit_reason: "合成资源仅验证播放器，不作为课程或评分证据", embed_status: "unknown",
      external_supplement: true, citation_refs: [] };
    await open();
    const embed = page.locator('.external-video-frame iframe');
    await expect(embed).toBeVisible();
    const frame = await embed.contentFrame();
    const video = frame.locator('video');
    await expect(video).toBeAttached({ timeout: 30_000 });
    await video.evaluate(async (element: HTMLVideoElement) => {
      element.muted = true;
      await element.play();
    });
    const start = await video.evaluate((element: HTMLVideoElement) => element.currentTime);
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime),
      { timeout: 20_000 }).toBeGreaterThan(start + 2);
    await expect(page.getByRole('link', { name: /无法播放时前往原平台/ }))
      .toHaveAttribute('href', 'https://www.bilibili.com/video/BV1b54y117KG');
    console.log('Live resource video: playback advanced over two seconds; original-platform fallback present.');
  }
});
