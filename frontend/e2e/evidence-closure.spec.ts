import { expect, test } from "@playwright/test";

test("approved version closes through bound evidence and server grading without duplicate effects", async ({ page, request }) => {
  test.setTimeout(180_000);
  // The isolated seed uses controlled model responses through real LangGraph graphs.
  // These synthetic credentials are not installed by the application.
  const login = await request.post("/api/v1/auth/login", { data: { account: "e2e_evidence_loop", password: "SyntheticLoop2026" } });
  expect(login.ok()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await login.json()).data.access_token}` };
  const get = async (path: string) => {
    const response = await request.get(`/api/v1${path}`, { headers });
    expect(response.ok(), path).toBeTruthy();
    return (await response.json()).data;
  };
  const courses = await get("/courses");
  const course = courses.find((item: { title: string }) => item.title === "受控 A* 学习闭环");
  expect(course).toBeTruthy();
  const drafts = await get(`/paths/drafts?course_id=${course.id}`);
  expect(drafts).toHaveLength(1);
  const draft = drafts[0];
  const pathId = draft.id;
  const approval = await request.post(`/api/v1/paths/${pathId}/approve`, { headers, data: { expected_active_path_id: null } });
  expect(approval.ok()).toBeTruthy();
  const task = (await approval.json()).data.tasks[0];
  const resources = await get(`/resources?course_id=${course.id}`);
  const doc = resources.find((item: { resource_type: string }) => item.resource_type === "doc");
  const quiz = resources.find((item: { resource_type: string }) => item.resource_type === "quiz");
  const progressPath = `/paths/tasks/${task.id}/progress`;
  expect(await get(progressPath)).toMatchObject({ activity_completed: false, assessment_passed: false, mastered: false, next_step: "study_resource" });
  // No token: ownership endpoint must not leak even a known task identifier.
  expect((await request.get(`/api/v1${progressPath}`)).status()).toBe(401);
  await page.goto("/login");
  await page.getByLabel("账号").fill("e2e_evidence_loop");
  await page.getByLabel("密码", { exact: true }).fill("SyntheticLoop2026");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  const studio = (id: string) => `/app/studio?course_id=${course.id}&path_task_id=${task.id}&resource_id=${id}`;
  await page.goto(studio(doc.id));
  await expect(page.getByRole("region", { name: "任务证据状态" })).toContainText("尚未掌握");
  await page.getByRole("button", { name: "完成学习", exact: true }).click();
  await expect(page.getByText("这份资源已完成", { exact: true })).toBeVisible();
  expect(await get(progressPath)).toMatchObject({ completed_activity_count: 1, assessment_passed: false, mastered: false, next_step: "take_assessment", next_resource_id: quiz.id });
  const next = await get(`/learning/next-action?course_id=${course.id}`);
  expect(next).toMatchObject({ kind: "continue_path_task", path_task_id: task.id, resource_id: quiz.id });
  await page.goto(studio(quiz.id));
  await page.getByRole("button", { name: "进入绑定测验" }).click();
  await expect(page).toHaveURL(/session_id=\d+/);
  const sessionId = new URL(page.url()).searchParams.get("session_id");
  for (let index = 1; index <= 3; index++) {
    await page.getByRole("button", { name: new RegExp(`第 ${index} 题，`) }).click();
    await page.getByRole("group", { name: "答案选项" }).getByRole("button").first().click();
  }
  await page.getByRole("button", { name: "提交练习", exact: true }).click();
  await expect.poll(async () => (await get(`/practice/sessions/${sessionId}`)).status).toBe("completed");
  expect(await get(`/practice/sessions/${sessionId}`)).toMatchObject({ score: 100, source_binding: { path_id: Number(pathId), task_id: Number(task.id) } });
  expect(await get(progressPath)).toMatchObject({ activity_completed: true, assessment_passed: true, mastered: true, mastery_score: 100, next_step: "continue_learning" });
  const repeated = await request.post(`/api/v1/paths/tasks/${task.id}/resources/${quiz.id}/practice`, { headers });
  expect((await repeated.json()).data.id).toBe(sessionId);
  const duplicate = await request.post(`/api/v1/practice/sessions/${sessionId}/answers`, { headers, data: { answers: [{ question_id: "q1", answer_text: "B" }] } });
  expect(duplicate.status()).toBe(409);
  await page.reload();
  await page.goto(studio(quiz.id));
  await expect(page.getByRole("region", { name: "任务证据状态" })).toContainText("已掌握（100%）");
  await expect.poll(async () => (await get(`/learning/next-action?course_id=${course.id}`)).kind, { timeout: 60_000 }).toBe("update_report");
  expect((await get(`/paths/${pathId}`)).path.approval_status).toBe("approved");
});
