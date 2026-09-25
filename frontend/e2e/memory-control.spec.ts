import { expect, test } from "@playwright/test";

test("confirmed memory can be corrected, exported, paused and permanently removed", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("昵称").fill("记忆管理测试");
  await page.getByLabel("账号").fill(`memory_e2e_${Date.now()}`);
  await page.getByLabel("密码", { exact: true }).fill("MemoryControl2026");
  await page.getByRole("textbox", { name: "确认密码 显示确认密码" }).fill("MemoryControl2026");
  await page.getByRole("button", { name: "创建并进入" }).click();
  await expect(page).toHaveURL(/\/app$/);
  await page.goto("/app/settings?section=privacy");
  const panel = page.getByRole("region", { name: "记忆管理" });
  // Check computed browser styles: jsdom cannot detect missing inherited Portal tokens.
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 960 });
    for (const label of ["清除派生索引", "清除全部记忆"]) {
      await panel.getByRole("button", { name: label, exact: true }).click();
      const dialog = page.getByRole("alertdialog", { name: `${label}？`, exact: true });
      await expect(dialog).toBeVisible();
      await expect(dialog.locator("section")).toHaveCSS("background-color", "rgb(250, 252, 251)");
      await expect(dialog).toHaveCSS("position", "fixed");
      await expect(dialog).toHaveCSS("background-color", "rgba(18, 28, 32, 0.36)");
      const box = await dialog.locator("section").boundingBox();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width);
      const cancel = dialog.getByRole("button", { name: "取消" });
      await expect(cancel).toBeFocused();
      await page.keyboard.press("Shift+Tab");
      await expect(dialog.getByRole("button", { name: "确认操作" })).toBeFocused();
      await page.screenshot({ path: `test-results/memory-confirm-${label === "清除派生索引" ? "indexes" : "all"}-${width}.png` });
      await cancel.click();
      await expect(dialog).not.toBeVisible();
    }
  }
  await page.setViewportSize({ width: 1440, height: 960 });
  await panel.getByLabel("长期学习信息", { exact: true }).fill("先举例再解释概念");
  await expect(panel.getByRole("button", { name: "保存长期信息" })).toBeDisabled();
  await panel.getByLabel("我确认这条信息，并希望在后续对话中使用").check();
  await panel.getByRole("button", { name: "保存长期信息" }).click();
  await expect(panel.getByText("先举例再解释概念", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "纠正", exact: true }).click();
  await panel.getByLabel("纠正内容").fill("先给一个队列例子，再解释概念");
  await panel.getByRole("button", { name: "确认保存纠正" }).click();
  await expect(panel.getByText("先给一个队列例子，再解释概念", { exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await panel.getByRole("button", { name: "导出记忆" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("edunova-memory.json");
  const stream = await download.createReadStream();
  const chunks = []; for await (const chunk of stream!) chunks.push(chunk);
  const exported = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  expect(exported.items).toHaveLength(1);
  expect(exported.items[0].content).toBe("先给一个队列例子，再解释概念");
  await panel.getByLabel("跨会话记忆", { exact: true }).click();
  await expect(panel.getByLabel("跨会话记忆", { exact: true })).not.toBeChecked();
  await page.reload();
  await panel.getByLabel("查看记忆层").selectOption("fact");
  await expect(panel.getByLabel("跨会话记忆", { exact: true })).not.toBeChecked();
  await expect(panel.getByText("先给一个队列例子，再解释概念", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();
  await page.screenshot({ path: "test-results/memory-mobile.png", fullPage: true });
  await panel.getByRole("button", { name: "永久删除", exact: true }).click();
  await expect(page.getByRole("alertdialog").locator("section")).toHaveCSS("background-color", "rgb(250, 252, 251)");
  await page.getByRole("alertdialog").getByRole("button", { name: "确认操作" }).click();
  await expect(panel.getByText("暂无这一层的记忆。")).toBeVisible();
  await page.reload();
  await panel.getByLabel("查看记忆层").selectOption("fact");
  await expect(panel.getByText("暂无这一层的记忆。")).toBeVisible();
});
