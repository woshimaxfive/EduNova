import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

async function confirmUploadedMaterial(page: Page, title: string) {
  const drawer = page.getByRole("dialog", { name: title });
  await expect(drawer).toBeVisible();
  const confirmOutline = drawer.getByRole("button", { name: "确认目录" });
  await expect(confirmOutline).toBeEnabled({ timeout: 90_000 });
  await confirmOutline.click();
  await expect(confirmOutline).toHaveCount(0);
  await drawer.getByRole("button", { name: `关闭${title}` }).click();
  await expect(page.getByText("目录已确认", { exact: true }).first()).toBeVisible();
}

test("rules-only Docker environment fails honestly instead of persisting generated templates", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/register");
  await page.getByLabel("昵称").fill("Phase 38 验收账号");
  await page.getByLabel("账号").fill("phase38_e2e");
  await page.getByLabel("密码", { exact: true }).fill("Phase38Test2026");
  await page.getByRole("textbox", { name: "确认密码 显示确认密码" }).fill("Phase38Test2026");
  await page.getByRole("radio", { name: /数据结构与算法/ }).check();
  await page.getByRole("button", { name: "创建并进入" }).click();
  await expect(page).toHaveURL(/\/app$/);

  await page.goto("/app/path");
  await expect(page.getByRole("button", { name: "一键生成学习路径" })).toBeEnabled();
  await page.getByRole("button", { name: "一键生成学习路径" }).click();
  const generationFailure = page.getByRole("alert").filter({ hasText: /模型|生成|规划/ }).first();
  await expect(generationFailure).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("还没有个性化学习路径")).toBeVisible();
  await expect(page.getByRole("button", { name: "路径详情" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "一键生成学习路径" })).toBeEnabled();

  await page.reload();
  await expect(page.getByText("还没有个性化学习路径")).toBeVisible();
  await expect(page.getByRole("button", { name: "路径详情" })).toBeDisabled();

  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["/app/path", "/app/practice", "/app/reports"]) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${route} should not overflow horizontally at 390px`).toBeLessThanOrEqual(1);
  }
});

test("material comparison remains an independent evidence tool", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/register");
  await page.getByLabel("昵称").fill("Phase 16 验收账号");
  await page.getByLabel("账号").fill("phase16_e2e");
  await page.getByLabel("密码", { exact: true }).fill("Phase16Test2026");
  await page.getByRole("textbox", { name: "确认密码 显示确认密码" }).fill("Phase16Test2026");
  await page.getByRole("button", { name: "创建并进入" }).click();
  await expect(page).toHaveURL(/\/app$/);

  await page.goto("/app/library");
  const uploadInput = page.getByLabel("上传资料文件");
  const notesPath = resolve("e2e/fixtures/phase16-ai-notes.md");
  const examPath = resolve("e2e/fixtures/phase16-exam-guide.md");

  await uploadInput.setInputFiles(notesPath);
  await expect(page.getByText("phase16-ai-notes.md").first()).toBeVisible();
  await confirmUploadedMaterial(page, "phase16-ai-notes.md");
  await uploadInput.setInputFiles(examPath);
  await expect(page.getByText("phase16-exam-guide.md").first()).toBeVisible();
  await confirmUploadedMaterial(page, "phase16-exam-guide.md");

  const generateCourse = page.getByRole("button", { name: "生成课程" }).first();
  await expect(generateCourse).toBeEnabled();
  await generateCourse.click();
  const courseDialog = page.getByRole("dialog", { name: "从资料生成课程" });
  await courseDialog.getByLabel("课程名称").fill("Phase 16 资料对比课");
  await courseDialog.getByRole("button", { name: /phase16-ai-notes\.md/ }).click();
  await courseDialog.getByRole("button", { name: /phase16-exam-guide\.md/ }).click();
  await courseDialog.getByRole("button", { name: "生成课程", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/courses\/\d+$/);

  await page.goto("/app/library");
  await page.getByRole("button", { name: "资料对比" }).click();
  await page.getByRole("button", { name: /phase16-ai-notes\.md/ }).click();
  await page.getByRole("button", { name: /phase16-exam-guide\.md/ }).click();
  const comparisonSetup = page.getByRole("region", { name: "资料对比" });
  await expect(comparisonSetup.getByLabel("对比课程")).toHaveValue(/.+/);
  await comparisonSetup.getByRole("button", { name: "生成资料对比" }).click();
  const comparisonResult = page.getByRole("dialog", { name: "对比结果" });
  await comparisonResult.getByRole("tab", { name: "来源与轨迹" }).click();
  await expect(comparisonResult.getByRole("button", { name: "查看 MaterialComparisonGraph" })).toBeVisible();
  await comparisonResult.getByRole("button", { name: "查看 MaterialComparisonGraph" }).click();
  await expect(page.getByText("deterministic_compare")).toBeVisible();
  await expect(comparisonResult.getByRole("button", { name: "用于期末冲刺" })).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["/app/library", "/app/path"]) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${route} should not overflow horizontally at 390px`).toBeLessThanOrEqual(1);
  }
});
