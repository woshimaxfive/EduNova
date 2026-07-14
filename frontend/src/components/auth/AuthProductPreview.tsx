import {
  ArrowRight,
  BookOpen,
  ChatCircleDots,
  FileText,
  FolderOpen,
  Path,
  Sparkle,
  Student,
  UserCircle
} from "@phosphor-icons/react";

const workspaceNavigation = [
  { label: "学习空间", icon: ChatCircleDots, active: true },
  { label: "资料库", icon: FolderOpen, active: false },
  { label: "资源工坊", icon: Sparkle, active: false },
  { label: "学习画像", icon: UserCircle, active: false }
] as const;

const learningEntries = [
  {
    title: "整理自己的学习资料",
    description: "上传文档后建立可引用的课程内容",
    icon: FileText
  },
  {
    title: "进入课程学习",
    description: "阅读知识点，并围绕真实来源继续提问",
    icon: BookOpen
  },
  {
    title: "通过练习持续更新",
    description: "让弱点、路径和报告随学习结果变化",
    icon: Path
  }
] as const;

export function AuthProductPreview() {
  return (
    <div className="auth-product-preview" aria-label="EduNova 学习工作区缩略图">
      <aside className="auth-preview-sidebar" aria-hidden="true">
        <div className="auth-preview-mark">
          <Student size={18} weight="duotone" />
          <strong>EduNova</strong>
        </div>
        <nav className="auth-preview-navigation">
          {workspaceNavigation.map((item) => {
            const Icon = item.icon;
            return (
              <span key={item.label} className={item.active ? "active" : undefined}>
                <Icon size={17} weight={item.active ? "fill" : "regular"} />
                {item.label}
              </span>
            );
          })}
        </nav>
        <span className="auth-preview-account">
          <UserCircle size={18} />
          个人学习空间
        </span>
      </aside>

      <div className="auth-preview-workspace">
        <header className="auth-preview-toolbar">
          <div>
            <span>学习空间</span>
            <strong>从你的内容开始</strong>
          </div>
          <span className="auth-preview-status">学习数据仅自己可见</span>
        </header>

        <div className="auth-preview-composer" aria-hidden="true">
          <span>提问，或使用资料创建课程</span>
          <span className="auth-preview-send"><ArrowRight size={17} /></span>
        </div>

        <section className="auth-preview-content" aria-label="学习入口预览">
          <header>
            <span>开始学习</span>
            <small>按自己的内容和进度展开</small>
          </header>
          <div className="auth-preview-entry-list">
            {learningEntries.map((entry) => {
              const Icon = entry.icon;
              return (
                <article key={entry.title}>
                  <span className="auth-preview-entry-icon" aria-hidden="true">
                    <Icon size={19} weight="duotone" />
                  </span>
                  <div>
                    <strong>{entry.title}</strong>
                    <p>{entry.description}</p>
                  </div>
                  <ArrowRight size={16} aria-hidden="true" />
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
