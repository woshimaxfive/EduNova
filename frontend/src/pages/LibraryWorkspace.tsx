import { BookOpen, ChatCircleText, Folders, Sparkle } from "@phosphor-icons/react";
import { useState } from "react";

import { buildCoursePath, PATHS } from "../app/routePaths";
import { type AiJob } from "../api/aiJobs";
import { type ApiCourseSummary } from "../api/courses";
import {
  type MaterialComparisonPoint,
  type MaterialComparisonResult,
  type MaterialDetail,
  type MaterialListItem,
  type MaterialOutline,
  type MaterialOutlineOperation,
  type MaterialOutlineSection
} from "../api/materials";
import { AgentTraceDisclosure } from "../components/evidence/AgentTraceDisclosure";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { LibraryCourseDialog } from "../components/library/LibraryCourseDialog";
import { LibraryDrawer } from "../components/library/LibraryDrawer";
import { LibraryFileTable } from "../components/library/LibraryFileTable";
import { isComparableMaterial } from "../components/library/libraryMaterialState";
import { LibraryWorkspaceToolbar } from "../components/library/LibraryWorkspaceToolbar";
import { NextLearningAction } from "../components/learning/NextLearningAction";
import { ConfirmDialog } from "../components/primitives/Dialog";
import {
  pointConfidenceLabel,
  type CompareTab,
  type CompareView,
  type DetailTab
} from "../features/library/libraryWorkspaceModel";
import "../styles/library.css";
import { PageFrame } from "./PageFrame";
import { useLibraryWorkspaceController } from "./useLibraryWorkspaceController";

function ComparisonPointList({ title, points }: { title: string; points: MaterialComparisonPoint[] }) {
  return (
    <section className="library-comparison-group" aria-label={title}>
      <h3>{title}</h3>
      {points.length === 0 ? <p>暂无结果。</p> : (
        <ul>
          {points.map((point) => (
            <li key={`${title}-${point.title}-${point.material_ids.join("-")}`}>
              <strong>{point.title}</strong>
              <span>{point.reason}</span>
              <small>依据 {point.support_count} 条 · 可信度 {pointConfidenceLabel(point.confidence)}</small>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function LibraryWorkspace() {
  const controller = useLibraryWorkspaceController();
  const {
    activeFilter,
    activeMaterialJob,
    applyOutlineOperations,
    cancelJob,
    closeDrawer,
    compareFeedback,
    compareMaterialIds,
    compareTab,
    compareView,
    courseDialogFeedback,
    courseJob,
    courseMaterialIds,
    courseTitle,
    courseTitles,
    courses,
    detailCanUse,
    detailState,
    detailTab,
    displayedComparison,
    drawerMode,
    effectiveCompareCourseId,
    files,
    filteredFiles,
    handleConfirmOutline,
    handleCompareMaterials,
    handleCreateCourse,
    handleDeleteMaterial,
    handleNextAction,
    handleReingestMaterial,
    handleUploadFile,
    isCourseDialogOpen,
    isComparingMaterials,
    isCreatingCourse,
    isDeletingMaterial,
    isUpdatingOutline,
    isUploadingMaterial,
    latestComparisonQuery,
    libraryFeedback,
    materialDetail,
    materialDetailQuery,
    materialOutline,
    materialOutlineQuery,
    materialPendingDeletion,
    materialsQuery,
    navigate,
    nextActionQuery,
    openCourseDialog,
    openMaterial,
    openRecentComparison,
    outlineFeedback,
    parsedCount,
    recentComparisonCourseId,
    retryJob,
    searchTerm,
    selectedCompareMaterials,
    selectedMaterial,
    setActiveFilter,
    setCompareCourseId,
    setCompareTab,
    setCourseJobId,
    setCourseTitle,
    setCourseTitleTouched,
    setDetailTab,
    setIsCourseDialogOpen,
    setMaterialPendingDeletion,
    setSearchTerm,
    sharedCourses,
    startCompare,
    toggleCompareMaterial,
    toggleCourseMaterial,
    uploadInputRef,
  } = controller;

  const compareFooter = compareView === "setup" ? (
    <>
      <p>{compareMaterialIds.length} 份资料 · {effectiveCompareCourseId ? courseTitles.get(effectiveCompareCourseId) : "等待共同课程"}</p>
      <button className="primary-action" type="button" disabled={compareMaterialIds.length < 2 || !effectiveCompareCourseId || isComparingMaterials} onClick={() => void handleCompareMaterials()}>
        {isComparingMaterials ? "对比中" : "生成资料对比"}
      </button>
    </>
  ) : undefined;

  return (
    <>
      <PageFrame title="资料库" titleMode="sr-only" variant="wide-workspace">
        <section className="library-workspace" aria-label="资料工作台">
          <input
            ref={uploadInputRef}
            className="visually-hidden"
            type="file"
            aria-label="上传资料文件"
            accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg,.webp"
            onChange={(event) => void handleUploadFile(event)}
          />
          <LibraryWorkspaceToolbar
            search={searchTerm}
            filter={activeFilter}
            materialCount={files.length}
            parsedCount={parsedCount}
            isUploading={isUploadingMaterial}
            hasCourses={courses.length > 0}
            onSearchChange={setSearchTerm}
            onFilterChange={setActiveFilter}
            onUpload={() => uploadInputRef.current?.click()}
            onGenerateCourse={() => openCourseDialog()}
            onStartCompare={() => startCompare()}
            onOpenRecentComparison={openRecentComparison}
          />
          <NextLearningAction
            action={nextActionQuery.data?.data}
            isLoading={nextActionQuery.isPending}
            error={nextActionQuery.isError}
            compact
            onAction={handleNextAction}
          />
          <InlineFeedback message={libraryFeedback} tone="warning" className="library-workspace-feedback" />
          {drawerMode === "compare" && compareView === "setup" ? (
            <div className="library-compare-mode-note">
              <strong>正在选择对比资料</strong>
              <span>选择至少两份已解析且属于同一课程的文档。</span>
              <button type="button" onClick={closeDrawer}>退出选择</button>
            </div>
          ) : null}
          <LibraryFileTable
            materials={filteredFiles}
            totalMaterialCount={files.length}
            courseTitles={courseTitles}
            compareMode={drawerMode === "compare" && compareView === "setup"}
            selectedMaterialIds={compareMaterialIds}
            isLoading={materialsQuery.isLoading}
            isError={materialsQuery.isError}
            onOpenMaterial={openMaterial}
            onToggleCompare={toggleCompareMaterial}
            onRequestDelete={setMaterialPendingDeletion}
          />
        </section>
      </PageFrame>

      {drawerMode === "detail" ? (
        <LibraryDrawer
          title={selectedMaterial?.title ?? "资料详情"}
          onClose={closeDrawer}
          footer={detailState ? (
            <div className="library-detail-actions">
              {!activeMaterialJob && ["legacy", "failed", "awaiting_confirmation"].includes(detailState.ingestion_status ?? "") ? (
                <button className="soft-button" type="button" disabled={isUpdatingOutline} onClick={() => void handleReingestMaterial()}>重新精细解析</button>
              ) : null}
              {materialOutline && !materialOutline.confirmed ? (
                <button className="primary-action" type="button" disabled={Boolean(activeMaterialJob) || isUpdatingOutline || !materialOutline.quality.passed} onClick={() => void handleConfirmOutline()}>
                  {isUpdatingOutline ? "保存中" : "确认目录"}
                </button>
              ) : null}
              <button className="soft-button" type="button" disabled={!detailCanUse} onClick={() => navigate(PATHS.app, { state: { selectedMaterialIds: [detailState.id] } })}>
                <ChatCircleText size={16} aria-hidden="true" />
                <span>带到主页提问</span>
              </button>
              <button className="soft-button" type="button" disabled={!detailCanUse} onClick={() => openCourseDialog([detailState.id])}>
                <Sparkle size={16} aria-hidden="true" />
                <span>生成课程</span>
              </button>
              <button className="soft-button" type="button" disabled={!isComparableMaterial(detailState)} onClick={() => startCompare([detailState.id])}>
                加入对比
              </button>
            </div>
          ) : undefined}
        >
          <MaterialDetailPanel
            material={materialDetail}
            fallbackMaterial={selectedMaterial}
            activeJob={activeMaterialJob}
            outline={materialOutline}
            tab={detailTab}
            isLoading={materialDetailQuery.isLoading}
            isError={materialDetailQuery.isError}
            isOutlineLoading={materialOutlineQuery.isLoading}
            isUpdatingOutline={isUpdatingOutline}
            outlineFeedback={outlineFeedback}
            onTabChange={setDetailTab}
            onApplyOutline={(operations) => void applyOutlineOperations(operations)}
            onOpenCourse={(courseId) => navigate(buildCoursePath(courseId))}
          />
        </LibraryDrawer>
      ) : null}

      <ConfirmDialog
        open={materialPendingDeletion !== null}
        title="删除资料"
        description={`删除“${materialPendingDeletion?.title ?? "这份资料"}”后，关联课程将不再使用它。此操作不可撤销。`}
        confirmLabel={isDeletingMaterial ? "正在删除" : "删除资料"}
        layerClassName="destructive-confirm-layer"
        onOpenChange={(open) => { if (!open && !isDeletingMaterial) setMaterialPendingDeletion(null); }}
        onConfirm={() => void handleDeleteMaterial()}
      >
        <section>
          <h2>删除资料</h2>
          <p>删除“{materialPendingDeletion?.title}”后，关联课程将不再使用它。此操作不可撤销。</p>
          <div>
            <button type="button" disabled={isDeletingMaterial} onClick={() => setMaterialPendingDeletion(null)}>取消</button>
            <button className="danger" type="button" disabled={isDeletingMaterial} onClick={() => void handleDeleteMaterial()}>{isDeletingMaterial ? "正在删除" : "删除资料"}</button>
          </div>
        </section>
      </ConfirmDialog>

      {drawerMode === "compare" ? (
        <LibraryDrawer
          title={compareView === "setup" ? "资料对比" : "对比结果"}
          workspaceInteractive={compareView === "setup"}
          onClose={closeDrawer}
          footer={compareFooter}
        >
          <ComparisonPanel
            view={compareView}
            tab={compareTab}
            selectedMaterials={selectedCompareMaterials}
            sharedCourses={compareView === "recent" ? courses : sharedCourses}
            selectedCourseId={compareView === "recent" ? recentComparisonCourseId : effectiveCompareCourseId}
            result={displayedComparison}
            feedback={compareFeedback}
            isLoading={compareView === "recent" && latestComparisonQuery.isLoading}
            isError={compareView === "recent" && latestComparisonQuery.isError}
            onCourseChange={setCompareCourseId}
            onTabChange={setCompareTab}
            onBackToSetup={() => startCompare()}
          />
        </LibraryDrawer>
      ) : null}

      {isCourseDialogOpen ? (
        <LibraryCourseDialog
          materials={files}
          selectedMaterialIds={courseMaterialIds}
          courseTitle={courseTitle}
          isCreatingCourse={isCreatingCourse}
          job={courseJob}
          onCancelJob={() => courseJob && void cancelJob(courseJob.job_id)}
          onRetryJob={() => courseJob && void retryJob(courseJob.job_id).then((job) => setCourseJobId(job.job_id))}
          onCourseTitleChange={(value) => {
            setCourseTitle(value);
            setCourseTitleTouched(true);
          }}
          onToggleMaterial={toggleCourseMaterial}
          feedback={courseDialogFeedback}
          onClose={() => setIsCourseDialogOpen(false)}
          onCreate={() => void handleCreateCourse()}
        />
      ) : null}
    </>
  );
}

function MaterialDetailPanel(props: {
  material: MaterialDetail | null;
  fallbackMaterial: MaterialListItem | null;
  activeJob: AiJob | null;
  outline: MaterialOutline | null;
  tab: DetailTab;
  isLoading: boolean;
  isError: boolean;
  isOutlineLoading: boolean;
  isUpdatingOutline: boolean;
  outlineFeedback: string | null;
  onTabChange: (tab: DetailTab) => void;
  onApplyOutline: (operations: MaterialOutlineOperation[]) => void;
  onOpenCourse: (courseId: string) => void;
}) {
  const tabs: Array<{ id: DetailTab; label: string }> = [
    { id: "overview", label: "概览" },
    { id: "outline", label: "目录" },
    { id: "chunks", label: "切片" },
    { id: "courses", label: "关联课程" }
  ];
  if (props.isLoading) return <p className="library-drawer-state">正在读取资料详情。</p>;
  if (props.isError || !props.material) return <InlineFeedback message="资料详情读取失败，请稍后重试。" tone="warning" />;
  const material = props.material;
  const quality = material.quality_summary ?? {};
  return (
    <>
      <div className="library-drawer-tabs library-detail-tabs" role="tablist" aria-label="资料详情分类">
        {tabs.map((tab) => <button key={tab.id} role="tab" type="button" aria-selected={props.tab === tab.id} onClick={() => props.onTabChange(tab.id)}>{tab.label}</button>)}
      </div>
      {props.tab === "overview" ? (
        <section className="library-detail-overview" role="tabpanel" aria-label="资料概览">
          {props.activeJob ? (
            <InlineFeedback
              message={`${props.activeJob.label}（${props.activeJob.progress_percent}%）`}
              tone="warning"
            />
          ) : null}
          <div className="library-detail-metrics">
            <div><span>结构状态</span><strong>{props.activeJob?.label ?? (material.outline_confirmed ? "目录已确认" : material.ingestion_status === "awaiting_confirmation" ? "等待确认" : props.fallbackMaterial?.detail ?? material.detail)}</strong></div>
            <div><span>解析质量</span><strong>{props.activeJob ? `重新解析中（上次${quality.passed ? "通过" : "未通过"}）` : quality.passed ? "通过" : material.ingestion_status === "legacy" ? "旧版待重建" : "未通过或处理中"}</strong></div>
            <div><span>章节</span><strong>{quality.section_count ?? material.section_count ?? 0}</strong></div>
            <div><span>切片</span><strong>{quality.chunk_count ?? material.chunk_count ?? 0}</strong></div>
            <div><span>页数</span><strong>{quality.page_count ?? material.page_count ?? "—"}</strong></div>
            <div><span>可读页面</span><strong>{typeof quality.readable_page_ratio === "number" ? `${Math.round(quality.readable_page_ratio * 100)}%` : "—"}</strong></div>
          </div>
          {!props.activeJob ? (quality.warnings ?? []).map((warning) => <InlineFeedback key={warning} message={warning} tone="warning" />) : null}
          {!props.activeJob && (quality.risk_flags ?? []).length > 0 ? <InlineFeedback message={`质量门禁未通过：${quality.risk_flags?.join("、")}`} tone="warning" /> : null}
          <section className="library-preview-block">
            <h3>内容短预览</h3>
            <p>{material.extracted_text_preview || "当前资料没有可展示的文本预览。"}</p>
          </section>
          {material.agent_trace_id ? <AgentTraceDisclosure traceId={material.agent_trace_id} label="查看资料处理轨迹" /> : null}
        </section>
      ) : null}
      {props.tab === "outline" ? (
        <section className="library-outline-editor" role="tabpanel" aria-label="资料目录">
          {props.isOutlineLoading ? <p className="library-drawer-state">正在读取目录结构。</p> : null}
          {!props.isOutlineLoading && !props.outline ? <p className="library-drawer-state">这份资料尚未生成精细目录，可先执行重新解析。</p> : null}
          <InlineFeedback message={props.outlineFeedback} tone={props.outline?.confirmed ? "success" : "warning"} />
          {props.outline ? (
            <>
              <div className="library-outline-summary">
                <span>版本 {props.outline.version}</span>
                <span>{props.outline.sections.filter((section) => section.included).length} 个章节纳入课程</span>
                <span>{props.outline.confirmed ? "已确认" : "修改后需要重新确认"}</span>
              </div>
              {props.outline.sections.every((section) => !section.included) ? (
                <InlineFeedback message="当前没有章节纳入课程，请勾选至少一个包含正文的章节。" tone="warning" />
              ) : null}
              {props.outline.sections.map((section, index) => (
                <OutlineSectionEditor
                  key={`${props.outline?.material_id}-${props.outline?.version}-${section.id}`}
                  section={section}
                  previousSection={props.outline?.sections[index - 1] ?? null}
                  disabled={props.isUpdatingOutline}
                  onApply={props.onApplyOutline}
                />
              ))}
            </>
          ) : null}
        </section>
      ) : null}
      {props.tab === "chunks" ? (
        <MaterialChunkInspector
          outline={props.outline}
          isLoading={props.isOutlineLoading}
          disabled={props.isUpdatingOutline}
          onApply={props.onApplyOutline}
        />
      ) : null}
      {props.tab === "courses" ? (
        <section className="library-linked-courses" role="tabpanel" aria-label="关联课程">
          {(material.linked_courses ?? []).length === 0 ? <p className="library-drawer-state">这份资料尚未关联课程。</p> : null}
          {(material.linked_courses ?? []).map((course) => (
            <button key={course.id} type="button" onClick={() => props.onOpenCourse(course.id)}>
              <BookOpen size={18} weight="duotone" aria-hidden="true" />
              <span><strong>{course.title}</strong><small>{course.usage_type === "reference" ? "课程参考资料" : course.usage_type}</small></span>
            </button>
          ))}
        </section>
      ) : null}
    </>
  );
}

function OutlineSectionEditor({ section, previousSection, disabled, onApply }: {
  section: MaterialOutlineSection;
  previousSection: MaterialOutlineSection | null;
  disabled: boolean;
  onApply: (operations: MaterialOutlineOperation[]) => void;
}) {
  const [title, setTitle] = useState(section.title);
  const pageLabel = section.start_page
    ? `第 ${section.start_page}${section.end_page && section.end_page !== section.start_page ? `–${section.end_page}` : ""} 页`
    : "未标注页码";
  return (
    <article className={section.included ? "library-outline-row" : "library-outline-row excluded"}>
      <label className="library-outline-toggle">
        <input
          type="checkbox"
          checked={section.included}
          disabled={disabled}
          onChange={(event) => onApply([{ type: "include", section_id: section.id, included: event.target.checked }])}
        />
        <span>纳入课程</span>
      </label>
      <div className="library-outline-main" style={{ paddingInlineStart: `${Math.min(5, Math.max(0, section.level - 1)) * 14}px` }}>
        <input aria-label={`${section.title}章节名称`} value={title} disabled={disabled} onChange={(event) => setTitle(event.target.value)} />
        <small>{pageLabel} · {section.chunk_indexes.length} 个切片 · 识别可信度 {Math.round(section.confidence * 100)}%</small>
      </div>
      <div className="library-outline-actions">
        <button type="button" disabled={disabled || title.trim() === section.title || !title.trim()} onClick={() => onApply([{ type: "rename", section_id: section.id, title: title.trim() }])}>保存名称</button>
        {previousSection ? (
          <button type="button" disabled={disabled} onClick={() => onApply([{ type: "merge", section_ids: [previousSection.id, section.id], title: previousSection.title }])}>并入上一节</button>
        ) : null}
      </div>
    </article>
  );
}

function MaterialChunkInspector({ outline, isLoading, disabled, onApply }: {
  outline: MaterialOutline | null;
  isLoading: boolean;
  disabled: boolean;
  onApply: (operations: MaterialOutlineOperation[]) => void;
}) {
  const [splitChunkId, setSplitChunkId] = useState<string | null>(null);
  const [splitTitle, setSplitTitle] = useState("");
  if (isLoading) return <p className="library-drawer-state">正在读取正文切片。</p>;
  if (!outline) return <p className="library-drawer-state">完成精细解析后可检查真实切片。</p>;
  return (
    <section className="library-chunk-inspector" role="tabpanel" aria-label="资料切片">
      {outline.chunks.length === 0 ? <p className="library-drawer-state">当前目录没有正文切片。</p> : null}
      {outline.chunks.map((chunk) => {
        const section = outline.sections.find((item) => item.id === chunk.section_id);
        const firstChunk = section?.chunk_indexes[0] === chunk.chunk_index;
        const pageLabel = chunk.start_page
          ? `第 ${chunk.start_page}${chunk.end_page && chunk.end_page !== chunk.start_page ? `–${chunk.end_page}` : ""} 页`
          : "未标注页码";
        return (
          <article key={chunk.id}>
            <header><strong>{chunk.section_path.join(" / ") || section?.title || "正文"}</strong><span>{pageLabel} · 切片 {chunk.chunk_index + 1}</span></header>
            <p>{chunk.content}</p>
            {!firstChunk ? (
              splitChunkId === chunk.id ? (
                <div className="library-chunk-split">
                  <input aria-label="新章节名称" placeholder="输入拆分后的新章节名称" value={splitTitle} onChange={(event) => setSplitTitle(event.target.value)} />
                  <button type="button" disabled={disabled || !splitTitle.trim()} onClick={() => {
                    if (!section) return;
                    onApply([{ type: "split", section_id: section.id, chunk_index: chunk.chunk_index, title: splitTitle.trim() }]);
                    setSplitChunkId(null);
                    setSplitTitle("");
                  }}>确认拆分</button>
                  <button type="button" onClick={() => setSplitChunkId(null)}>取消</button>
                </div>
              ) : <button className="library-chunk-split-trigger" type="button" disabled={disabled} onClick={() => setSplitChunkId(chunk.id)}>从此处拆分章节</button>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}

function ComparisonPanel(props: {
  view: CompareView;
  tab: CompareTab;
  selectedMaterials: MaterialListItem[];
  sharedCourses: ApiCourseSummary[];
  selectedCourseId: string;
  result: MaterialComparisonResult | null;
  feedback: string | null;
  isLoading: boolean;
  isError: boolean;
  onCourseChange: (courseId: string) => void;
  onTabChange: (tab: CompareTab) => void;
  onBackToSetup: () => void;
}) {
  if (props.view === "setup") {
    return (
      <section className="library-compare-setup">
        <div className="library-selected-materials">
          <h3>已选资料</h3>
          {props.selectedMaterials.length === 0 ? <p>在左侧文件列表中选择资料。</p> : props.selectedMaterials.map((material) => (
            <div key={material.id}><span>{material.extension}</span><strong>{material.title}</strong></div>
          ))}
        </div>
        <label className="library-drawer-field">
          <span>共同课程</span>
          <select aria-label="对比课程" value={props.selectedCourseId} disabled={props.sharedCourses.length === 0} onChange={(event) => props.onCourseChange(event.target.value)}>
            {props.sharedCourses.length === 0 ? <option value="">等待共同课程</option> : null}
            {props.sharedCourses.length > 1 ? <option value="">请选择课程</option> : null}
            {props.sharedCourses.map((course) => <option key={course.id} value={course.id}>{course.title}</option>)}
          </select>
        </label>
        {props.selectedMaterials.length >= 2 && props.sharedCourses.length === 0 ? <InlineFeedback message="所选资料不属于同一课程，请调整选择。" tone="warning" /> : null}
        <InlineFeedback message={props.feedback} tone="warning" />
      </section>
    );
  }

  if (props.view === "recent") {
    return (
      <>
        <label className="library-drawer-field recent-course-select">
          <span>查看课程</span>
          <select aria-label="最近对比课程" value={props.selectedCourseId} onChange={(event) => props.onCourseChange(event.target.value)}>
            {props.sharedCourses.map((course) => <option key={course.id} value={course.id}>{course.title}</option>)}
          </select>
        </label>
        {props.isLoading ? <p className="library-drawer-state">正在读取最近对比。</p> : null}
        {props.isError ? <InlineFeedback message="最近对比读取失败，请稍后重试。" tone="warning" /> : null}
        {!props.isLoading && !props.isError && !props.result ? (
          <div className="library-recent-empty"><Folders size={28} weight="duotone" /><strong>这门课程还没有资料对比</strong><button type="button" onClick={props.onBackToSetup}>选择资料开始对比</button></div>
        ) : null}
        {props.result ? <ComparisonResult result={props.result} tab={props.tab} onTabChange={props.onTabChange} onBackToSetup={props.onBackToSetup} /> : null}
      </>
    );
  }

  return props.result ? <ComparisonResult result={props.result} tab={props.tab} onTabChange={props.onTabChange} onBackToSetup={props.onBackToSetup} /> : null;
}

function ComparisonResult({ result, tab, onTabChange, onBackToSetup }: {
  result: MaterialComparisonResult;
  tab: CompareTab;
  onTabChange: (tab: CompareTab) => void;
  onBackToSetup: () => void;
}) {
  const tabs: Array<{ id: CompareTab; label: string }> = [
    { id: "common", label: "共同重点" },
    { id: "exam", label: "考点" },
    { id: "differences", label: "差异遗漏" },
    { id: "sources", label: "来源与轨迹" }
  ];
  return (
    <section className="library-comparison-result">
      <header>
        <strong>{result.summary.message}</strong>
        <span>{result.summary.comparable_material_count} 份可比较 · {result.summary.matched_concept_count} 个命中点 · {result.summary.citation_count} 条引用</span>
        <small>{result.generation_mode === "model_enhanced" ? "模型增强" : "规则底稿"} · {result.review_mode === "model_and_rules" ? "模型与规则审核" : "规则审核"}</small>
      </header>
      {(result.warnings ?? []).map((warning) => <InlineFeedback key={warning} message={warning} tone="warning" />)}
      <div className="library-drawer-tabs" role="tablist" aria-label="资料对比结果分类">
        {tabs.map((item) => <button key={item.id} role="tab" type="button" aria-selected={tab === item.id} onClick={() => onTabChange(item.id)}>{item.label}</button>)}
      </div>
      {tab === "common" ? <><ComparisonPointList title="重复重点" points={result.repeated_concepts} /><ComparisonPointList title="优先复习顺序" points={result.priority_order} /></> : null}
      {tab === "exam" ? <ComparisonPointList title="疑似考点" points={result.exam_likely_points} /> : null}
      {tab === "differences" ? <><ComparisonPointList title="单资料独有点" points={result.materials_only_points} /><ComparisonPointList title="试题独有点" points={result.questions_only_points} /><ComparisonPointList title="遗漏复习点" points={result.missing_review_points} /></> : null}
      {tab === "sources" ? (
        <section className="library-comparison-sources" role="tabpanel" aria-label="对比来源与轨迹">
          {result.citations.length === 0 ? <p className="library-drawer-state">暂无引用。</p> : result.citations.map((citation) => (
            <article key={citation.id}><strong>{citation.source_title}</strong><small>{citation.section_title ?? "未标注章节"}{citation.page_number ? ` · 第 ${citation.page_number} 页` : ""}</small><p>{citation.excerpt}</p></article>
          ))}
          <AgentTraceDisclosure traceId={result.agent_trace_id} label="查看 MaterialComparisonGraph" />
        </section>
      ) : null}
      <button className="library-compare-again" type="button" onClick={onBackToSetup}>选择其他资料重新对比</button>
    </section>
  );
}
