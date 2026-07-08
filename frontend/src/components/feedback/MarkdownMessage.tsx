import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownMessageProps = {
  content: string;
  className?: string;
};

// AI 回答的 Markdown 渲染：react-markdown 默认不渲染原始 HTML，天然防 XSS
// remark-gfm 补齐表格、任务列表、删除线等 GitHub 扩展语法
// 链接强制新标签打开并加 noreferrer，避免打断学习会话
export function MarkdownMessage({ content, className }: MarkdownMessageProps) {
  return (
    <div className={className ? `markdown-body ${className}` : "markdown-body"}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, href, title }) => (
            <a href={href} title={title} target="_blank" rel="noreferrer">
              {children}
            </a>
          )
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
