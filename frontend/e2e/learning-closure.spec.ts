import { expect, test, type Page } from "@playwright/test";

async function createAndSubmitWrongPractice(page: Page) {
  await page.goto("/app/practice");
  await expect(page.getByRole("button", { name: "生成练习" })).toBeEnabled();
  await page.getByLabel("题量").selectOption("3");
  await page.getByRole("button", { name: "生成练习" }).click();

  const answerBoxes = page.getByRole("textbox", { name: /作答区/ });
  await expect(answerBoxes).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) {
    await answerBoxes.nth(index).fill("这是一次故意提交的错误答案");
  }

  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.getByText("练习已完成")).toBeVisible();
  await expect(page.getByText("错因诊断").first()).toBeVisible();
  await expect(page.getByText("已有路径已按本次练习重排")).toBeVisible();
}

test("rules-only Docker environment closes the learning loop with real traces", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("昵称").fill("Phase 14 验收账号");
  await page.getByLabel("邮箱").fill("phase14-e2e@edunova.local");
  await page.getByLabel("密码", { exact: true }).fill("Phase14Test2026");
  await page.getByLabel("确认密码").fill("Phase14Test2026");
  await expect(page.getByRole("radio", { name: /带一个示例课程开始/ })).toBeChecked();
  await page.getByRole("button", { name: "创建并进入" }).click();
  await expect(page).toHaveURL(/\/app$/);

  await page.goto("/app/path");
  await expect(page.getByRole("button", { name: "生成学习路径" })).toBeEnabled();
  await page.getByRole("button", { name: "生成学习路径" }).click();
  await expect(page.getByRole("button", { name: "查看 PathPlanningGraph" })).toBeVisible();
  await page.getByRole("button", { name: "查看 PathPlanningGraph" }).click();
  await expect(page.getByText("deterministic_rank")).toBeVisible();

  await createAndSubmitWrongPractice(page);
  await page.getByRole("button", { name: "查看 AssessmentGraph" }).click();
  await expect(page.getByText("deterministic_score")).toBeVisible();

  await page.goto("/app/path");
  await expect(page.getByText(/由练习结果更新 · 保留 \d+ 个既有任务/)).toBeVisible();
  await expect(page.getByText(/规则底稿 · 规则审核/)).toBeVisible();

  await createAndSubmitWrongPractice(page);

  await page.goto("/app/reports");
  await expect(page.getByRole("button", { name: "生成学习报告" })).toBeEnabled();
  await page.getByRole("button", { name: "生成学习报告" }).click();
  await expect(page.getByRole("button", { name: "查看 ReportGraph" })).toBeVisible();
  await expect(page.getByText("2 次练习")).toBeVisible();
  await page.getByRole("button", { name: "查看 ReportGraph" }).click();
  await expect(page.getByText("aggregate_evidence")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["/app/path", "/app/practice", "/app/reports"]) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${route} should not overflow horizontally at 390px`).toBeLessThanOrEqual(1);
  }
});
