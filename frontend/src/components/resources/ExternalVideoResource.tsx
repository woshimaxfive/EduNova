import { ArrowSquareOut } from "@phosphor-icons/react";

import { type ResourceExternalVideoArtifact } from "../../api/resources";

const YOUTUBE_ID = /^[A-Za-z0-9_-]{6,20}$/;
const BILIBILI_ID = /^BV[A-Za-z0-9]{10}$/i;

function safeVideoUrls(artifact: ResourceExternalVideoArtifact) {
  if (artifact.platform === "youtube" && YOUTUBE_ID.test(artifact.video_id)) {
    return {
      embed: `https://www.youtube.com/embed/${artifact.video_id}`,
      watch: `https://www.youtube.com/watch?v=${artifact.video_id}`
    };
  }
  if (artifact.platform === "bilibili" && BILIBILI_ID.test(artifact.video_id)) {
    return {
      embed: `https://player.bilibili.com/player.html?bvid=${artifact.video_id}`,
      watch: `https://www.bilibili.com/video/${artifact.video_id}`
    };
  }
  return null;
}

export function ExternalVideoResource({ artifact }: { artifact: ResourceExternalVideoArtifact }) {
  const urls = safeVideoUrls(artifact);
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
        />
      </div>
      <div className="external-video-copy">
        <strong>{artifact.title}</strong>
        <p>{artifact.fit_reason}</p>
        <span>联网精选 · 外部补充，不作为教材或评分证据</span>
        <a href={urls.watch} target="_blank" rel="noreferrer noopener">
          无法播放时前往原平台 <ArrowSquareOut size={15} aria-hidden="true" />
        </a>
      </div>
    </section>
  );
}
