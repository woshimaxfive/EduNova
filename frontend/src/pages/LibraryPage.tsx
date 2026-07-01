import { FileArrowUp, SealCheck } from "@phosphor-icons/react";

import { PageFrame } from "./PageFrame";

export function LibraryPage() {
  return (
    <PageFrame kicker="资料库" title="课程资料进入学习空间" description="内置课程、上传资料、解析阶段和引用覆盖度都在这里汇合。">
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
