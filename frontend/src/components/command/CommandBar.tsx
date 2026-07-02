import { FileArrowUp, Sparkle } from "@phosphor-icons/react";
import { type KeyboardEvent, useState } from "react";

import { ActionNotice } from "../feedback/ActionNotice";
import { useActionNotice } from "../feedback/useActionNotice";

const suggestions = [
  "根据反向传播给我出 10 道期末题",
  "解释我为什么链式法则总错",
  "把今天的学习整理成复盘报告"
];

export function CommandBar() {
  const [value, setValue] = useState("");
  const [sentPrompt, setSentPrompt] = useState("");
  const { notice, showNotice } = useActionNotice();

  function sendCommand() {
    const prompt = value.trim();

    if (!prompt) {
      showNotice("先输入学习指令。", "warning");
      return;
    }

    setSentPrompt(prompt);
    setValue("");
    showNotice("已记录学习指令，等待 AI 服务接入。", "success");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendCommand();
    }
  }

  return (
    <section className="command-zone" aria-label="AI 命令区">
      <div className="suggestion-row" aria-label="快捷建议">
        {suggestions.map((suggestion) => (
          <button key={suggestion} type="button" onClick={() => setValue(suggestion)}>
            {suggestion}
          </button>
        ))}
      </div>
      <div className="command-bar">
        <button className="icon-button" type="button" aria-label="添加资料" onClick={() => showNotice("添加资料会在资料库上传接入后开放。")}>
          <FileArrowUp size={20} />
        </button>
        <textarea
          aria-label="AI 命令栏"
          value={value}
          rows={1}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="上传资料、生成练习、追问知识点或安排复习计划"
        />
        <button className="send-button" type="button" onClick={sendCommand}>
          <Sparkle size={18} weight="fill" aria-hidden="true" />
          <span>发送</span>
        </button>
      </div>
      <ActionNotice notice={notice} />
      {sentPrompt ? <p className="command-result">最近指令：{sentPrompt}</p> : null}
    </section>
  );
}
