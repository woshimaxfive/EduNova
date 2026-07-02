# EduNova MVP Implementation Plan

中文阅读版：[2026-07-01-edunova-mvp-implementation-中文阅读版.md](2026-07-01-edunova-mvp-implementation-中文阅读版.md)

测试计划：[../../TEST_PLAN.md](../../TEST_PLAN.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 2026-07-14 前完成 EduNova 可运行第一版：学生注册登录、对话画像、上传资料建课、RAG 引用问答、多智能体生成 5 类资源、学习路径、练习评估、可视化 AI 学习空间、Agent 轨迹、Demo Mode、Docker Compose、核心文档。2026-07-15 到 2026-07-20 完成测试说明、开发说明、部署说明、PPT、演示视频和提交包。
**Architecture:** React + TypeScript 学生 AI 学习空间通过 HTTP/SSE 调用 FastAPI；FastAPI 以 service 层承载课程、画像、建课、RAG、资源、路径、评估等业务；LangGraph 编排 ProfileAgent、DiagnosisAgent、CourseBuilderAgent、RetrieverAgent、ResourceAgent、PathAgent、TutorAgent、AssessmentAgent、ReviewAgent；PostgreSQL + pgvector 保存业务数据、知识切片和向量；Redis 保存任务进度、限流和 Demo 缓存；Nginx 提供部署入口。
**Tech Stack:** Python 3.12.10, FastAPI, Pydantic, SQLAlchemy, Alembic, LangGraph, LangChain, PostgreSQL, pgvector, Redis, JWT, bcrypt, python-pptx, pypdf, python-docx, React, TypeScript, Vite, Tailwind CSS, Radix UI / shadcn/ui 按需组件, Motion, React Flow, ECharts, Mermaid, Markmap, pytest, Vitest, Playwright, Docker Compose, Nginx.
---

## Ground Rules

- [ ] 所有新增文本文件使用 UTF-8 无 BOM；中文直接写入，不使用 `\uXXXX`。
- [ ] 不复制参考项目代码；只借鉴产品结构、功能边界和答辩表达，并在 `docs/OPEN_SOURCE_NOTICE.md` 标注参考项目名称、来源、协议情况。
- [ ] 每天结束必须有可运行版本；若 AI 服务不可用，Demo Mode 使用明确标记的 fallback 数据保证演示不中断。
- [ ] 每个 AI 生成结果必须绑定 `trace_id`、`citation_refs`、`review_status`、`confidence_score` 中的关键字段。
- [ ] 所有用户私有数据绑定 `user_id`；课程内数据绑定 `user_id` 与 `course_id`；主页会话和独立资料库允许先不绑定课程，避免多人部署后数据串用。
- [ ] 第一版只做学生端主线和轻量系统设置；不建设完整教师端、家长端、班级运营后台、支付、真实视频生成、扫描 OCR、移动端。
- [ ] Phase 3 前端必须遵守 `docs/UI_UX_DESIGN.md`：不采用固定左侧后台菜单和卡片堆，首页重定向为 AI 对话主页、贴边可收起历史侧栏、侧栏账号入口、输入区资料库浮层入口、文件上传入口、发送后底部输入区、最近学习轻量列表和课程空间入口；资料库采用文件库式页面，并用浮层承载从资料生成课程。
- [ ] Phase 3 路由与入口必须遵守 `docs/FRONTEND_ROUTING_DESIGN.md`：登录、注册、Demo、首次进入和路由保护先搭稳。
- [ ] 每个阶段提交一次小而清晰的 commit；提交前运行本阶段列出的检查命令。

## Target Repository Structure

```text
EduNova/
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── graph.py
│   │   │   ├── schemas.py
│   │   │   ├── nodes/
│   │   │   └── workers/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── courses.py
│   │   │       ├── materials.py
│   │   │       ├── profiles.py
│   │   │       ├── resources.py
│   │   │       ├── paths.py
│   │   │       ├── tutor.py
│   │   │       ├── practice.py
│   │   │       ├── reports.py
│   │   │       ├── demo.py
│   │   │       └── settings.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   └── sse.py
│   │   ├── models/
│   │   ├── providers/
│   │   ├── rag/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── tasks/
│   │   ├── main.py
│   │   └── seed.py
│   ├── tests/
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── app/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── stores/
│   │   ├── styles/
│   │   ├── types/
│   │   └── visualizations/
│   ├── tests/
│   └── package.json
├── knowledge_base/
│   └── artificial_intelligence_intro/
│       ├── course.json
│       ├── knowledge_points.json
│       ├── seed_questions.json
│       └── materials/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DEPLOYMENT.md
│   ├── DEFENSE_QA.md
│   ├── DEVELOPMENT_REPORT.md
│   ├── TEST_REPORT.md
│   ├── OPEN_SOURCE_NOTICE.md
│   └── superpowers/
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── nginx.conf
├── scripts/
│   ├── dev.ps1
│   ├── test.ps1
│   ├── seed_demo.ps1
│   └── verify_encoding.ps1
├── .env.example
├── docker-compose.yml
├── LICENSE
└── README.md
```

## Phase 0: Repository Baseline

### Task 0.1: Preserve Current Design Evidence

- [ ] Confirm current status:

```powershell
git status --short --untracked-files=all
rg --files
```

- [ ] Add `docs/软件杯A3赛题.txt` to Git if it is the official local copy the user wants versioned.
- [ ] Keep `.superpowers/`, `.agents/`, `.codex/`, virtual environments, Node modules, caches, logs and local uploads ignored.
- [ ] Commit:

```powershell
git add docs/软件杯A3赛题.txt .gitignore .gitattributes docs/superpowers/specs/2026-07-01-edunova-product-design.md docs/superpowers/plans/2026-07-01-edunova-mvp-implementation.md
git commit -m "docs: add EduNova implementation plan"
```

### Task 0.2: Create Project Quality Scripts

- [ ] Create `scripts/verify_encoding.ps1` to fail on UTF-8 BOM, UTF-16 BOM and `\uXXXX` escapes in tracked source/document files.

```powershell
$ErrorActionPreference = "Stop"
$files = git ls-files | Where-Object { $_ -match '\.(py|ts|tsx|js|jsx|json|md|txt|yml|yaml|toml|env|css|html|ps1)$' }
$failed = $false
foreach ($file in $files) {
  $bytes = [System.IO.File]::ReadAllBytes($file)
  if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    Write-Error "UTF-8 BOM found: $file"
    $failed = $true
  }
  if ($bytes.Length -ge 2 -and (($bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) -or ($bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF))) {
    Write-Error "UTF-16 BOM found: $file"
    $failed = $true
  }
  $text = [System.Text.Encoding]::UTF8.GetString($bytes)
  if ($text -match '\\u[0-9a-fA-F]{4}') {
    Write-Error "Unicode escape found: $file"
    $failed = $true
  }
}
if ($failed) { exit 1 }
Write-Host "encoding check passed"
```

- [ ] Create `scripts/test.ps1` to run backend tests, frontend tests, frontend build and encoding check in one command.
- [ ] Create `scripts/dev.ps1` to start Docker services, backend and frontend in separate instructions printed to the console.
- [ ] Verify:

```powershell
.\scripts\verify_encoding.ps1
```

- [ ] Commit:

```powershell
git add scripts
git commit -m "chore: add local verification scripts"
```

## Phase 1: Backend Foundation

### Task 1.1: Scaffold FastAPI Project

- [ ] Create Python environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
```

- [ ] Create `backend/requirements.txt` with these runtime dependencies:

```text
fastapi
uvicorn[standard]
pydantic
pydantic-settings
sqlalchemy
alembic
psycopg[binary]
pgvector
redis
python-jose[cryptography]
passlib[bcrypt]
python-multipart
httpx
langchain
langchain-community
langgraph
pypdf
python-docx
python-pptx
markdown
beautifulsoup4
tiktoken
orjson
tenacity
```

- [ ] Create `backend/requirements-dev.txt`:

```text
-r requirements.txt
pytest
pytest-asyncio
pytest-cov
ruff
mypy
```

- [ ] Install:

```powershell
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

- [ ] Create `backend/app/main.py` exposing `/api/health` and `/api/v1`.
- [ ] Create `backend/app/core/config.py` with `Settings` using `pydantic-settings`; include `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `DEMO_MODE`, `SYSTEM_MODEL_PROVIDER`, `SYSTEM_MODEL_API_KEY`, `SYSTEM_MODEL_BASE_URL`, `SYSTEM_CHAT_MODEL`, `SYSTEM_EMBEDDING_MODEL`.
- [ ] Create `backend/app/core/database.py` with SQLAlchemy engine, session dependency and metadata import hook.
- [ ] Verify:

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/api/health`; expected JSON:

```json
{"status":"ok","service":"edunova-api"}
```

- [ ] Commit:

```powershell
git add backend
git commit -m "feat(backend): scaffold FastAPI foundation"
```

### Task 1.2: Docker Infrastructure

- [ ] Create `.env.example` with safe sample values and no real key.
- [ ] Create `docker-compose.yml` with services `postgres`, `redis`, `backend`, `frontend`, `nginx`.
- [ ] Configure PostgreSQL image to enable pgvector through migration, not through manual database steps.
- [ ] Create `docker/backend.Dockerfile`, `docker/frontend.Dockerfile`, `docker/nginx.conf`.
- [ ] Verify local dependencies first:

```powershell
docker compose config
docker compose up -d postgres redis
docker compose ps
```

- [ ] Commit:

```powershell
git add .env.example docker-compose.yml docker
git commit -m "chore: add Docker Compose infrastructure"
```

## Phase 2: Data Model and Seed Course

### Task 2.1: Implement Core Models and Migration

- [ ] Add Alembic initialization under `backend/alembic`.
- [ ] Create models in `backend/app/models/`:

```text
user.py
course.py
material.py
knowledge.py
profile.py
resource.py
path.py
practice.py
chat.py
agent_log.py
model_setting.py
export.py
```

- [ ] Include these tables and minimum fields:

```text
users: id, email, hashed_password, display_name, role, created_at, updated_at
courses: id, owner_id, title, description, subject, source_type, visibility, status, created_at
course_enrollments: id, user_id, course_id, role, progress_percent, created_at
materials: id, user_id, filename, content_type, storage_path, parse_status, extracted_text, metadata_json, created_at
course_material_links: id, course_id, material_id, added_by, created_at
course_materials: id, user_id, course_id, filename, content_type, storage_path, parse_status, extracted_text, metadata_json, created_at  # 当前 Phase 2 课程资料表，后续迁移到 materials + course_material_links
knowledge_points: id, course_id, title, summary, chapter, order_index, difficulty, prerequisites_json
knowledge_chunks: id, course_id, material_id, knowledge_point_id, content, page_number, section_title, embedding, metadata_json
student_profiles: id, user_id, profile_json, version, updated_at
profile_events: id, user_id, dimension, old_value, new_value, reason, evidence_refs, created_at
learning_paths: id, user_id, course_id, title, status, plan_json, created_at, updated_at
learning_tasks: id, path_id, user_id, course_id, knowledge_point_id, title, task_type, status, due_at, source_type, evidence_refs, order_index
generated_resources: id, user_id, course_id, knowledge_point_id, resource_type, title, content_markdown, content_json, citation_refs, review_status, confidence_score, trace_id, created_at
resource_quality_scores: id, resource_id, source_match, profile_fit, fact_confidence, difficulty_fit, completeness, notes
agent_run_logs: id, trace_id, user_id, course_id, agent_name, step_index, input_summary, output_summary, duration_ms, status, citation_refs, review_status, error_message, created_at
practice_sessions: id, user_id, course_id, title, status, score, started_at, finished_at
practice_answers: id, session_id, user_id, knowledge_point_id, question_json, answer_text, is_correct, score, feedback, created_at
assessment_reports: id, user_id, course_id, report_json, mastery_json, weakness_json, evidence_refs, created_at
weakness_review_queue: id, user_id, course_id, knowledge_point_id, weakness_reason, priority, recommended_resource_ids, next_review_at, status
chat_sessions: id, user_id, scope, course_id, title, mode, created_at
chat_messages: id, session_id, user_id, role, content, citation_refs, trace_id, created_at
model_settings: id, user_id, provider, base_url, encrypted_api_key, chat_model, embedding_model, is_default, created_at
learning_export_jobs: id, user_id, course_id, status, export_type, output_path, created_at, finished_at
```

- [ ] Run migration:

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\python -m alembic -c backend\alembic.ini revision --autogenerate -m "create core schema"
.\.venv\Scripts\python -m alembic -c backend\alembic.ini upgrade head
```

- [ ] Add tests in `backend/tests/test_models.py` for table creation and required columns.
- [ ] Verify:

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_models.py
```

- [ ] Commit:

```powershell
git add backend
git commit -m "feat(backend): add core database schema"
```

### Task 2.2: Add Artificial Intelligence Intro Course Pack

- [ ] Create `knowledge_base/artificial_intelligence_intro/course.json` with course title, summary, chapters and source metadata.
- [ ] Create `knowledge_base/artificial_intelligence_intro/knowledge_points.json` covering at least:

```text
人工智能概述
搜索问题与状态空间
启发式搜索
知识表示
机器学习基础
监督学习
神经网络
反向传播
自然语言处理
计算机视觉
智能体与多智能体
AI 伦理与安全
```

- [ ] Create `knowledge_base/artificial_intelligence_intro/seed_questions.json` with at least 24 questions, each bound to `knowledge_point_title`, `question_type`, `stem`, `answer`, `analysis`, `difficulty`.
- [ ] Add two short UTF-8 Markdown materials under `knowledge_base/artificial_intelligence_intro/materials/`, enough for RAG seeding and demo citations.
- [ ] Implement `backend/app/seed.py` to import the course pack, create course, knowledge points, seed chunks and seed questions.
- [ ] Verify:

```powershell
.\.venv\Scripts\python -m backend.app.seed --demo
.\.venv\Scripts\python -m pytest backend\tests
```

- [ ] Commit:

```powershell
git add knowledge_base backend
git commit -m "feat(data): seed artificial intelligence intro course"
```

## Phase 3: Frontend Foundation

### Task 3.1: Scaffold React Student Workspace

- [x] Create Vite React TypeScript app:

```powershell
pnpm create vite frontend --template react-ts
cd frontend
pnpm install
pnpm add @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-popover @radix-ui/react-tabs @tanstack/react-query axios zustand react-router-dom motion @xyflow/react echarts mermaid markmap-lib markmap-view clsx dayjs @phosphor-icons/react
pnpm add -D tailwindcss @tailwindcss/vite vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event @playwright/test
cd ..
```

- [x] Configure Tailwind CSS v4 through `@tailwindcss/vite` in `frontend/vite.config.ts` and import styles in `frontend/src/styles/global.css`.
- [x] Create app shell based on `docs/UI_UX_DESIGN.md`:

```text
frontend/src/app/App.tsx
frontend/src/app/routes.tsx
frontend/src/app/routePaths.ts
frontend/src/app/ProtectedRoute.tsx
frontend/src/app/PublicOnlyRoute.tsx
frontend/src/components/layout/LearningSpaceShell.tsx
frontend/src/components/layout/AppSidebar.tsx
frontend/src/components/command/CommandBar.tsx
frontend/src/components/canvas/LearningCanvas.tsx
frontend/src/components/canvas/SourceCluster.tsx
frontend/src/components/studio/StudioDock.tsx
frontend/src/components/evidence/EvidenceLayer.tsx
frontend/src/components/evidence/AgentTimeline.tsx
frontend/src/features/auth/authStore.ts
frontend/src/api/client.ts
frontend/src/features/demo/demoApi.ts
frontend/src/features/onboarding/FirstRunGuide.tsx
```

- [x] Pages to create now:

```text
LoginPage.tsx
RegisterPage.tsx
DemoEntryPage.tsx
LearningSpacePage.tsx
LibraryPage.tsx
StudioPage.tsx
ReportsPage.tsx
ProfilePage.tsx
TutorPage.tsx
PracticePage.tsx
SettingsPage.tsx
```

- [x] Design direction:

```text
AI conversation-first learning home for students
Top lightweight navigation
Central AI learning input
Home conversation history
Independent material library entry
Recent courses / recent learning spaces
Course spaces for learning canvas, Studio, citations and Agent traces
Quiet material depth with restrained motion
No marketing landing page
No decorative gradient orbs
No giant hero section
No fixed left admin sidebar
No KPI card wall
```

- [x] Route baseline:

```text
/ -> RootRedirect
/login -> LoginPage
/register -> RegisterPage
/demo -> DemoEntryPage
/app -> LearningSpacePage
/app/library -> LibraryPage
/app/courses/:courseId -> CourseSpacePage
/app/studio -> StudioPage
/app/profile -> ProfilePage
/app/tutor -> TutorPage
/app/practice -> PracticePage
/app/reports -> ReportsPage
/app/settings -> SettingsPage
* -> NotFoundPage
```

- [x] Entry experience:

```text
Login page includes normal login, register link and demo experience entry.
Register page collects nickname, email, password and password confirmation only.
FirstRunGuide appears when user has no home history, uploaded material, recent course or profile.
ProtectedRoute redirects unauthenticated `/app/*` users to `/login`.
PublicOnlyRoute redirects authenticated users away from `/login` and `/register`.
```

- [x] Verify:

```powershell
cd frontend
pnpm lint
pnpm test
pnpm build
cd ..
```

- [ ] Commit:

```powershell
git add frontend
git commit -m "feat(frontend): scaffold student workspace shell"
```

Current Phase 3.1 implementation note:

- `frontend/` has been created with React, TypeScript, Vite, Tailwind CSS v4, React Router, Zustand, React Query, Motion, Radix, React Flow, ECharts, Mermaid, Markmap, Vitest and ESLint.
- `markmap-viewer` in the initial plan was corrected to the actual npm package `markmap-view`.
- Routes, public/protected guards, local preview auth store, API client, login/register/Demo pages, learning-space shell, top navigation, AI conversation-first home, home history, material library entry, recent courses, course generation dialog, first-run guide and student core page skeletons are implemented.
- Phase 3D/3E added frontend API contract modules, upload-to-course workflow state, empty/loading/error/low-evidence/demo-fallback state panels and page-level tests.
- Phase 3 closure redesign first produced the skill-based direction `Productivity Tool + AI-Native UI + Knowledge Graph + Process Map`, replacing the five-card status feel with a learning operating system canvas, process rail, status signals and dark Studio Dock.
- 2026-07-01 P3R3 implemented the AI conversation-first learning home with history, centered learning input, material-library drawer entry, semantic recent-learning list, restrained learning-signal background and course generation dialog; the existing learning canvas, Studio Dock and evidence layer should be reused inside course space or answer expansion instead of dominating `/app`.
- P3 completion added `/app/courses/:courseId` as a protected static/semi-static course space with course chat, course history, knowledge canvas, today's tasks, Studio output, citations and Agent trace; real backend data remains Phase 4+.
- P3.6 added structured skeletons for library, Studio, profile, tutor, practice, reports and settings pages; tests now lock their material, generation, profile, tutoring, practice, report and settings regions so they do not regress into placeholder pages.
- P3.7 added local interaction feedback for the main visible buttons: home composer, material drawer selection, course answer expansion, knowledge-node detail, tutor mode, practice submission, library citations, settings save, Studio/profile/report actions and top search now show explicit demo-state feedback until real APIs replace those handlers.
- P3.8 now uses layered route discovery: top and mobile navigation expose learning space, library and Studio; the personal menu exposes profile, reports and settings; course space exposes tutor, practice and reports as contextual learning actions.
- The `/app` home shell now follows the user-provided ChatGPT references: the home sidebar is flush with the left browser edge, can collapse to an icon rail, the initial composer is smaller, and the first sent question moves the page into a chat thread with the composer docked near the bottom.
- Browser visual checks covered P3R3 `/app` at desktop and mobile widths with no horizontal overflow; the material-library drawer and course generation dialog open and remain readable.
- Frontend `pnpm lint`, `pnpm test` and `pnpm build` pass before final repository-wide verification.
- Real backend auth, `/dashboard/summary`, upload/RAG/AI data and final browser E2E remain later-phase work.

### Task 3.2: Add Frontend Data Contracts

- [x] Create `frontend/src/types/api.ts` mirroring backend response shapes for user, course, material, profile, resource, path, task, report, agent log.
- [x] Create API modules:

```text
frontend/src/api/auth.ts
frontend/src/api/courses.ts
frontend/src/api/materials.ts
frontend/src/api/profiles.ts
frontend/src/api/resources.ts
frontend/src/api/paths.ts
frontend/src/api/tutor.ts
frontend/src/api/practice.ts
frontend/src/api/reports.ts
frontend/src/api/demo.ts
frontend/src/api/settings.ts
```

- [x] Configure Axios to attach JWT and handle 401 by returning to login.
- [x] Add Vitest tests for auth store token persistence, API client base URL and key API route constants.
- [x] Add Phase 3D state tests for upload-to-course workflow status and fallback state panels.
- [x] Connect the state layer to LearningSpace, Library and Studio surfaces without introducing a fixed left admin dashboard.
- [ ] Commit:

```powershell
git add frontend
git commit -m "feat(frontend): add API client contracts"
```

## Phase 4: Authentication and Student Learning Space

### Task 4.1: Backend Auth

- [ ] Implement `backend/app/core/security.py` with password hashing, JWT creation, JWT parsing and current user dependency.
- [ ] Implement `backend/app/api/v1/auth.py`:

```text
POST /auth/register
POST /auth/login
GET /auth/me
POST /auth/logout
```

- [ ] Validation:

```text
email must be valid
password length at least 8
role defaults to student
duplicate email returns 409
```

- [ ] Tests:

```text
backend/tests/test_auth.py
register user
reject duplicate user
login user
reject wrong password
read current user
```

- [ ] Verify:

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_auth.py
```

- [ ] Commit:

```powershell
git add backend
git commit -m "feat(auth): add student authentication"
```

### Task 4.2: Frontend Auth and Learning Space

- [ ] Connect Login and Register pages to backend.
- [ ] Protect student learning-space routes.
- [ ] Implement route return after login for users redirected from `/app/*`.
- [ ] Connect Demo entry to `/demo/status` and `/demo/reset`.
- [ ] Show FirstRunGuide for new accounts without profile or selected course.
- [ ] LearningSpace page shows:

```text
profile summary
current course
today tasks
recent resources
learning canvas backed by `/dashboard/summary` response data
AI command suggestions
Studio output summary
evidence layer entry with latest citations and Agent trace
```

- [ ] Backend adds:

```text
GET /dashboard/summary
```

- [ ] Verify in browser:

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend
pnpm dev --host 127.0.0.1 --port 5173
```

Manual acceptance:

```text
register -> login -> learning space visible -> logout -> protected page redirects to login
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(workspace): connect login and learning space"
```

## Phase 5: Upload Materials and Build Course

### Task 5.1: Document Parsing Service

- [ ] Create parsers:

```text
backend/app/services/document_parser.py
backend/app/services/chunking_service.py
backend/app/services/course_builder_service.py
```

- [ ] Supported formats:

```text
PDF via pypdf
PPTX via python-pptx
DOCX via python-docx
Markdown as structured headings
TXT as plain text
```

- [ ] Implement upload endpoint:

```text
POST /materials/upload
GET /materials/{material_id}
GET /materials/{material_id}/progress
```

- [ ] Store uploaded files under `storage/uploads/{user_id}/library/`; course-derived chunks and generated outputs use course-scoped paths after material is linked or used to generate a course. Keep `storage/` ignored by Git.
- [ ] Progress states:

```text
uploaded
parsing
building_course
chunking
embedding
path_generating
completed
failed
```

- [ ] Tests:

```text
backend/tests/fixtures/sample_ai_notes.md
backend/tests/fixtures/sample_ai_notes.txt
backend/tests/test_material_parsing.py
```

- [ ] Verify:

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_material_parsing.py
```

- [ ] Commit:

```powershell
git add backend .gitignore
git commit -m "feat(materials): parse uploaded learning files"
```

### Task 5.2: CourseBuilderAgent v1

- [ ] Implement `CourseBuilderAgent` to extract:

```text
course title
course summary
chapters
knowledge points
prerequisite relations
key difficulties
exam-oriented points
```

- [ ] Use LLM when configured; use deterministic fallback extractor when Demo Mode is enabled or provider health check fails.
- [ ] Add `POST /courses/from-materials`、`GET /courses/{course_id}/overview` and `POST /courses/{course_id}/materials`.
- [ ] Library upload flow shows independent material progress, optional course linking and generated course overview.
- [ ] Tests cover fallback extractor and API response.
- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(courses): build course from uploaded materials"
```

## Phase 6: Model Provider, Embedding and RAG

### Task 6.1: Provider Abstraction

- [ ] Create `backend/app/providers/base.py`:

```python
from typing import Protocol, AsyncIterator

class LLMProvider(Protocol):
    async def chat_completion(self, messages: list[dict], model: str | None = None) -> str: ...
    async def stream_chat_completion(self, messages: list[dict], model: str | None = None) -> AsyncIterator[str]: ...
    async def embedding(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...
    async def model_list(self) -> list[str]: ...
    async def health_check(self) -> bool: ...
```

- [ ] Implement:

```text
backend/app/providers/openai_compatible.py
backend/app/providers/fallback.py
backend/app/providers/factory.py
```

- [ ] Settings page supports provider, base URL, API key, chat model, embedding model and connection test.
- [ ] API Key logging rule: never log raw key; return only masked key like `sk-****abcd`.
- [ ] Tests:

```text
backend/tests/test_provider.py
frontend/src/pages/SettingsPage.test.tsx
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(ai): add model provider abstraction"
```

### Task 6.2: RAG Search and Citations

- [ ] Implement:

```text
backend/app/rag/embedding_service.py
backend/app/rag/vector_store.py
backend/app/rag/retriever.py
backend/app/rag/citation.py
```

- [ ] Use pgvector for configured embeddings; use deterministic hashed vectors for tests and Demo Mode fallback.
- [ ] Add endpoints:

```text
GET /courses/{course_id}/knowledge-points
POST /rag/search
```

- [ ] Search response includes:

```text
chunk_id
course_id
material_id
knowledge_point_id
content
source_title
page_number
score
```

- [ ] Tests:

```text
backend/tests/test_rag.py
```

- [ ] Commit:

```powershell
git add backend
git commit -m "feat(rag): add vector search with citations"
```

## Phase 7: Conversational Profile

### Task 7.1: ProfileAgent and Profile APIs

- [ ] Implement `ProfileAgent` in `backend/app/agents/nodes/profile_agent.py`.
- [ ] Profile JSON dimensions:

```text
major_background
knowledge_foundation
learning_goal
cognitive_style
learning_preference
weak_points
learning_pace
motivation_interest
```

- [ ] API:

```text
GET /profiles/me
POST /profiles/chat
GET /profiles/events
```

- [ ] `POST /profiles/chat` takes a message, updates profile when evidence is sufficient, and creates `profile_events`.
- [ ] Frontend Profile page provides chat UI, profile cards and evidence list.
- [ ] Tests:

```text
backend/tests/test_profiles.py
frontend/src/pages/ProfilePage.test.tsx
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(profile): add conversational learning profile"
```

## Phase 8: Multi-Agent Resource Generation

### Task 8.1: Agent Graph and Observability

- [ ] Create `backend/app/agents/schemas.py` with shared state:

```text
trace_id
user_id
course_id
knowledge_point_id
intent
profile
retrieved_chunks
diagnosis
generated_resources
review_result
errors
```

- [ ] Create `backend/app/agents/graph.py` with LangGraph flow:

```text
profile -> retrieve -> diagnosis -> resource -> review -> persist
```

- [ ] Every node writes `agent_run_logs` with `trace_id`, `agent_name`, `step_index`, `duration_ms`, `status`, `input_summary`, `output_summary`.
- [ ] API:

```text
GET /agents/traces/{trace_id}
```

- [ ] Frontend EvidenceLayer and AgentTimeline render status, duration, citation count and review result.
- [ ] Tests:

```text
backend/tests/test_agent_logs.py
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(agents): add observable agent graph"
```

### Task 8.2: Generate 5 Resource Types

- [ ] Implement workers:

```text
DocWorker: personalized explanation Markdown
MindMapWorker: Mermaid mindmap or Markmap Markdown
QuizWorker: single choice, multiple choice, short answer and analysis
CodeWorker: runnable learning case for AI course topics
SlideWorker: PPT outline and teaching script
```

- [ ] API:

```text
POST /resources/generate
GET /resources
GET /resources/{resource_id}
GET /resources/{resource_id}/quality
```

- [ ] Resource generation input:

```text
course_id
knowledge_point_id
resource_types
learning_goal
difficulty
```

- [ ] Persist `generated_resources` and `resource_quality_scores`.
- [ ] Studio page lets user select course, knowledge point and resource types; displays generated resource outputs with citations, confidence, review status and quality scores.
- [ ] Tests:

```text
backend/tests/test_resource_generation.py
frontend/src/pages/StudioPage.test.tsx
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(resources): generate five personalized resource types"
```

## Phase 9: Learning Path, Mastery Map and Review Queue

### Task 9.1: PathAgent and Learning Tasks

- [ ] Implement `PathAgent` using profile, course knowledge points, prerequisites and mastery data.
- [ ] API:

```text
POST /paths/generate
GET /paths/current
PATCH /paths/tasks/{task_id}
```

- [ ] Learning path output:

```text
3/7/14 day plan option
ordered tasks
knowledge point dependencies
recommended resources
reason for task order
```

- [ ] LearningPath page shows timeline, current day task, future tasks and task completion.
- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(paths): generate personalized learning path"
```

### Task 9.2: Mastery and Blind-Spot Tracing

- [ ] Implement `backend/app/services/mastery_service.py`.
- [ ] Mastery statuses:

```text
not_started
learning
mastered
weak
recommended_review
```

- [ ] Implement blind-spot tracing:

```text
wrong answer knowledge point -> prerequisites graph -> weakest prerequisite -> recommended repair task
```

- [ ] API:

```text
GET /courses/{course_id}/mastery-map
GET /weakness-review-queue
POST /weakness-review-queue/{item_id}/start
```

- [ ] Frontend adds ECharts mastery map and review queue panel.
- [ ] Tests:

```text
backend/tests/test_mastery.py
frontend/src/visualizations/MasteryMap.test.tsx
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(learning): add mastery map and blind spot tracing"
```

## Phase 10: Tutor, Practice and Assessment

### Task 10.1: RAG Tutor with Socratic Mode

- [ ] Implement `TutorAgent` with modes:

```text
direct
socratic
exam_sprint
```

- [ ] API:

```text
POST /tutor/sessions
GET /tutor/sessions
GET /tutor/sessions/{session_id}
POST /tutor/sessions/{session_id}/messages
GET /tutor/sessions/{session_id}/stream
```

- [ ] Responses include citations; when sources are insufficient, answer says the current course materials do not provide enough basis and clearly separates general background knowledge.
- [ ] Tutor page supports Markdown rendering, citation drawer, Socratic mode switch and Agent timeline.
- [ ] Tests:

```text
backend/tests/test_tutor.py
frontend/src/pages/TutorPage.test.tsx
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(tutor): add cited AI tutoring"
```

### Task 10.2: Practice, Assessment and Report

- [ ] Implement:

```text
backend/app/services/practice_service.py
backend/app/services/assessment_service.py
```

- [ ] API:

```text
POST /practice/sessions
GET /practice/sessions/{session_id}
POST /practice/sessions/{session_id}/answers
POST /reports/generate
GET /reports/latest
```

- [ ] Assessment report includes:

```text
score
mastery update
weakness list
profile changes
evidence_refs
next_step_suggestions
review_queue_updates
```

- [ ] Practice page supports answering, submit, immediate feedback and wrong-question explanation.
- [ ] Report page shows radar chart, mastery summary, profile event list and next tasks.
- [ ] Tests:

```text
backend/tests/test_practice_assessment.py
frontend/src/pages/PracticePage.test.tsx
frontend/src/pages/ReportPage.test.tsx
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(assessment): add practice and learning reports"
```

## Phase 11: Exam Sprint and Material Comparison

### Task 11.1: Exam Sprint Mode

- [ ] Implement `backend/app/services/exam_sprint_service.py`.
- [ ] API:

```text
POST /exam-sprint/plans
GET /exam-sprint/plans/{plan_id}
```

- [ ] Plan durations: `3`, `7`, `14` days.
- [ ] Output includes:

```text
high_frequency_points
weak_points
daily_tasks
must_do_questions
easy_mistake_warnings
recommended_resources
```

- [ ] Add sprint mode entry on LearningSpace and LearningPath page.
- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(exam): add sprint learning mode"
```

### Task 11.2: Material Comparison and Exam Point Extraction

- [ ] Implement `backend/app/services/material_comparison_service.py`.
- [ ] API:

```text
POST /materials/compare
```

- [ ] Output:

```text
repeated_concepts
exam_likely_points
materials_only_points
questions_only_points
missing_review_points
priority_order
citations
```

- [ ] Library upload flow allows selecting multiple materials for comparison.
- [ ] Tests:

```text
backend/tests/test_material_comparison.py
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(materials): extract exam points from compared materials"
```

## Phase 12: Demo Mode, Export and Open Source Readiness

### Task 12.1: Demo Mode

- [ ] Create demo account seeding:

```text
email: demo@edunova.local
password: Demo123456
display_name: 演示学生
```

- [ ] Create `backend/app/services/demo_service.py` to seed demo course, profile, resources, path, practice session, report and agent logs.
- [ ] API:

```text
POST /demo/reset
GET /demo/status
```

- [ ] Frontend login page has Demo button that signs into the demo account after reset confirmation.
- [ ] Clearly label fallback content with `demo_fallback` in API payloads and UI detail panels.
- [ ] Verify full demo chain:

```text
demo login -> learning space -> profile -> upload course sample -> generate resources -> path -> tutor -> practice -> report -> agent trace
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(demo): add stable demonstration mode"
```

### Task 12.2: Markdown Learning Dossier Export

- [ ] Implement `backend/app/services/export_service.py`.
- [ ] API:

```text
POST /exports/learning-dossier
GET /exports/{job_id}
```

- [ ] Export Markdown sections:

```text
学习画像摘要
画像变化记录
课程学习路径
生成过的核心资源
错题和薄弱点
掌握度变化
AI 学习报告
引用来源摘要
Agent 轨迹摘要
```

- [ ] Report page adds export button and download link.
- [ ] Tests:

```text
backend/tests/test_export.py
```

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat(export): add markdown learning dossier"
```

### Task 12.3: Documentation Set

- [ ] Create or update:

```text
README.md
docs/ARCHITECTURE.md
docs/API.md
docs/DEPLOYMENT.md
docs/DEVELOPMENT_REPORT.md
docs/TEST_REPORT.md
docs/OPEN_SOURCE_NOTICE.md
docs/DEFENSE_QA.md
```

- [ ] Documentation must cover:

```text
赛题需求映射
核心创新点
多智能体架构
RAG 与防幻觉机制
上传资料建课流程
数据模型
部署方式
测试方法
参考项目与许可证
AI Coding 工具使用说明
答辩问题与回答
```

- [ ] Commit:

```powershell
git add README.md docs
git commit -m "docs: add competition documentation set"
```

## Phase 13: Verification and Hardening

### Task 13.1: Automated Test Gate

- [ ] Backend checks:

```powershell
.\.venv\Scripts\python -m ruff check backend
.\.venv\Scripts\python -m pytest backend\tests --cov=backend\app
```

- [ ] Frontend checks:

```powershell
cd frontend
pnpm lint
pnpm test
pnpm build
pnpm exec playwright install chromium
pnpm exec playwright test
cd ..
```

- [ ] Encoding and repository checks:

```powershell
.\scripts\verify_encoding.ps1
git status --short --untracked-files=all
```

- [ ] Commit fixes:

```powershell
git add backend frontend docs scripts
git commit -m "test: harden EduNova acceptance checks"
```

### Task 13.2: Browser Acceptance

- [ ] Start system:

```powershell
docker compose up --build
```

- [ ] Verify in browser:

```text
open login page
use demo account
learning space loads
profile radar renders
course list renders
upload sample material and see progress
generated course overview appears
generate 5 resources
resource citations visible
agent trace visible
generate learning path
ask tutor a cited question
finish practice session
report updates mastery and review queue
export Markdown dossier
```

- [ ] Save screenshots under `docs/evidence/`:

```text
learning-space.png
upload-course.png
resource-generation.png
agent-trace.png
learning-path.png
tutor-citation.png
practice-report.png
export-dossier.png
```

- [ ] Commit:

```powershell
git add docs/evidence
git commit -m "docs: add browser acceptance evidence"
```

## Phase 14: Submission Assets

### Task 14.1: PPT Outline and Video Script

- [ ] Create `docs/submission/PPT_OUTLINE.md` with 12 slides:

```text
1 项目标题与赛题定位
2 高校学生学习痛点
3 EduNova 产品定义
4 总体架构
5 多智能体协作机制
6 上传资料自动建课
7 个性化资源生成
8 RAG 防幻觉与引用溯源
9 学习路径与评估闭环
10 Demo 效果截图
11 创新价值与开源计划
12 总结与未来扩展
```

- [ ] Create `docs/submission/VIDEO_SCRIPT.md` for a 7-minute demo:

```text
0:00-0:30 项目定位
0:30-1:10 登录与学习空间
1:10-2:00 对话画像
2:00-3:00 上传资料建课
3:00-4:00 资源生成与 Agent 轨迹
4:00-5:00 学习路径与 RAG 辅导
5:00-6:00 练习评估与报告
6:00-7:00 防幻觉、部署、开源价值总结
```

- [ ] Commit:

```powershell
git add docs/submission
git commit -m "docs: add submission presentation assets"
```

### Task 14.2: Final Package Check

- [ ] Run:

```powershell
.\scripts\test.ps1
docker compose config
docker compose up --build
.\scripts\verify_encoding.ps1
git status --short --untracked-files=all
```

- [ ] Confirm submission package includes:

```text
source code
knowledge_base
docker-compose.yml
.env.example
README.md
system development document
test document
deployment document
PPT
demo video
open source notice
AI Coding tool usage note
```

- [ ] Tag local release:

```powershell
git tag edunova-initial-submission-2026-07-20
```

## Acceptance Matrix

| Requirement | Implementation Target | Evidence |
| --- | --- | --- |
| 不少于 6 维对话画像 | 8 维 `student_profiles.profile_json` + `profile_events` | Profile page + tests |
| 多智能体架构 | LangGraph + 9 agents + `agent_run_logs` | Agent trace panel + architecture doc |
| 至少 5 类资源 | Doc, MindMap, Quiz, Code, Slide | Studio page + resource tests |
| 学习路径规划 | PathAgent + `learning_paths` + `learning_tasks` | LearningPath page |
| 资源精准推送 | profile + mastery + resource quality scores | LearningSpace recommendations |
| 智能辅导 | RAG Tutor + Socratic mode + citations | Tutor page |
| 学习效果评估 | practice, mastery, weakness queue, reports | Practice and Report pages |
| 防幻觉 | citations, ReviewAgent, confidence, low-evidence warning | Tutor/resources UI |
| 响应等待体验 | SSE/progress endpoints + Agent timeline | Upload and generation progress |
| 自建课程知识库 | AI intro course pack + upload course builder | Course pages |
| 开源协议说明 | `OPEN_SOURCE_NOTICE.md` + `LICENSE` | docs |
| 部署复现 | Docker Compose + deployment doc | `docker compose up --build` |

## Daily Schedule

| Date | Target | Required Commit Theme |
| --- | --- | --- |
| 2026-07-01 | Repo baseline, scripts, backend skeleton, Docker draft | docs/chore/feat backend foundation |
| 2026-07-02 | Data model, migrations, AI intro seed course | feat data schema |
| 2026-07-03 | Frontend learning space shell and auth | feat workspace |
| 2026-07-04 | Upload parsing and CourseBuilderAgent | feat materials/courses |
| 2026-07-05 | Provider abstraction, embeddings, RAG citations | feat ai/rag |
| 2026-07-06 | Conversational profile | feat profile |
| 2026-07-07 | Agent graph, resource generation, trace panel | feat agents/resources |
| 2026-07-08 | Learning path, mastery map, review queue | feat paths/learning |
| 2026-07-09 | Tutor with RAG, Socratic mode | feat tutor |
| 2026-07-10 | Practice, assessment, learning report | feat assessment |
| 2026-07-11 | Exam sprint, material comparison, export | feat exam/export |
| 2026-07-12 | Demo Mode, visual polish, docs first pass | feat demo/docs |
| 2026-07-13 | Docker acceptance, tests, browser evidence | test/docs evidence |
| 2026-07-14 | Freeze feature scope, fix defects, lock runnable build | chore freeze |
| 2026-07-15 | Development report and test report | docs reports |
| 2026-07-16 | Deployment guide and defense QA | docs defense |
| 2026-07-17 | PPT production | docs presentation |
| 2026-07-18 | Demo video recording | docs video script |
| 2026-07-19 | Full rehearsal and screenshots | docs evidence |
| 2026-07-20 | Submission package check | release tag |

## Execution Order

1. Finish Phase 0 through Phase 4 before adding AI-heavy features.
2. Finish upload parsing before RAG, because RAG needs course chunks and citations.
3. Finish provider abstraction before agent generation, because every agent depends on the same model contract.
4. Finish Agent logs before polishing UI, because trace visibility is a core competition proof.
5. Keep Demo Mode integrated from Phase 5 onward, so every feature can be shown even when model APIs are unstable.

## Self-Review Checklist

- [ ] The plan covers all basic赛题 requirements and both optional bonus features.
- [ ] The plan maps each major feature to concrete files, APIs, tests and commits.
- [ ] The plan keeps the first version student-first and avoids full teacher/classroom/admin scope.
- [ ] The plan includes upload-to-course, RAG citation, ReviewAgent, Agent trace, Demo Mode and Docker deployment.
- [ ] The plan includes documentation, PPT, video and submission package work.
- [ ] The plan avoids untracked secrets and requires `.env.example` instead of real `.env`.
- [ ] The plan respects UTF-8 no BOM and Chinese literal output requirements.
