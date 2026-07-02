import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PATHS } from "../app/routePaths";
import { CourseSpacePage } from "./CourseSpacePage";
import { LearningSpacePage } from "./LearningSpacePage";
import { LibraryPage } from "./LibraryPage";
import { PracticePage } from "./PracticePage";
import { SettingsPage } from "./SettingsPage";
import { TutorPage } from "./TutorPage";

function renderPage(page: ReactNode) {
  render(<MemoryRouter>{page}</MemoryRouter>);
}

describe("student interaction affordances", () => {
  it("turns the home composer buttons into visible demo-state feedback", async () => {
    const user = userEvent.setup();

    renderPage(<LearningSpacePage />);

    const uploadedFile = new File(["demo"], "数据结构期末题.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("上传资料文件"), uploadedFile);

    expect(screen.getByRole("status")).toHaveTextContent("数据结构期末题.pdf 已上传到资料库");

    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    expect(screen.getByRole("dialog", { name: "资料库" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /数据结构期末题.pdf/ })).toBeInTheDocument();

    const material = screen.getByRole("button", { name: /神经网络课堂讲义/ });

    expect(material).toHaveAttribute("aria-pressed", "false");

    await user.click(material);

    expect(material).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("已选择 1 份资料");

    await user.click(screen.getByRole("button", { name: "关闭资料库" }));
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByRole("status")).toHaveTextContent("先输入一个学习问题");

    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "监督学习怎么复习？");
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.click(screen.getByRole("button", { name: "深度思考" }));
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByRole("button", { name: "联网搜索" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "深度思考" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("已生成回答");
  });

  it("opens course answer detail panels instead of leaving action buttons inert", async () => {
    const user = userEvent.setup();

    renderPage(<CourseSpacePage />);

    await user.click(screen.getByRole("button", { name: "学习路径" }));

    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("建议路径");

    await user.click(screen.getByRole("button", { name: "Agent 过程" }));

    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("RetrieverAgent");

    await user.click(screen.getByRole("button", { name: "监督学习，当前焦点" }));

    expect(screen.getByRole("region", { name: "当前知识点详情" })).toHaveTextContent("监督学习");
  });

  it("keeps tutoring practice and reports as course-context actions", () => {
    renderPage(<CourseSpacePage />);

    const courseActions = screen.getByRole("navigation", { name: "课程行动入口" });
    const expectedActions = [
      ["进入 AI 辅导", PATHS.tutor],
      ["开始练习", PATHS.practice],
      ["查看学习报告", PATHS.reports]
    ] as const;

    for (const [label, path] of expectedActions) {
      expect(within(courseActions).getByRole("link", { name: label })).toHaveAttribute("href", path);
    }
  });

  it("uses the shared sidebar history to switch the course thread", async () => {
    const user = userEvent.setup();

    renderPage(<CourseSpacePage />);

    const historyRail = screen.getByRole("region", { name: "历史对话" });
    const courseThreadList = screen.getByLabelText("课程内历史对话");

    await user.click(within(historyRail).getByRole("button", { name: /解释泛化能力和过拟合的区别/ }));

    expect(within(courseThreadList).getByRole("button", { name: "解释泛化能力和过拟合的区别" })).toHaveAttribute("aria-pressed", "true");
  });

  it("switches tutor modes and provides feedback for tutor actions", async () => {
    const user = userEvent.setup();

    renderPage(<TutorPage />);

    await user.click(screen.getByRole("button", { name: "苏格拉底追问" }));

    expect(screen.getByRole("button", { name: "苏格拉底追问" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("当前模式：苏格拉底追问")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "深度思考" }));

    expect(screen.getByRole("status")).toHaveTextContent("深度思考已开启");
  });

  it("validates and acknowledges practice submissions", async () => {
    const user = userEvent.setup();

    renderPage(<PracticePage />);

    await user.click(screen.getByRole("button", { name: "提交答案" }));

    expect(screen.getByRole("status")).toHaveTextContent("先写下你的推导思路");

    await user.type(screen.getByRole("textbox", { name: "作答区" }), "需要把局部梯度沿计算图传回参数。");
    await user.click(screen.getByRole("button", { name: "提交答案" }));

    expect(screen.getByRole("status")).toHaveTextContent("已提交答案");
  });

  it("shows feedback for library and settings actions that await real APIs", async () => {
    const user = userEvent.setup();

    renderPage(<LibraryPage />);

    const uploadedFile = new File(["demo"], "课堂截图.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("上传资料文件"), uploadedFile);

    expect(screen.getByRole("status")).toHaveTextContent("课堂截图.png 已上传到资料库");
    expect(screen.getByRole("button", { name: /课堂截图.png/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "图片" }));

    expect(screen.getByRole("button", { name: "图片" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /课堂截图.png/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /AI 导论讲义/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "全部" }));
    await user.click(screen.getByRole("button", { name: /AI 导论讲义/ }));

    expect(screen.getByRole("region", { name: "资料动作反馈" })).toHaveTextContent("AI 导论讲义");

    await user.click(screen.getByRole("button", { name: "从资料生成课程" }));

    const courseDialog = screen.getByRole("dialog", { name: "从资料生成课程" });
    expect(courseDialog).toBeInTheDocument();
    const courseMaterial = within(courseDialog).getByRole("button", { name: /AI 导论讲义/ });

    expect(courseMaterial).toHaveAttribute("aria-pressed", "true");

    await user.click(courseMaterial);

    expect(courseMaterial).toHaveAttribute("aria-pressed", "false");

    renderPage(<SettingsPage />);

    await user.click(screen.getByRole("button", { name: "保存设置" }));

    const settingsRegion = screen.getByRole("region", { name: "账号设置" });
    expect(within(settingsRegion).getByRole("status")).toHaveTextContent("设置已保存");
  });
});
