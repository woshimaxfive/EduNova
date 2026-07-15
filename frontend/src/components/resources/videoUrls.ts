import type { ResourceExternalVideoArtifact } from "../../api/resources";


const YOUTUBE_ID = /^[A-Za-z0-9_-]{6,20}$/;
const BILIBILI_ID = /^BV[A-Za-z0-9]{10}$/i;


export function safeVideoUrls(artifact: ResourceExternalVideoArtifact) {
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
