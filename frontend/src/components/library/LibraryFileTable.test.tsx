import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { LibraryFileTable } from "./LibraryFileTable";

const baseProps = {
  materials: [],
  courseTitles: new Map<string, string>(),
  compareMode: false,
  selectedMaterialIds: [],
  isLoading: false,
  isError: false,
  onOpenMaterial: vi.fn(),
  onToggleCompare: vi.fn(),
  onRequestDelete: vi.fn()
};

it("资料库真正为空时引导上传第一份资料", () => {
  render(<LibraryFileTable {...baseProps} totalMaterialCount={0} />);

  expect(screen.getByText("还没有资料。使用右上角“上传”添加第一份学习资料。")).toBeInTheDocument();
});

it("有资料但筛选为空时说明筛选条件未命中", () => {
  render(<LibraryFileTable {...baseProps} totalMaterialCount={3} />);

  expect(screen.getByText("没有符合当前搜索或类型筛选的资料。")).toBeInTheDocument();
});
