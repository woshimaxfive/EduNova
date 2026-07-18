import type { CreateTutorResourceJobRequest } from "../../api/tutor";

export function resourceRequestFromPrompt(prompt: string, courseId: number): CreateTutorResourceJobRequest | null {
  const text = prompt.trim();
  if (!/(生成|制作|创建|出).{0,16}(资源|讲义|笔记|思维导图|脑图|题|练习|测验|代码|课件|ppt|动画|视频)/i.test(text)) return null;
  const type = /思维导图|脑图/i.test(text) ? "mindmap" : /题目|练习|测验/i.test(text) ? "quiz" : /代码|编程/i.test(text) ? "code" : /课件|ppt/i.test(text) ? "slide" : /动画/i.test(text) ? "animation" : /视频/i.test(text) ? "video" : "doc";
  const difficulty = /困难|难一点|hard/i.test(text) ? "hard" : /简单|基础|easy/i.test(text) ? "easy" : "medium";
  return { course_id: courseId, resource_types: [type], learning_goal: text.slice(0, 500), difficulty };
}

export function isResourceGenerationPrompt(prompt: string) {
  return resourceRequestFromPrompt(prompt, 1) !== null;
}
