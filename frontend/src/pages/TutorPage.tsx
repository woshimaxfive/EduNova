import { ChatCircleText, GraduationCap, MagnifyingGlass, Microphone, ShieldCheck, Sparkle } from "@phosphor-icons/react";

import { demoLearningSpace } from "../data/demoLearningSpace";
import { PageFrame } from "./PageFrame";

export function TutorPage() {
  return (
    <PageFrame kicker="AI 辅导" title="围绕课程资料追问" description="直接解释、苏格拉底追问和考前冲刺会共用同一套引用机制。">
      <div className="student-workspace tutor-workspace">
        <section className="student-panel tutor-dialog" role="region" aria-label="AI 辅导对话">
          <div className="student-panel-heading">
            <div>
              <p className="section-kicker">Tutor</p>
              <h2>像聊天一样追问，像课堂一样留痕</h2>
            </div>
          </div>
          <div className="tutor-shell">
            <div className="message user">为什么反向传播需要链式法则？</div>
            <div className="message assistant">
              <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
              <span>因为每一层参数对最终损失的影响都要沿计算图逐层传回。先把复合函数拆成局部梯度，再沿路径相乘。</span>
            </div>
            <div className="answer-action-row" aria-label="回答附加信息">
              <button type="button">
                <ShieldCheck size={17} weight="duotone" aria-hidden="true" />
                <span>查看来源</span>
              </button>
              <button type="button">
                <Sparkle size={17} weight="duotone" aria-hidden="true" />
                <span>深度思考</span>
              </button>
              <button type="button">
                <Microphone size={17} weight="duotone" aria-hidden="true" />
                <span>语音输入</span>
              </button>
            </div>
          </div>
          <label className="tutor-composer">
            <span>追问输入</span>
            <textarea rows={3} aria-label="追问输入" placeholder="继续问这道题，或者让 EduNova 换一种方式解释" />
          </label>
        </section>

        <aside className="tutor-side-stack">
          <section className="student-panel tutor-mode-panel" role="region" aria-label="辅导模式">
            <div className="mode-row">
              {["直接解释", "苏格拉底追问", "考前冲刺"].map((mode, index) => (
                <button className={index === 0 ? "active" : ""} type="button" key={mode}>
                  <GraduationCap size={17} weight="duotone" aria-hidden="true" />
                  <span>{mode}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="student-panel citation-panel" role="region" aria-label="引用来源">
            <div className="student-panel-heading compact">
              <div>
                <p className="section-kicker">Sources</p>
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
