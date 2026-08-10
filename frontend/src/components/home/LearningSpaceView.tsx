import { ArrowRight, BookOpen, LinkSimple, Microphone, SpeakerHigh, Sparkle, Stop } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { buildCoursePath, PATHS } from "../../app/routePaths";
import { learningActionButtonLabel, learningActionHref } from "../../features/learning-actions/learningActions";
import type { useLearningSpaceController } from "../../features/home/useLearningSpaceController";
import { SecureTutorImages, TutorImagePicker } from "../../features/tutor/TutorImageAttachments";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { MarkdownMessage } from "../feedback/MarkdownMessage";
import { AppSidebar } from "../layout/AppSidebar";
import { LearningSpaceShell } from "../layout/LearningSpaceShell";
import { TutorResponseProgress } from "../tutor/TutorResponseProgress";
import { HomeCourseDrawer } from "./HomeCourseDrawer";
import { CourseGenerationDialog, HomeAnswerInsights, HomeResourceCourseDialog, MaterialLibraryDrawer } from "./HomeLearningPanels";
import { TodayLearningInsight } from "./TodayLearningInsight";

type LearningSpaceController = ReturnType<typeof useLearningSpaceController>;

export function LearningSpaceView({ controller }: { controller: LearningSpaceController }) {
  const {
    isHistoryCollapsed,
    hasHomeThread,
    homeThreads,
    activeHomeThreadId,
    setIsHistoryCollapsed,
    resetHomeEntry,
    selectHomeConversation,
    renameHomeConversation,
    deleteHomeConversation,
    historyQuery,
    historySearch,
    historySearchThreads,
    historySearchQuery,
    setHistorySearch,
    homeChatStageRef,
    messages,
    streamingAnswerId,
    streamProgress,
    answerProgress,
    persistedAnswerProgress,
    speech,
    toggleReadMessage,
    activeAnswerPanel,
    expandedAnswerId,
    effectiveConversationMaterialIds,
    answerWarnings,
    updateHomeAnswerState,
    homeQuestionInputRef,
    prompt,
    setPrompt,
    handleComposerKeyDown,
    imageDraft,
    openLibrary,
    openCourseGeneration,
    isListening,
    isTranscribing,
    handleVoiceInput,
    isSendingQuestion,
    handleSendQuestion,
    materials,
    composerFeedback,
    learnerName,
    recentCourses,
    insightCourseId,
    nextActionQuery,
    insightMasteryQuery,
    insightLearningStateQuery,
    dashboardQuery,
    recentCourseActions,
    isCourseDrawerOpen,
    setIsCourseDrawerOpen,
    emptyState,
    isLibraryOpen,
    materialDraftIds,
    toggleMaterialDraft,
    openCourseGenerationFromLibrary,
    confirmConversationMaterials,
    materialDialogFeedback,
    closeLibrary,
    pendingHomeResourceGeneration,
    generateHomeResource,
    openResourceGeneration,
    closeResourceGeneration,
    isCourseDialogOpen,
    courseMaterialIds,
    toggleCourseMaterial,
    closeCourseGeneration,
    createCourseFromSelectedMaterials,
    isCreatingCourse,
    courseJob,
    cancelCourseCreation,
    retryCourseCreation,
    courseDialogFeedback,
  } = controller;
  return (
    <LearningSpaceShell hideTopNavigation surfaceClassName="home-learning-surface">
      <div className={["learning-home", isHistoryCollapsed ? "history-collapsed" : "", hasHomeThread ? "chat-active" : ""].filter(Boolean).join(" ")}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <AppSidebar
          isCollapsed={isHistoryCollapsed}
          conversations={homeThreads}
          activeConversationId={activeHomeThreadId}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onHomeClick={resetHomeEntry}
          onNewChat={resetHomeEntry}
          onSelectConversation={(conversation) => void selectHomeConversation(conversation)}
          onRenameConversation={renameHomeConversation}
          onDeleteConversation={deleteHomeConversation}
          hasMoreConversations={Boolean(historyQuery.hasNextPage)}
          isLoadingMoreConversations={historyQuery.isFetchingNextPage}
          onLoadMoreConversations={() => void historyQuery.fetchNextPage()}
          historySearchResults={historySearch ? historySearchThreads : undefined}
          historySearchPending={historySearchQuery.isPending && Boolean(historySearch)}
          historySearchError={historySearchQuery.isError}
          historySearchHasMore={Boolean(historySearchQuery.hasNextPage)}
          historySearchLoadingMore={historySearchQuery.isFetchingNextPage}
          onHistorySearch={setHistorySearch}
          onRetryHistorySearch={() => void historySearchQuery.refetch()}
          onLoadMoreHistorySearch={() => void historySearchQuery.fetchNextPage()}
        />

        <section
          ref={homeChatStageRef}
          className={hasHomeThread ? "home-chat-stage chat-active" : "home-chat-stage"}
          aria-label="AI 学习入口"
        >
          {hasHomeThread ? (
            <section className="home-thread-stage" aria-label="主页对话">
              {messages.map((message) => (
                <article className={`home-message ${message.role}`} key={message.id}>
                  {message.role === "assistant" && message.streaming && message.id === streamingAnswerId && streamProgress ? (
                    <TutorResponseProgress state={streamProgress} />
                  ) : null}
                  {message.role === "user" ? <SecureTutorImages attachments={message.attachments} /> : null}
                  {message.role === "assistant" && !message.streaming && (answerProgress[message.id] ?? persistedAnswerProgress[message.id]) ? (
                    <TutorResponseProgress
                      state={answerProgress[message.id] ?? persistedAnswerProgress[message.id]}
                      completed
                      durationMs={(answerProgress[message.id] ?? persistedAnswerProgress[message.id]).durationMs}
                      storageKey={`home-message:${message.id}`}
                    />
                  ) : null}
                  {message.role === "assistant" ? <MarkdownMessage content={message.content} /> : <p>{message.content}</p>}
                  {message.role === "assistant" && message.resource_jobs?.map((job) => (
                    <section className="tutor-resource-card" key={job.job_id} aria-label="对话生成资源">
                      <strong>{job.status === "completed" ? "已生成学习资源" : job.status === "failed" ? "资源生成失败" : job.label}</strong>
                      {job.resources.map((resource) => <Link key={resource.id} to={`${PATHS.studio}?course_id=${resource.course_id}&resource_id=${resource.id}`}>{resource.title}</Link>)}
                      {job.error_message ? <small>{job.error_message}</small> : null}
                    </section>
                  ))}
                  {message.role === "assistant" && message.resource_proposal && message.resource_proposal.action !== "none" && !(message.resource_jobs?.length) ? (
                    <section className="tutor-resource-card" aria-label="学习资源建议">
                      <strong>{message.resource_proposal.action === "generate" ? "准备生成配套学习资源" : "可以生成配套学习资源"}</strong>
                      <small>{message.resource_proposal.reason_summary}</small>
                      <button
                        type="button"
                        onClick={() => openResourceGeneration(message.id)}
                      >
                        选择课程并生成
                      </button>
                    </section>
                  ) : null}
                  {message.role === "assistant" && !message.streaming ? (
                    <button
                      className="message-speak-button"
                      type="button"
                      aria-label={speech.activeSpeechId === message.id ? "停止朗读" : "朗读回答"}
                      aria-pressed={speech.activeSpeechId === message.id}
                      onClick={() => toggleReadMessage(message)}
                    >
                      {speech.activeSpeechId === message.id ? <Stop size={15} weight="fill" aria-hidden="true" /> : <SpeakerHigh size={15} weight="duotone" aria-hidden="true" />}
                      <span>{speech.activeSpeechId === message.id ? "停止" : "朗读"}</span>
                    </button>
                  ) : null}
                  {message.role === "assistant" && !message.streaming ? (
                    <HomeAnswerInsights
                      message={message}
                      activePanel={activeAnswerPanel}
                      expandedAnswerId={expandedAnswerId}
                      selectedMaterialCount={effectiveConversationMaterialIds.length}
                      warnings={answerWarnings[message.id] ?? []}
                      onTogglePanel={(panel, messageId) => updateHomeAnswerState(messageId, panel)}
                    />
                  ) : null}
                </article>
              ))}
            </section>
          ) : (
            <div className="home-hero-copy">
              <h1>
                <span>{`嗨，${learnerName}，`}</span>
                <span>准备好一起学习了吗？</span>
              </h1>
            </div>
          )}

          <section className={hasHomeThread ? "composer-frame docked" : "composer-frame"} aria-label={hasHomeThread ? "底部学习输入" : "学习输入区"}>
            <div className="conversation-composer">
              <TutorImagePicker draft={imageDraft} compact display="previews" />
              <textarea
                ref={homeQuestionInputRef}
                aria-label="学习问题输入"
                value={prompt}
                rows={2}
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                onPaste={(event) => {
                  const files = Array.from(event.clipboardData.files).filter((file) => file.type.startsWith("image/"));
                  if (files.length) { event.preventDefault(); void imageDraft.addFiles(files); }
                }}
                onDrop={(event) => {
                  const files = Array.from(event.dataTransfer.files).filter((file) => file.type.startsWith("image/"));
                  if (files.length) { event.preventDefault(); void imageDraft.addFiles(files); }
                }}
                onDragOver={(event) => event.preventDefault()}
                placeholder="问学习问题，或用资料生成课程"
              />
              <div className="composer-actions">
                <div className="composer-toolbar" aria-label="输入工具">
                  <TutorImagePicker draft={imageDraft} compact display="controls" />
                  <button type="button" aria-label="打开资料库" title="资料库" onClick={() => openLibrary()}>
                    <BookOpen size={18} weight="duotone" aria-hidden="true" />
                  </button>
                  <button type="button" title="生成课程" onClick={openCourseGeneration}>
                    <Sparkle size={18} weight="duotone" aria-hidden="true" />
                  </button>
                </div>
                <div className="composer-submit-row">
                  <button
                    className={isListening ? "voice-button active" : "voice-button"}
                    type="button"
                    title={isTranscribing ? "正在识别" : isListening ? "结束录音" : "语音输入"}
                    aria-label="语音输入"
                    aria-pressed={isListening}
                    disabled={isTranscribing}
                    onClick={handleVoiceInput}
                  >
                    <Microphone size={18} weight="duotone" aria-hidden="true" />
                  </button>
                  <button className="ask-button" type="button" title="发送" disabled={isSendingQuestion} onClick={() => void handleSendQuestion()}>
                    <ArrowRight size={18} weight="bold" aria-hidden="true" />
                  </button>
                </div>
              </div>
            </div>
            {effectiveConversationMaterialIds.length > 0 ? (
              <div className="selected-materials-note">
                <LinkSimple size={16} weight="duotone" aria-hidden="true" />
                <span>{materials.filter((material) => effectiveConversationMaterialIds.includes(material.id)).slice(0, 3).map((material) => material.title).join("、")}</span>
                <small>{`共 ${effectiveConversationMaterialIds.length} 份`}</small>
                <button type="button" onClick={openLibrary}>管理</button>
              </div>
            ) : null}
            <InlineFeedback message={composerFeedback?.message ?? null} tone={composerFeedback?.tone} className="composer-inline-feedback" />
          </section>

          {!hasHomeThread ? (
            <TodayLearningInsight
              course={recentCourses.find((course) => Number(course.id) === insightCourseId) ?? null}
              action={nextActionQuery.data?.data}
              mastery={insightMasteryQuery.data?.data ?? null}
              learningState={insightLearningStateQuery.data?.data ?? null}
              loading={nextActionQuery.isPending || dashboardQuery.isPending}
            />
          ) : null}

          {!hasHomeThread && dashboardQuery.isLoading ? (
            <section className="recent-course-strip empty" aria-label="最近学习">
              <strong>正在读取学习空间</strong>
              <p>我们正在加载你的课程、资料和主页历史。</p>
            </section>
          ) : null}
          {!hasHomeThread && !dashboardQuery.isLoading && dashboardQuery.isError ? (
            <section className="recent-course-strip empty" aria-label="最近学习">
              <strong>学习空间暂时没有读取成功</strong>
              <p>稍后刷新页面，或重新登录后再试。</p>
            </section>
          ) : null}
          {!hasHomeThread && !dashboardQuery.isLoading && !dashboardQuery.isError && recentCourses.length > 0 ? (
            <section className="recent-course-strip" aria-label="最近学习">
              <div className="recent-course-heading">
                <span>最近学习</span>
                <button
                  className="home-all-courses-button"
                  type="button"
                  aria-expanded={isCourseDrawerOpen}
                  aria-controls="home-course-drawer-title"
                  onClick={() => setIsCourseDrawerOpen(true)}
                >
                  <BookOpen size={15} weight="duotone" aria-hidden="true" />
                  <span>全部课程</span>
                </button>
              </div>
              <ul className="recent-course-list" aria-label="最近学习列表">
                {recentCourses.map((course) => {
                  const action = recentCourseActions.get(course.id);
                  const progress = course.knowledge_point_count > 0
                    ? `${course.practiced_knowledge_point_count} / ${course.knowledge_point_count}`
                    : course.progress_label;
                  return (
                  <li key={course.id}>
                    <article className="recent-course">
                      <BookOpen size={18} weight="duotone" aria-hidden="true" />
                      <span className="recent-course-copy">
                        <Link to={buildCoursePath(course.id)}>{course.title}</Link>
                        <span className={`recent-course-state ${course.learning_status === "archived" ? "archived" : course.is_current ? "current" : "other"}`}>
                          {course.learning_status === "archived" ? "已完成" : course.is_current ? "当前学习" : "其他课程"}
                        </span>
                        <small><b>当前重点</b>{action?.label ?? course.focus}</small>
                      </span>
                      <span className="recent-course-progress"><small>学习覆盖</small><em>{progress}</em></span>
                      {action ? (
                        <Link className="course-next" to={learningActionHref(action)} aria-label={`下一步：${action.label}`}>
                          <small>下一步</small><strong>{learningActionButtonLabel(action)}</strong>
                        </Link>
                      ) : (
                        <Link className="course-next" to={buildCoursePath(course.id)}>
                          <small>下一步</small><strong>{course.next}</strong>
                        </Link>
                      )}
                    </article>
                  </li>
                  );
                })}
              </ul>
            </section>
          ) : null}
          {!hasHomeThread && !dashboardQuery.isLoading && !dashboardQuery.isError && recentCourses.length === 0 ? (
            <section className="recent-course-strip empty" aria-label="最近学习">
              <strong>{emptyState?.title ?? "还没有课程"}</strong>
              <p>{emptyState?.description ?? "上传资料后可直接问，也可生成课程。"}</p>
            </section>
          ) : null}
        </section>
      </div>

      {isLibraryOpen ? (
        <MaterialLibraryDrawer
          materials={materials}
          selectedMaterialIds={materialDraftIds}
          onToggleMaterial={toggleMaterialDraft}
          onOpenCourseGeneration={openCourseGenerationFromLibrary}
          onConfirm={() => void confirmConversationMaterials()}
          allowClear={effectiveConversationMaterialIds.length > 0}
          feedback={materialDialogFeedback}
          onClose={closeLibrary}
        />
      ) : null}
      {isCourseDrawerOpen ? <HomeCourseDrawer onClose={() => setIsCourseDrawerOpen(false)} /> : null}
      {pendingHomeResourceGeneration ? (
        <HomeResourceCourseDialog
          onClose={closeResourceGeneration}
          onSelect={(courseId) => void generateHomeResource(courseId)}
        />
      ) : null}
      {isCourseDialogOpen ? (
        <CourseGenerationDialog
          materials={materials}
          selectedMaterialIds={courseMaterialIds}
          onToggleMaterial={toggleCourseMaterial}
          onClose={closeCourseGeneration}
          onCreate={(courseTitle) => void createCourseFromSelectedMaterials(courseTitle)}
          isCreatingCourse={isCreatingCourse}
          initialCourseTitle={typeof courseJob?.request.course_title === "string" ? courseJob.request.course_title : undefined}
          job={courseJob}
          onCancelJob={() => void cancelCourseCreation()}
          onRetryJob={() => void retryCourseCreation()}
          feedback={courseDialogFeedback}
        />
      ) : null}
    </LearningSpaceShell>
  );
}
