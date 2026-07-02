import { ChatCircleText, GraduationCap, MagnifyingGlass, Microphone, ShieldCheck, Sparkle } from "@phosphor-icons/react";
import { useState } from "react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { PageFrame } from "./PageFrame";

const tutorModes = ["直接解释", "苏格拉底追问", "考前冲刺"] as const;

type TutorMode = (typeof tutorModes)[number];

export function TutorPage() {
  const [activeMode, setActiveMode] = useState<TutorMode>("直接解释");
  const { notice, showNotice } = useActionNotice();

  return (
    <PageFrame title="AI 辅导" description="基于课程资料继续追问。">
      <div className="student-workspace tutor-workspace">
        <section className="student-panel tutor-dialog" role="region" aria-label="AI 辅导对话">
          <div className="student-panel-heading">
            <div>
              <h2>继续追问</h2>
            </div>
          </div>
          <div className="tutor-shell">
            <div className="message user">为什么反向传播需要链式法则？</div>
            <div className="message assistant">
              <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
              <span>因为每一层参数对最终损失的影响都要沿计算图逐层传回。先把复合函数拆成局部梯度，再沿路径相乘。</span>
            </div>
            <div className="answer-action-row" aria-label="回答附加信息">
              <button type="button" onClick={() => showNotice("已展开回答来源。")}>
                <ShieldCheck size={17} weight="duotone" aria-hidden="true" />
                <span>查看来源</span>
              </button>
              <button type="button" onClick={() => showNotice("已切换到深度思考演示态。")}>
                <Sparkle size={17} weight="duotone" aria-hidden="true" />
                <span>深度思考</span>
              </button>
              <button type="button" onClick={() => showNotice("语音输入会在录音权限和转写接口接入后开放。")}>
                <Microphone size={17} weight="duotone" aria-hidden="true" />
                <span>语音输入</span>
              </button>
            </div>
            <ActionNotice notice={notice} />
          </div>
          <label className="tutor-composer">
            <span>追问输入</span>
            <textarea rows={3} aria-label="追问输入" placeholder="继续问这道题，或者让 EduNova 换一种方式解释" />
          </label>
        </section>

        <aside className="tutor-side-stack">
          <section className="student-panel tutor-mode-panel" role="region" aria-label="辅导模式">
            <div className="mode-row">
              {tutorModes.map((mode) => (
                <button
                  className={activeMode === mode ? "active" : ""}
                  type="button"
                  key={mode}
                  aria-pressed={activeMode === mode}
                  onClick={() => {
                    setActiveMode(mode);
                    showNotice(`已切换到${mode}模式。`, "success");
                  }}
                >
                  <GraduationCap size={17} weight="duotone" aria-hidden="true" />
                  <span>{mode}</span>
                </button>
              ))}
            </div>
            <p className="mode-current">当前模式：{activeMode}</p>
          </section>

          <section className="student-panel citation-panel" role="region" aria-label="引用来源">
            <div className="student-panel-heading compact">
              <div>
                <h2>回答来源</h2>
              </div>
              <MagnifyingGlass size={18} weight="duotone" aria-hidden="true" />
            </div>
            <div className="citation-list">
              {demoLearningSpace.citations.map((citation) => (
                <article key={citation.id}>
                  <strong>{citation.sourceTitle}</strong>
                  <small>
                    {citation.sectionTitle} · 第 {citation.pageNumber} 页
                  </small>
                </article>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
