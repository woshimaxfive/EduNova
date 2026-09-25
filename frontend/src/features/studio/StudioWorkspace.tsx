import { ArrowClockwise, CheckCircle, X } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";
import { CourseMentorDock } from "../../components/course-space/CourseMentorDock";
import { InlineFeedback } from "../../components/feedback/InlineFeedback";
import { NextLearningAction } from "../../components/learning/NextLearningAction";
import { ConfirmDialog } from "../../components/primitives/Dialog";
import { StudioArtifactCanvas } from "../../components/studio/StudioArtifactCanvas";
import { StudioDrawer } from "../../components/studio/StudioDrawer";
import { StudioResourceLibrary } from "../../components/studio/StudioResourceLibrary";
import { StudioWorkspaceToolbar } from "../../components/studio/StudioWorkspaceToolbar";
import {
  StudioRegenerateDialog,
  StudioVersionCompareDialog
} from "../../components/studio/StudioVersionDialogs";
import { PageFrame } from "../../pages/PageFrame";
import { useStudioWorkspaceController } from "./useStudioWorkspaceController";

export function StudioWorkspace() {
  const {
    artifact,
    course,
    deletion,
    dialogs,
    drawer,
    generation,
    library,
    mentor,
    nextAction,
    path,
    resourceFamilies,
    selectResource,
    selectedResource,
    selectedVersions
  } = useStudioWorkspaceController();

  return (
    <>
      <PageFrame title="资源工坊" titleMode="sr-only" variant="wide-workspace">
        <section className="studio-workspace" aria-label="资源成果工作台">
          <StudioWorkspaceToolbar
            courses={course.items}
            courseId={course.id}
            resourceCount={resourceFamilies.length}
            selectedResource={selectedResource}
            isGenerating={generation.isGenerating}
            onCourseChange={course.change}
            onOpenGenerate={drawer.openGenerate}
            onOpenDetails={drawer.openDetails}
            onRegenerate={dialogs.openRegenerate}
          />

          {generation.showCompactJob && generation.job ? (
            <section className="studio-job-strip" role="status" aria-label="资源生成进度">
              <ArrowClockwise className="spinning" size={17} aria-hidden="true" />
              <div>
                <strong>{generation.job.label}</strong>
                <span>{generation.job.stage} · {generation.job.progress_percent}%</span>
              </div>
              <progress max="100" value={generation.job.progress_percent}>
                {generation.job.progress_percent}%
              </progress>
              <button type="button" onClick={() => void generation.cancelJob(generation.job?.job_id ?? "")}>
                <X size={15} />
                <span>取消</span>
              </button>
            </section>
          ) : null}
          {generation.feedback && drawer.mode === null ? (
            <InlineFeedback
              message={generation.feedback}
              tone={generation.feedbackTone}
              className="studio-workspace-feedback"
            />
          ) : null}
          {path.pathTaskId ? (
            <section className="studio-job-strip" aria-label="路径任务">
              <CheckCircle size={17} weight="duotone" aria-hidden="true" />
              <div>
                <strong>
                  本节已完成 {path.pathTask?.learning_bundle?.completed_count ?? 0}/
                  {path.pathTask?.learning_bundle?.ready_count ?? 0} 个可学习资源
                </strong>
                <span>逐项学习资源，最后返回路径确认完成本节。</span>
              </div>
              {path.selectedBundleItem?.learning_status === "completed" && path.nextBundleItem?.resource_id ? (
                <button type="button" onClick={() => selectResource(path.nextBundleItem?.resource_id as string)}>
                  学习下一项
                </button>
              ) : (
                <Link to={`${PATHS.path}?course_id=${course.id ?? ""}`}>返回本节学习安排</Link>
              )}
            </section>
          ) : (
            <NextLearningAction
              action={nextAction.value}
              isLoading={nextAction.isLoading}
              error={nextAction.error}
              compact
            />
          )}

          <div className="studio-workspace-body">
            <StudioResourceLibrary
              hasCourse={course.id !== null}
              families={library.families}
              selectedResourceId={selectedResource?.id ?? null}
              search={library.search}
              typeFilter={library.typeFilter}
              isLoading={library.isLoading}
              onSearchChange={library.changeSearch}
              onTypeFilterChange={library.changeTypeFilter}
              onSelectResource={library.selectResource}
              onRequestDelete={deletion.setPending}
            />
            <StudioArtifactCanvas
              resource={artifact.resource}
              hasCourse={course.id !== null}
              courseTitle={course.selected?.title ?? null}
              knowledgePointTitle={artifact.knowledgePointTitle}
              isLoading={artifact.isLoading}
              isError={artifact.dataError}
              onCreate={drawer.openGenerate}
              onRetry={artifact.retry}
              versions={artifact.versions}
              onSelectVersion={selectResource}
              onCompareVersions={dialogs.openCompare}
              onRegenerate={dialogs.openRegenerate}
            />
          </div>
        </section>
      </PageFrame>

      <StudioDrawer
        mode={drawer.mode}
        detailTab={drawer.detailTab}
        courses={course.items}
        courseId={course.id}
        knowledgePoints={course.knowledgePoints}
        knowledgePointId={course.knowledgePointId}
        selectedTypes={drawer.selectedTypes}
        learningGoal={drawer.learningGoal}
        difficulty={drawer.difficulty}
        resource={selectedResource}
        qualityScores={drawer.qualityScores}
        traceEvents={drawer.traceEvents}
        traceLoading={drawer.traceLoading}
        traceError={drawer.traceError}
        traceId={drawer.traceId}
        job={generation.job}
        feedback={drawer.feedback}
        canGenerate={drawer.canGenerate}
        isGenerating={drawer.isGenerating}
        onClose={drawer.close}
        onDetailTabChange={drawer.changeDetailTab}
        onCourseChange={course.change}
        onKnowledgePointChange={course.changeKnowledgePoint}
        onToggleType={drawer.toggleResourceType}
        onLearningGoalChange={drawer.changeLearningGoal}
        onDifficultyChange={drawer.changeDifficulty}
        onGenerate={drawer.generate}
        onCancelJob={() => generation.job ? void drawer.cancelJob(generation.job.job_id) : undefined}
        onRetryJob={() => void drawer.retryJob()}
        onDeleteJob={() => void drawer.deleteJob()}
      />

      {course.id !== null && selectedResource ? (
        <CourseMentorDock
          open={mentor.open}
          courseTitle={course.selected?.title ?? "当前课程"}
          pointTitle={artifact.knowledgePointTitle}
          resourceTitle={selectedResource.title}
          masteryScore={mentor.masteryScore}
          weaknessCount={mentor.weaknessCount}
          recommendation={nextAction.value ?? null}
          messages={mentor.controller.messages}
          prompt={mentor.controller.prompt}
          isSending={mentor.controller.isSending}
          feedback={mentor.controller.feedback}
          isListening={mentor.controller.speech.isListening}
          isTranscribing={mentor.controller.speech.isTranscribing}
          isSpeaking={Boolean(mentor.controller.speech.activeSpeechId)}
          isSpeechPaused={mentor.controller.speech.isSpeechPaused}
          onOpenChange={mentor.changeOpen}
          onPromptChange={mentor.controller.setPrompt}
          onPromptKeyDown={mentor.controller.onPromptKeyDown}
          onSend={() => void mentor.controller.send()}
          onToggleListening={() => void mentor.controller.speech.toggleListening()}
          onReadLatest={mentor.controller.readLatest}
          onPauseOrResume={mentor.controller.speech.pauseOrResumeSpeaking}
          onStopSpeaking={mentor.controller.speech.stopSpeaking}
        />
      ) : null}

      {dialogs.regenerateOpen && selectedResource ? (
        <StudioRegenerateDialog
          resource={selectedResource}
          isSubmitting={generation.mutationPending || generation.isGenerating}
          onClose={dialogs.closeRegenerate}
          onChoose={generation.regenerate}
        />
      ) : null}

      {dialogs.compareOpen && selectedResource && selectedVersions.length > 1 ? (
        <StudioVersionCompareDialog
          key={`${selectedResource.id}-${selectedVersions.map((resource) => resource.id).join("-")}`}
          current={selectedResource}
          versions={selectedVersions}
          onClose={dialogs.closeCompare}
        />
      ) : null}

      <ConfirmDialog
        open={deletion.pending !== null}
        title="删除资源"
        description={`删除“${deletion.pending?.title ?? "这个资源"}”后不可恢复。`}
        confirmLabel={deletion.isDeleting ? "正在删除" : "删除资源"}
        layerClassName="destructive-confirm-layer"
        onOpenChange={(open) => { if (!open && !deletion.isDeleting) deletion.cancel(); }}
        onConfirm={() => void deletion.confirm()}
      >
        <section>
          <h2>删除资源</h2>
          <p>删除“{deletion.pending?.title}”后不可恢复。</p>
          <div>
            <button type="button" disabled={deletion.isDeleting} onClick={deletion.cancel}>取消</button>
            <button
              className="danger"
              type="button"
              disabled={deletion.isDeleting}
              onClick={() => void deletion.confirm()}
            >
              {deletion.isDeleting ? "正在删除" : "删除资源"}
            </button>
          </div>
        </section>
      </ConfirmDialog>
    </>
  );
}
