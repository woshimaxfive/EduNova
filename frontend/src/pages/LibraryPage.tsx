import { FileArrowUp, SealCheck } from "@phosphor-icons/react";

import { WorkflowStatusRail } from "../components/states/WorkflowStatusRail";
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
      <div className="process-lane">
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
