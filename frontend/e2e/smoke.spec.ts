import { expect, test } from "@playwright/test";

test("demo path: search, evidence, and RAG fallback remain visible", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText(/工业设备检修|检修 AI|设备检修/).first()).toBeVisible();

  await page.getByLabel(/设备型号|型号/).fill("发动机-示例型号 A");
  await page.getByLabel(/故障现象|故障描述|现象/).fill("启动困难 怠速不稳");
  await page.getByRole("button", { name: /检索|搜索/ }).click();

  await expect(page.getByText(/排序分|命中|来源|证据/).first()).toBeVisible();

  const ragButton = page.getByRole("button", { name: /RAG|建议|生成/ }).first();
  await ragButton.click();

  await expect(page.getByText(/引用|citations|本地兜底|provider|模型|排序分/i).first()).toBeVisible();
});
