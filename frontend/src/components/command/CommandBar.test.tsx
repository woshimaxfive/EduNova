import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CommandBar } from "./CommandBar";

describe("CommandBar", () => {
  it("records commands without showing global feedback bars", async () => {
    const user = userEvent.setup();

    render(<CommandBar />);

    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "根据反向传播给我出 10 道期末题" }));
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByText("最近指令：根据反向传播给我出 10 道期末题")).toBeInTheDocument();
  });
});
