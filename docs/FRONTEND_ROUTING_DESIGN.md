# EduNova 前端路由与入口体验设计

日期：2026-07-01

## 1. 文档目的

本文档补齐 Phase 3A 前必须明确的前端入口、路由、登录注册、首次进入、Demo 体验和路由保护设计。

它和 [UI_UX_DESIGN.md](UI_UX_DESIGN.md) 的关系：

- `UI_UX_DESIGN.md` 定义登录后的 AI 学习空间长什么样。
- 本文档定义用户如何进入这个学习空间，以及前端工程应该有哪些路由和页面边界。

Phase 3A 开发前必须遵守本文档，避免登录页、注册页、首次进入和 Demo 入口在实现时临时拼凑。

## 2. 设计目标

登录注册页不是普通表单页，也不是营销落地页。它承担三个任务：

1. 让学生快速进入学习。
2. 让评委第一眼感受到 EduNova 是一个高级 AI 学习空间。
3. 让 Demo Mode 可以稳定进入主演示链路。

入口体验必须做到：

- 美观但克制。
- 学习感强于广告感。
- 登录、注册、Demo 三条路径清晰。
- 未登录保护明确。
- 首次进入有轻量引导，不让用户面对空白学习空间。

## 3. 路由总览

第一版前端采用 React Router。路由按公开入口、受保护应用区和兜底页面分组。

### 3.1 公开入口

| 路径 | 页面 | 说明 |
| --- | --- | --- |
| `/` | RootRedirect | 未登录跳 `/login`，已登录跳 `/app` |
| `/login` | LoginPage | 登录、Demo 体验入口 |
| `/register` | RegisterPage | 注册新学生账号 |
| `/demo` | DemoEntryPage | 可选轻量路由，用于一键初始化并进入 Demo |

### 3.2 受保护应用区

| 路径 | 页面 | 说明 |
| --- | --- | --- |
| `/app` | LearningSpacePage | AI 学习空间首页 |
| `/app/library` | LibraryPage | 资料库、课程资料、上传建课入口 |
| `/app/studio` | StudioPage | 生成和管理学习资源 |
| `/app/profile` | ProfilePage | 对话式画像与画像证据 |
| `/app/tutor` | TutorPage | AI 辅导和苏格拉底追问 |
| `/app/practice` | PracticePage | 练习、批改、错因复盘 |
| `/app/reports` | ReportsPage | 学习报告、掌握度、导出入口 |
| `/app/settings` | SettingsPage | 模型设置、个人设置、数据导出 |

### 3.3 兜底页面

| 路径 | 页面 | 说明 |
| --- | --- | --- |
| `*` | NotFoundPage | 未匹配路由，提供回到学习空间或登录页入口 |

## 4. 路由保护规则

### 4.1 未登录用户

未登录用户允许访问：

- `/`
- `/login`
- `/register`
- `/demo`

未登录用户访问 `/app/*` 时：

```text
记录原目标路径
-> 跳转 `/login`
-> 登录成功后回到原目标路径
```

如果没有原目标路径，登录后进入 `/app`。

### 4.2 已登录用户

已登录用户访问 `/login` 或 `/register` 时：

```text
如果已有基础画像和课程上下文 -> 跳 `/app`
如果缺少画像或课程上下文 -> 跳 `/app` 并显示首次进入引导
```

### 4.3 Token 失效

任一受保护接口返回 401 时：

```text
清理本地登录状态
-> 记录当前路径
-> 跳转 `/login`
-> 显示“登录已过期，请重新进入学习空间”
```

## 5. 登录页设计

### 5.1 页面定位

登录页是产品第一眼，不做传统后台登录页。

视觉表达：

```text
安静的学习空间预览
+ 居中的登录面板
+ 明确 Demo 体验按钮
+ 少量能力提示
```

### 5.2 布局结构

桌面端推荐结构：

```text
全屏柔和背景
  顶部：EduNova 标识和简短定位
  中央：登录表单
  背景或侧后方：学习画布预览、资料源、Studio 输出、证据层的弱化片段
  底部：开源/比赛/隐私提示
```

移动端：

```text
EduNova 标识
登录表单
Demo 体验
注册入口
能力提示压缩为 2-3 条
```

### 5.3 表单字段

登录表单字段：

- 邮箱。
- 密码。
- 记住登录状态。

主要操作：

- 登录。
- Demo 体验。
- 创建账号。

次要操作：

- 忘记密码第一版可不实现，显示“暂未开放”或不展示。

### 5.4 文案基线

标题：

```text
进入你的 AI 学习空间
```

辅助文案：

```text
把课程资料、知识路径、练习评估和 AI 辅导放在同一个学习空间里。
```

Demo 按钮：

```text
体验演示学生
```

错误提示：

```text
邮箱或密码不正确，请检查后重试。
登录已过期，请重新进入学习空间。
Demo 数据初始化失败，请稍后重试或使用普通登录。
```

## 6. 注册页设计

### 6.1 页面定位

注册页不是复杂问卷，只收集创建账号必要信息。学习画像由首次进入引导或对话画像完成。

### 6.2 表单字段

注册字段：

- 昵称。
- 邮箱。
- 密码。
- 确认密码。

可选勾选：

- 我了解上传资料会用于构建个人学习空间。

### 6.3 注册成功后

注册成功后直接登录，并进入首次进入引导：

```text
注册成功
-> 自动写入 token
-> 进入 `/app`
-> 打开首次进入引导
```

如果自动登录失败：

```text
提示注册成功
-> 跳转 `/login`
-> 要求重新登录
```

## 7. 首次进入引导

首次进入引导以轻量 Overlay 或学习空间内的引导面板实现，不做多页强制问卷。

触发条件：

- 当前用户没有学习画像。
- 当前用户没有选定课程。
- 用户第一次进入 Demo 之外的 `/app`。

引导步骤：

```text
1. 选择开始方式
   - 从人工智能导论开始
   - 上传自己的课程资料
   - 先和 EduNova 聊聊我的学习情况

2. 建立初始上下文
   - 如果选择人工智能导论：设置当前课程
   - 如果选择上传资料：跳 `/app/library` 并打开上传入口
   - 如果选择画像对话：跳 `/app/profile`

3. 回到学习空间
   - 展示当前课程焦点
   - 命令栏给出 3 条建议
```

引导必须可以跳过，但跳过后学习空间要显示清晰空状态。

## 8. Demo 入口

Demo 是比赛和试用的关键入口，必须显眼但不喧宾夺主。

推荐流程：

```text
点击“体验演示学生”
-> 调用 `/demo/reset` 或检查 `/demo/status`
-> 使用演示账号登录
-> 进入 `/app`
-> 显示 Demo 标识
```

Demo 入口状态：

| 状态 | 前端表现 |
| --- | --- |
| 初始化中 | 显示“正在准备演示学习空间” |
| 成功 | 进入 `/app` |
| 失败 | 显示可理解错误，提供重试和普通登录 |
| fallback | 在学习空间显示“演示兜底内容”标识 |

Demo 标识要求：

- 不遮挡核心操作。
- 任何 fallback 内容都不能伪装成实时模型结果。
- 截图和演示视频中能看出 Demo 数据是演示数据。

## 9. 应用区导航

应用区不是固定左侧后台菜单。导航由顶部轻导航和命令栏共同承担。

顶部导航：

```text
EduNova
课程切换
学习空间
资料库
Studio
报告
搜索
上传
用户菜单
```

不把所有能力都平铺成菜单。练习、画像、AI 辅导等能力可以通过：

- 命令栏建议。
- 学习画布节点。
- Studio 输出。
- 报告页入口。
- 用户菜单或二级入口。

Phase 3A 为了工程清晰，可以先有对应路由，但视觉上不做复杂后台导航。

## 10. 页面职责边界

| 页面 | 第一版职责 | 不做什么 |
| --- | --- | --- |
| LoginPage | 登录、Demo 入口、进入注册 | 不做营销长页 |
| RegisterPage | 创建学生账号 | 不做学习画像问卷 |
| LearningSpacePage | 首屏学习画布、命令栏、Studio 摘要、证据入口 | 不承载所有详情表格 |
| LibraryPage | 资料源、课程资料、上传建课、解析进度 | 不做后台文件管理器 |
| StudioPage | 资源生成和资源详情 | 不做卡片墙首页 |
| ProfilePage | 对话画像、画像证据、画像事件 | 不做复杂用户中心 |
| TutorPage | 沉浸式 AI 辅导和引用问答 | 不替代学习空间主入口 |
| PracticePage | 练习、批改、错因复盘 | 不做完整考试系统 |
| ReportsPage | 掌握度、学习报告、导出 | 不做运营报表 |
| SettingsPage | 模型 Key、个人资料、导出设置 | 不做复杂管理员后台 |

## 11. 空状态与错误状态

### 11.1 登录页

- 表单为空：显示普通输入提示。
- 账号不存在或密码错误：统一错误，不暴露账号是否存在。
- 网络失败：提示稍后重试。
- 后端不可用：提示本地服务未启动或网络异常。

### 11.2 注册页

- 邮箱已注册：提示去登录。
- 密码不一致：前端即时提示。
- 密码太短：前端提示，后端仍需校验。
- 注册失败：保留表单输入，允许重试。

### 11.3 学习空间

无课程时：

```text
从人工智能导论开始
上传课程资料
先建立学习画像
```

无画像时：

```text
和 EduNova 聊 2 分钟，生成你的学习画像。
```

无资源时：

```text
选择一个知识点，让 Studio 生成讲解、练习或复盘报告。
```

## 12. 技术实现约束

Phase 3A 实现时遵守：

- React Router 使用集中路由配置。
- `ProtectedRoute` 统一处理登录保护。
- `PublicOnlyRoute` 统一处理已登录用户访问登录/注册页。
- API client 统一处理 401。
- 登录态使用 Zustand。
- 路由常量集中定义，避免字符串散落。
- 页面组件只关心渲染，不直接拼接 token。
- Demo 入口使用独立 service，避免登录页堆业务逻辑。

建议文件：

```text
frontend/src/app/routes.tsx
frontend/src/app/routePaths.ts
frontend/src/app/ProtectedRoute.tsx
frontend/src/app/PublicOnlyRoute.tsx
frontend/src/pages/LoginPage.tsx
frontend/src/pages/RegisterPage.tsx
frontend/src/pages/LearningSpacePage.tsx
frontend/src/pages/DemoEntryPage.tsx
frontend/src/features/auth/authStore.ts
frontend/src/features/auth/authApi.ts
frontend/src/features/demo/demoApi.ts
frontend/src/features/onboarding/FirstRunGuide.tsx
```

## 13. 测试验收

Phase 3A 前端入口验收：

1. `/` 根据登录态正确跳转。
2. `/login`、`/register` 可打开并符合入口设计。
3. 未登录访问 `/app` 或 `/app/*` 会跳转登录页。
4. 登录成功后回到原目标路径，或进入 `/app`。
5. 注册成功后进入首次进入引导。
6. Demo 入口有初始化中、成功、失败三类状态。
7. Token 失效后清理登录态并跳回登录页。
8. 404 页面能回到登录页或学习空间。
9. 1366x768、1440x900、390px 宽度下登录页不溢出。
10. 文案不出现 AI 味过重的营销套话。

## 14. 与后续阶段关系

Phase 3A：

- 实现路由、登录注册静态/半静态页面、学习空间壳子、Demo 入口占位和首次进入引导占位。

Phase 4：

- 接入真实注册、登录、`/auth/me`、路由保护和登录态恢复。

Phase 5 以后：

- 上传建课、RAG、Studio、AI 辅导、练习评估逐步接入对应路由和学习空间入口。

如果路由、入口或首次进入流程变化，必须同步更新：

- `docs/UI_UX_DESIGN.md`
- `docs/ARCHITECTURE.md`
- `docs/REQUIREMENTS.md`
- `docs/TEST_PLAN.md`
- `docs/PROJECT_BOARD.md`
- `docs/superpowers/plans/2026-07-01-edunova-mvp-implementation.md`
- `docs/superpowers/plans/2026-07-01-edunova-mvp-implementation-中文阅读版.md`

## 15. 当前实现状态

Phase 3 当前已在 `frontend/` 中实现：

- `/` 根据本地登录态跳转 `/login` 或 `/app`。
- `/login`、`/register`、`/demo` 已有页面。
- `/app/*` 使用 `ProtectedRoute` 保护，未登录会回到 `/login`。
- 已登录用户访问 `/login` 或 `/register` 会通过 `PublicOnlyRoute` 回到 `/app`。
- `authStore` 使用 Zustand 保存本地预览 token 和用户信息。
- API client 默认基础路径为 `/api/v1`，会自动附加 Bearer token；接口返回 401 时清理登录态，如果用户位于 `/app/*`，会返回 `/login`。
- `frontend/src/api/` 已按业务域拆分 auth、courses、materials、profiles、resources、paths、tutor、practice、reports、demo、settings 等合同模块，路径与 `docs/API.md` 对齐。
- 登录、注册和 Demo 当前只用于前端预览，未接真实 `/auth/register`、`/auth/login`、`/auth/me` 和 `/demo/reset`。
- `FirstRunGuide` 已作为学习空间中的轻量引导占位，真实触发条件需要 Phase 4 根据画像和课程上下文接入。
- 学习空间已展示上传建课状态轨道和空状态、加载状态、错误恢复、低依据提示、Demo fallback 标记。

当前前端测试覆盖：

- 未登录访问 `/app/studio` 会跳到登录入口。
- 已登录访问 `/login` 会回到学习空间。
- 登录态会写入本地存储。
- 学习空间包含学习画布、Studio、证据层和 AI 命令栏。
- 前端 API 合同模块默认使用 `/api/v1`，关键路径常量有 Vitest 覆盖。
- 上传建课工作流状态和学习空间状态面板有 Vitest 覆盖。
