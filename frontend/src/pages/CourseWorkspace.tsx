import {
  ArrowRight,
  ChartLineUp,
  ListChecks,
  MapTrifold,
  Microphone
} from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS, buildCoursePathWorkspacePath, buildCoursePracticeWorkspacePath, buildCourseReportsWorkspacePath } from "../app/routePaths";
import { CourseAnswerDetailPanel } from "../components/course-space/CourseAnswerDetailPanel";
import { CourseAssistantTurn } from "../components/course-space/CourseAssistantTurn";
import { CourseClosedLoopActions } from "../components/course-space/CourseClosedLoopActions";
import { CourseContentView } from "../components/course-space/CourseContentView";
import { CourseInlineResourcePanel } from "../components/course-space/CourseInlineResourcePanel";
import { CourseProgressDrawer } from "../components/course-space/CourseProgressDrawer";
import { CourseWorkspaceHeader } from "../components/course-space/CourseWorkspaceHeader";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { NextLearningAction } from "../components/learning/NextLearningAction";
import { TutorResponseProgress } from "../components/tutor/TutorResponseProgress";
import { findBestCitationKnowledgePoint } from "../features/course-space/courseRecommendation";
import {
  buildCourseClosureHref,
  findQuestionForAssistant,
  sanitizeCourseAnswerContent
} from "../features/course-space/courseConversation";
import { SecureTutorImages, TutorImagePicker } from "../features/tutor/TutorImageAttachments";
import "../styles/course-space.css";
import { useCourseWorkspaceController } from "../features/course-space/useCourseWorkspaceController";

export function CourseWorkspace() {
  const controller = useCourseWorkspaceController();
  const {
    activeTurnDetail,
    activeWeaknessCount,
    agentTraceEvents,
    agentTraceQuery,
    apiCourse,
    apiKnowledgePoints,
    cancelJob,
    changeCourseContentView,
    changeCourseMode,
    changeGraphChapter,
    changeGraphScope,
    changeKnowledgeDetail,
    changeStudyAssistant,
    courseAnswerProgress,
    courseChatEndRef,
    courseContentView,
    courseFeedback,
    courseLoopSummary,
    courseMode,
    coursePrompt,
    courseQuestionInputRef,
    courseResourceFeedback,
    courseResourceMutation,
    courseStarterQuestions,
    courseStreamProgress,
    courseStudySteps,
    courseSummary,
    createCourseConversation,
    currentPathTaskPointId,
    deleteCourseConversation,
    displayedCourseMessages,
    fallbackCourse,
    generateSuggestedCourseResources,
    generatedResources,
    graphChapter,
    graphScope,
    handleCourseComposerKeyDown,
    handledResourceJobId,
    hasDisplayedCourseMessages,
    hasRealCourseId,
    imageDraft,
    isGeneratingCourseResources,
    isHistoryCollapsed,
    isKnowledgeDetailOpen,
    isProgressDrawerOpen,
    isProgressSyncing,
    isSearchingCourse,
    isStudyAssistantOpen,
    knowledgePointContentQuery,
    knowledgePointCount,
    latestAgentTraceId,
    latestAssistantWithRetrieval,
    latestGeneratedResources,
    learningState,
    learningStateQuery,
    masteryMapQuery,
    materialCount,
    navigate,
    numericCourseId,
    openCitationStudy,
    openCourseProgress,
    openKnowledgeStudy,
    persistedCourseAnswerProgress,
    progressSyncWarning,
    recommendation,
    renameCourseConversation,
    resourceJob,
    retryJob,
    runRecommendedAction,
    searchParams,
    selectCourseConversation,
    selectedCitation,
    selectedCourseResourceTypes,
    selectedCourseSessionId,
    selectedKnowledgePoint,
    sendCourseQuestion,
    setCoursePrompt,
    setIsHistoryCollapsed,
    setIsProgressDrawerOpen,
    setResourceJobId,
    sidebarConversations,
    speech,
    submitCourseResourceGeneration,
    syncCourseProgress,
    toggleCourseResourceType,
    toggleReadMessage,
    toggleTurnPanel,
    updateWeaknessReviewItem,
    updatingWeaknessItemId,
    weaknessFeedback,
    weaknessItems,
    weaknessSummary,
  } = controller;

  return (
    <LearningSpaceShell hideTopNavigation mainClassName="course-learning-shell" surfaceClassName="course-learning-surface">
      <section className={isHistoryCollapsed ? "app-workspace-layout course-workspace-layout history-collapsed" : "app-workspace-layout course-workspace-layout"}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <AppSidebar
          isCollapsed={isHistoryCollapsed}
          conversations={sidebarConversations}
          activeConversationId={hasRealCourseId ? selectedCourseSessionId : null}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onNewChat={() => void createCourseConversation()}
          onSelectConversation={(conversation) =>
            hasRealCourseId ? void selectCourseConversation(conversation.id) : undefined
          }
          onRenameConversation={renameCourseConversation}
          onDeleteConversation={deleteCourseConversation}
        />
        <section className="route-main-surface course-route-surface">
          <div className="course-space">
            <CourseWorkspaceHeader
              title={courseSummary.title}
              progressPercent={courseSummary.progressPercent}
              materialCount={materialCount}
              knowledgePointCount={knowledgePointCount}
              weaknessCount={activeWeaknessCount}
              mode={courseMode}
              onModeChange={changeCourseMode}
              onOpenProgress={openCourseProgress}
            />

            {courseMode === "chat" ? (
              <section className="course-chat-panel course-chat-mode" role="region" aria-label="课程对话空间">
                <div className="course-chat-scroll-area" aria-label="课程学习内容">
                  {hasDisplayedCourseMessages ? (
                    <section className="course-message-stack" aria-label="课程即时对话">
                      {displayedCourseMessages.map((message, index) => {
                        if (message.role === "user") {
                          return <article className="course-message user" key={message.id}><SecureTutorImages attachments={message.attachments ?? []} /><p>{message.content}</p></article>;
                        }

                        const isPersisted = !message.id.startsWith("course-assistant-stream-");
                        const turnPanel = activeTurnDetail?.messageId === message.id ? activeTurnDetail.panel : null;
                        const question = findQuestionForAssistant(displayedCourseMessages, index);
                        const citations = message.citations ?? [];
                        const citationKnowledgePointId = findBestCitationKnowledgePoint(citations);
                        const isLatestAssistant = !displayedCourseMessages.slice(index + 1).some((item) => item.role === "assistant");
                        const turnKnowledgePointId = recommendation.knowledge_point_id ?? citationKnowledgePointId;
                        const practiceHref = buildCourseClosureHref(
                          PATHS.practice,
                          numericCourseId,
                          selectedCourseSessionId,
                          message.id,
                          turnKnowledgePointId
                        );
                        const reportHref = buildCourseClosureHref(
                          PATHS.reports,
                          numericCourseId,
                          selectedCourseSessionId,
                          message.id
                        );
                        const pathHref = buildCourseClosureHref(
                          PATHS.path,
                          numericCourseId,
                          selectedCourseSessionId,
                          message.id,
                          turnKnowledgePointId
                        );
                        const effectiveTraceId = message.traceId
                          ?? (message.id === latestAssistantWithRetrieval?.id ? latestAgentTraceId : null);
                        const detail = turnPanel ? (
                          <>
                            {turnPanel === "resources" ? (
                              <CourseInlineResourcePanel
                                selectedTypes={selectedCourseResourceTypes}
                                isGenerating={courseResourceMutation.isPending || isGeneratingCourseResources}
                                feedback={courseResourceFeedback}
                                generatedCount={generatedResources.length}
                                generatedResources={latestGeneratedResources}
                                job={resourceJob}
                                onCancelJob={() => resourceJob && void cancelJob(resourceJob.job_id)}
                                onRetryJob={() => resourceJob && void retryJob(resourceJob.job_id).then((job) => {
                                  handledResourceJobId.current = null;
                                  setResourceJobId(job.job_id);
                                })}
                                onToggleType={toggleCourseResourceType}
                                onGenerate={submitCourseResourceGeneration}
                              />
                            ) : null}
                            <CourseAnswerDetailPanel
                              activePanel={turnPanel}
                              courseId={hasRealCourseId ? numericCourseId : null}
                              citations={citations}
                              supplementalSources={message.supplementalSources ?? []}
                              hasRealCourse={Boolean(apiCourse)}
                              hasSearched
                              pathSummary={learningState?.path_summary ?? null}
                              pathHref={pathHref}
                              agentTraceId={effectiveTraceId}
                              agentTraceEvents={agentTraceEvents}
                              agentTraceSummary={agentTraceQuery.data?.data.summary ?? null}
                              isAgentTraceLoading={agentTraceQuery.isPending && agentTraceQuery.fetchStatus !== "idle"}
                              isAgentTraceError={agentTraceQuery.isError}
                              onOpenCitation={openCitationStudy}
                            />
                          </>
                        ) : null;

                        return (
                          <CourseAssistantTurn
                            key={message.id}
                            messageId={message.id}
                            content={sanitizeCourseAnswerContent(message.content)}
                            progress={!isPersisted && courseStreamProgress ? (
                              <TutorResponseProgress state={courseStreamProgress} />
                            ) : isPersisted && (courseAnswerProgress[message.id] ?? persistedCourseAnswerProgress[message.id]) ? (
                              <TutorResponseProgress
                                state={courseAnswerProgress[message.id] ?? persistedCourseAnswerProgress[message.id]}
                                completed
                                durationMs={(courseAnswerProgress[message.id] ?? persistedCourseAnswerProgress[message.id]).durationMs}
                                storageKey={`course-message:${message.id}`}
                              />
                            ) : undefined}
                            actions={isPersisted && message.content.trim() ? (
                              <CourseClosedLoopActions
                                recommendation={isLatestAssistant ? recommendation : null}
                                citationCount={citations.length}
                                resourceCount={generatedResources.length}
                                hasTrace={Boolean(effectiveTraceId)}
                                activePanel={turnPanel}
                                isSpeaking={speech.activeSpeechId === message.id}
                                pathHref={pathHref}
                                practiceHref={practiceHref}
                                reportHref={reportHref}
                                onRecommendedAction={() => runRecommendedAction(message.id, citations, recommendation)}
                                onRead={() => toggleReadMessage(message)}
                                onOpenCitations={() => toggleTurnPanel(message.id, "citations", question, citations)}
                                onOpenResources={() => toggleTurnPanel(message.id, "resources", question, citations)}
                                onOpenWhy={() => toggleTurnPanel(message.id, "why", question, citations)}
                                onOpenTrace={() => toggleTurnPanel(message.id, "thinking", question, citations)}
                              />
                            ) : undefined}
                            detail={
                              <>
                                {message.resourceJobs?.map((job) => (
                                  <section className="tutor-resource-card" key={job.job_id} aria-label="对话生成资源">
                                    <strong>{job.status === "completed" ? "已生成学习资源" : job.status === "failed" ? "资源生成失败" : job.label}</strong>
                                    {job.resources.map((resource) => <Link key={resource.id} to={`${PATHS.studio}?course_id=${numericCourseId}&resource_id=${resource.id}`}>{resource.title}</Link>)}
                                    {job.error_message ? <small>{job.error_message}</small> : null}
                                  </section>
                                ))}
                                {message.resourceProposal && message.resourceProposal.action !== "none" && !(message.resourceJobs?.length) ? (
                                  <section className="tutor-resource-card" aria-label="学习资源建议">
                                    <strong>{message.resourceProposal.action === "generate" ? "准备生成学习资源" : "建议补充学习资源"}</strong>
                                    <small>{message.resourceProposal.reason_summary}</small>
                                    <button type="button" onClick={() => void generateSuggestedCourseResources(message)}>生成建议资源</button>
                                  </section>
                                ) : null}
                                {detail}
                              </>
                            }
                          />
                        );
                      })}
                    </section>
                  ) : (
                    <article className="course-answer course-start-panel" role="region" aria-label="课程提问引导">
                      <h2>可以从这些问题开始</h2>
                      <div className="course-question-suggestions" aria-label="推荐问题">
                        {courseStarterQuestions.map((question) => (
                          <button type="button" key={question} onClick={() => setCoursePrompt(question)}>
                            {question}
                          </button>
                        ))}
                      </div>
                    </article>
                  )}

                  {!hasDisplayedCourseMessages && hasRealCourseId ? (
                    <>
                      <NextLearningAction action={recommendation} compact />
                      <nav className="course-action-links" aria-label="课程辅助入口">
                        <Link to={buildCoursePathWorkspacePath(numericCourseId)}>
                          <MapTrifold size={17} weight="duotone" aria-hidden="true" />
                          <span>学习路径</span>
                        </Link>
                        <Link to={buildCoursePracticeWorkspacePath(numericCourseId)}>
                          <ListChecks size={17} weight="duotone" aria-hidden="true" />
                          <span>自由练习</span>
                        </Link>
                        <Link to={buildCourseReportsWorkspacePath(numericCourseId)}>
                          <ChartLineUp size={17} weight="duotone" aria-hidden="true" />
                          <span>查看报告</span>
                        </Link>
                      </nav>
                    </>
                  ) : null}
                  <div className="course-chat-end" ref={courseChatEndRef} aria-hidden="true" />
                </div>

                <div className="course-composer" role="region" aria-label="课程输入区">
                  <label htmlFor="course-question-input">课程问题输入</label>
                  <div className="conversation-composer course-conversation-composer">
                    <TutorImagePicker draft={imageDraft} compact display="previews" />
                    <textarea
                      ref={courseQuestionInputRef}
                      id="course-question-input"
                      rows={2}
                      value={coursePrompt}
                      onChange={(event) => setCoursePrompt(event.target.value)}
                      onKeyDown={handleCourseComposerKeyDown}
                      onPaste={(event) => {
                        const files = Array.from(event.clipboardData.files).filter((file) => file.type.startsWith("image/"));
                        if (files.length) { event.preventDefault(); void imageDraft.addFiles(files); }
                      }}
                      onDrop={(event) => {
                        const files = Array.from(event.dataTransfer.files).filter((file) => file.type.startsWith("image/"));
                        if (files.length) { event.preventDefault(); void imageDraft.addFiles(files); }
                      }}
                      onDragOver={(event) => event.preventDefault()}
                      placeholder="继续问这门课，例如：给我生成监督学习 10 分钟复习路线"
                    />
                    <div className="composer-actions">
                      <div className="composer-toolbar" aria-label="输入工具">
                        <TutorImagePicker draft={imageDraft} compact display="controls" />
                      </div>
                      <div className="composer-submit-row">
                        <button
                          className={speech.isListening ? "voice-button active" : "voice-button"}
                          type="button"
                          title={speech.isTranscribing ? "正在识别" : speech.isListening ? "结束录音" : "语音输入"}
                          aria-label="语音输入"
                          aria-pressed={speech.isListening}
                          disabled={speech.isTranscribing}
                          onClick={speech.toggleListening}
                        >
                          <Microphone size={18} weight="duotone" aria-hidden="true" />
                        </button>
                        <button className="ask-button" type="button" title={isSearchingCourse ? "正在回答" : "发送"} aria-label="发送" disabled={isSearchingCourse} onClick={() => void sendCourseQuestion()}>
                          <ArrowRight size={18} weight="bold" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                  </div>
                  <InlineFeedback message={courseFeedback} tone="warning" className="course-inline-feedback" />
                </div>
              </section>
            ) : (
              <CourseContentView
                courseId={numericCourseId}
                courseTitle={courseSummary.title}
                courseSessionId={selectedCourseSessionId}
                points={apiKnowledgePoints}
                masteryPoints={masteryMapQuery.data?.data.points ?? []}
                selectedPoint={selectedKnowledgePoint}
                content={knowledgePointContentQuery.data?.data ?? null}
                contentPending={knowledgePointContentQuery.isPending && knowledgePointContentQuery.fetchStatus !== "idle"}
                contentError={knowledgePointContentQuery.isError}
                selectedCitation={selectedCitation}
                guided={searchParams.get("guided") === "1"}
                view={courseContentView}
                graphScope={graphScope}
                graphChapter={graphChapter}
                graphDetailOpen={isKnowledgeDetailOpen}
                weaknesses={weaknessItems}
                recommendation={recommendation}
                currentTaskPointId={currentPathTaskPointId}
                assistantOpen={isStudyAssistantOpen}
                messages={displayedCourseMessages.map((message) => message.role === "assistant"
                  ? { ...message, content: sanitizeCourseAnswerContent(message.content) }
                  : message)}
                prompt={coursePrompt}
                isSending={isSearchingCourse}
                feedback={courseFeedback}
                isListening={speech.isListening}
                isTranscribing={speech.isTranscribing}
                isSpeaking={Boolean(speech.activeSpeechId)}
                isSpeechPaused={speech.isSpeechPaused}
                onViewChange={changeCourseContentView}
                onGraphScopeChange={changeGraphScope}
                onGraphChapterChange={changeGraphChapter}
                onGraphDetailClose={() => changeKnowledgeDetail(false)}
                onSelectPoint={openKnowledgeStudy}
                onSelectPrevious={() => {
                  const pointId = knowledgePointContentQuery.data?.data.previous_knowledge_point_id;
                  if (pointId) openKnowledgeStudy(pointId);
                }}
                onSelectNext={() => {
                  const pointId = knowledgePointContentQuery.data?.data.next_knowledge_point_id;
                  if (pointId) openKnowledgeStudy(pointId);
                }}
                onAssistantOpenChange={changeStudyAssistant}
                onPromptChange={setCoursePrompt}
                onPromptKeyDown={handleCourseComposerKeyDown}
                onSend={() => void sendCourseQuestion()}
                onToggleListening={() => void speech.toggleListening()}
                onReadLatest={() => {
                  const latest = [...displayedCourseMessages].reverse().find((message) => message.role === "assistant" && message.content.trim());
                  if (latest) toggleReadMessage(latest);
                }}
                onPauseOrResumeSpeaking={speech.pauseOrResumeSpeaking}
                onStopSpeaking={speech.stopSpeaking}
              />
            )}

            <CourseProgressDrawer
              open={isProgressDrawerOpen}
              summary={courseLoopSummary}
              steps={courseStudySteps}
              traceId={fallbackCourse?.agent_trace_id}
              weaknessSummary={weaknessSummary}
              learnerContext={learningState?.learner_context}
              weaknessItems={weaknessItems}
              updatingWeaknessItemId={updatingWeaknessItemId}
              learningStateError={learningStateQuery.isError && learningStateQuery.data === undefined}
              weaknessFeedback={weaknessFeedback}
              isRefreshing={isProgressSyncing}
              refreshWarning={progressSyncWarning}
              onClose={() => setIsProgressDrawerOpen(false)}
              onRefresh={() => void syncCourseProgress()}
              onWeaknessAction={(item, action) => void updateWeaknessReviewItem(item, action)}
              onPracticeWeakness={(item) => {
                const params = new URLSearchParams({
                  course_id: String(numericCourseId),
                  knowledge_point_id: item.knowledge_point_id ?? "",
                  weakness_item_id: item.id,
                  new: "1"
                });
                navigate(`${buildCoursePracticeWorkspacePath(numericCourseId)}?${params.toString()}`);
              }}
              onOpenWeaknessResource={(item, resourceId) => {
                const params = new URLSearchParams({
                  course_id: String(numericCourseId),
                  knowledge_point_id: item.knowledge_point_id ?? "",
                  learning_goal: item.diagnosis?.recommended_action || `复习并掌握${item.title}`
                });
                if (resourceId) params.set("resource_id", resourceId);
                navigate(`${PATHS.studio}?${params.toString()}`);
              }}
            />
          </div>
        </section>
      </section>
    </LearningSpaceShell>
  );
}
