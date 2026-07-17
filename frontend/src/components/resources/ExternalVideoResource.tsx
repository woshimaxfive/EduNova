import { ArrowSquareOut } from "@phosphor-icons/react";
import { useState } from "react";

import { type ResourceExternalVideoArtifact } from "../../api/resources";
import { safeVideoUrls } from "./videoUrls";

export function ExternalVideoResource({ artifact }: { artifact: ResourceExternalVideoArtifact }) {
  const urls = safeVideoUrls(artifact);
  const [embedStatus, setEmbedStatus] = useState<ResourceExternalVideoArtifact["embed_status"]>(artifact.embed_status);
  if (!urls) {
    return <p className="form-error">视频来源未通过安全校验，已停止嵌入。</p>;
  }
  return (
    <section className="external-video-resource" aria-label="外部教学视频">
      <div className="external-video-frame">
        <iframe
          src={urls.embed}
          title={artifact.title}
          loading="lazy"
          allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
          sandbox="allow-scripts allow-same-origin allow-presentation"
          onLoad={() => setEmbedStatus("available")}
          onError={() => setEmbedStatus("unavailable")}
        />
      </div>
      <div className="external-video-copy">
        <strong>{artifact.title}</strong>
        <p>{artifact.fit_reason}</p>
        <span>
          {artifact.match_level === "related" ? "相关补充" : "知识点匹配"} · 联网精选 · {artifact.access_scope === "external_fallback" || artifact.platform === "youtube" ? "境外补充" : "国内平台"} · 外部补充，不作为教材或评分证据 ·
          {embedStatus === "available" ? " 播放器已载入" : embedStatus === "unavailable" ? " 播放器不可用" : " 正在确认播放器"}
        </span>
        <a href={urls.watch} target="_blank" rel="noreferrer noopener">
          无法播放时前往原平台 <ArrowSquareOut size={15} aria-hidden="true" />
        </a>
      </div>
    </section>
  );
}
