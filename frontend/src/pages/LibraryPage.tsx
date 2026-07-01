import { BookOpen, FileArrowUp, FolderOpen, LinkSimple, SealCheck, Sparkle } from "@phosphor-icons/react";

import { WorkflowStatusRail } from "../components/states/WorkflowStatusRail";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { buildMaterialLifecycle } from "../features/workspace/workflowState";
import { PageFrame } from "./PageFrame";

export function LibraryPage() {
  const materialLifecycle = buildMaterialLifecycle("chunking", 60);

  return (
    <PageFrame kicker="资料库" title="课程资料进入学习空间" description="内置课程、上传资料、解析阶段和引用覆盖度都在这里汇合。">
      <WorkflowStatusRail
        title="上传资料后自动扩展成课程"
        description="资料从文件进入系统，到知识点、索引和初始路径生成，学生能看到每一步。"
        stages={materialLifecycle}
      />

      <div className="student-workspace library-workspace">
        <section className="student-panel library-list-panel" role="region" aria-label="资料列表">
          <div className="student-panel-heading">
            <div>
              <p className="section-kicker">Materials</p>
              <h2>可被引用的资料</h2>
            </div>
            <span className="panel-count">{demoLearningSpace.materials.length} 份</span>
          </div>
          <div className="material-source-list">
            {demoLearningSpace.materials.map((material) => (
              <article className="material-source-row" key={material.id}>
                <span className="material-source-icon" aria-hidden="true">
                  {material.type === "builtin" ? (
                    <BookOpen size={20} weight="duotone" />
                  ) : (
                    <FolderOpen size={20} weight="duotone" />
                  )}
                </span>
                <div>
                  <strong>{material.title}</strong>
                  <small>
                    {material.coverageLabel} · {material.parseStatus === "completed" ? "已解析" : "解析中"}
                  </small>
                </div>
                <button type="button">查看引用</button>
              </article>
            ))}
          </div>
        </section>

        <aside className="library-side-stack">
          <section className="student-panel library-actions" role="region" aria-label="资料操作">
            <div className="student-panel-heading compact">
              <div>
                <p className="section-kicker">Actions</p>
                <h2>把资料变成学习入口</h2>
              </div>
            </div>
            <div className="action-stack">
              <button className="primary-action" type="button">
                <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
                <span>上传资料</span>
              </button>
              <button type="button">
                <Sparkle size={18} weight="duotone" aria-hidden="true" />
                <span>生成课程</span>
              </button>
              <button type="button">
                <LinkSimple size={18} weight="duotone" aria-hidden="true" />
                <span>作为对话参考</span>
              </button>
            </div>
          </section>

          <section className="student-panel course-ownership-panel" role="region" aria-label="课程归属">
            <div className="student-panel-heading compact">
              <div>
                <p className="section-kicker">Courses</p>
                <h2>资料可以独立存在，也可以加入课程</h2>
              </div>
            </div>
            <ul className="ownership-list">
              <li>
                <strong>人工智能导论</strong>
                <span>2 份资料已加入</span>
              </li>
              <li>
                <strong>主页独立对话</strong>
                <span>可临时引用，不抢占课程空间</span>
              </li>
            </ul>
          </section>
        </aside>
      </div>

      <div className="process-lane" aria-label="资料解析流程">
        {["上传", "解析", "抽取知识点", "写入向量索引", "进入学习画布"].map((step, index) => (
          <article key={step} className="process-step">
            {index === 0 ? <FileArrowUp size={20} weight="duotone" /> : <SealCheck size={20} weight="duotone" />}
            <strong>{step}</strong>
          </article>
        ))}
      </div>
    </PageFrame>
  );
}
