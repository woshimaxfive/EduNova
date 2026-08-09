import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { buildCoursePath } from "../../app/routePaths";
import { createCourseBuilderJob, createIdempotencyKey, getAiJob } from "../../api/aiJobs";
import { listCourses, type ApiCourseSummary } from "../../api/courses";
import { getApiErrorMessage } from "../../api/errors";
import {
  compareMaterials,
  confirmMaterialOutline,
  createMaterialIngestionJob,
  deleteMaterial,
  getLatestMaterialComparison,
  getMaterial,
  getMaterialOutline,
  listMaterials,
  type MaterialComparisonResult,
  type MaterialListItem,
  type MaterialOutlineOperation,
  updateMaterialOutline,
  uploadMaterial
} from "../../api/materials";
import { isComparableMaterial } from "../../components/library/libraryMaterialState";
import { type LibraryFilter } from "../../components/library/LibraryWorkspaceToolbar";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import {
  asArray,
  asMaterialComparison,
  asMaterialOutline,
  buildSuggestedCourseTitle,
  commonCourseIds,
  parsePositiveId,
  type CompareTab,
  type CompareView,
  type DetailTab,
  type DrawerMode
} from "./libraryWorkspaceModel";
import {
  invalidateLearningNextActions,
  learningActionHref,
  useLearningNextAction
} from "../learning-actions/learningActions";

export function useLibraryWorkspaceController() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const initialMaterialId = parsePositiveId(searchParams.get("material_id"));
  const [activeFilter, setActiveFilter] = useState<LibraryFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(initialMaterialId ? "detail" : null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [compareTab, setCompareTab] = useState<CompareTab>("common");
  const [compareView, setCompareView] = useState<CompareView>("setup");
  const [compareCourseId, setCompareCourseId] = useState("");
  const [compareMaterialIds, setCompareMaterialIds] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<MaterialComparisonResult | null>(null);
  const [compareFeedback, setCompareFeedback] = useState<string | null>(null);
  const [isComparingMaterials, setIsComparingMaterials] = useState(false);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [courseMaterialIds, setCourseMaterialIds] = useState<string[]>([]);
  const [courseTitle, setCourseTitle] = useState("资料生成课程");
  const [courseTitleTouched, setCourseTitleTouched] = useState(false);
  const [courseJobId, setCourseJobId] = useState<string | null>(null);
  const [isUploadingMaterial, setIsUploadingMaterial] = useState(false);
  const [materialPendingDeletion, setMaterialPendingDeletion] = useState<MaterialListItem | null>(null);
  const [isDeletingMaterial, setIsDeletingMaterial] = useState(false);
  const [libraryFeedback, setLibraryFeedback] = useState<string | null>(null);
  const [outlineFeedback, setOutlineFeedback] = useState<string | null>(null);
  const [isUpdatingOutline, setIsUpdatingOutline] = useState(false);
  const [courseDialogFeedback, setCourseDialogFeedback] = useState<string | null>(null);
  const { jobs, trackJob, getJob, cancelJob, retryJob } = useAiJobs();
  const courseJob = getJob(courseJobId);
  const isCreatingCourse = Boolean(courseJob && ["queued", "running", "cancelling"].includes(courseJob.status));

  const materialsQuery = useQuery({ queryKey: ["materials", "list"], queryFn: () => listMaterials(), staleTime: 30_000 });
  const coursesQuery = useQuery({ queryKey: ["courses", "list"], queryFn: () => listCourses(), staleTime: 30_000 });
  const nextActionQuery = useLearningNextAction();
  const files = useMemo(() => asArray<MaterialListItem>(materialsQuery.data?.data), [materialsQuery.data?.data]);
  const courses = useMemo(() => asArray<ApiCourseSummary>(coursesQuery.data?.data), [coursesQuery.data?.data]);
  const courseTitles = useMemo(() => new Map(courses.map((course) => [course.id, course.title])), [courses]);
  const selectedMaterialId = parsePositiveId(searchParams.get("material_id"));
  const selectedMaterial = files.find((material) => Number(material.id) === selectedMaterialId) ?? null;
  const activeMaterialJob = jobs.find((job) => (
    job.workflow === "material_ingestion"
    && ["queued", "running", "cancelling"].includes(job.status)
    && Number(job.request.material_id) === selectedMaterialId
  )) ?? null;
  const materialDetailQuery = useQuery({
    queryKey: ["materials", "detail", selectedMaterialId],
    queryFn: () => getMaterial(selectedMaterialId ?? 0),
    enabled: drawerMode === "detail" && selectedMaterialId !== null,
    staleTime: 30_000
  });
  const materialDetail = materialDetailQuery.data?.data ?? null;
  const materialOutlineQuery = useQuery({
    queryKey: ["materials", "outline", selectedMaterialId],
    queryFn: () => getMaterialOutline(selectedMaterialId ?? 0),
    enabled: drawerMode === "detail" && selectedMaterialId !== null && materialDetail?.category === "document" && materialDetail.ingestion_status !== "legacy",
    staleTime: 10_000
  });
  const materialOutline = asMaterialOutline(materialOutlineQuery.data?.data);

  const selectedCompareMaterials = useMemo(
    () => compareMaterialIds.map((id) => files.find((file) => file.id === id)).filter((material): material is MaterialListItem => Boolean(material)),
    [compareMaterialIds, files]
  );
  const sharedCourseIds = useMemo(() => commonCourseIds(selectedCompareMaterials), [selectedCompareMaterials]);
  const sharedCourses = courses.filter((course) => sharedCourseIds.includes(course.id));
  const effectiveCompareCourseId = sharedCourseIds.includes(compareCourseId)
    ? compareCourseId
    : sharedCourseIds.length === 1
      ? sharedCourseIds[0]
      : "";
  const recentComparisonCourseId = compareCourseId || courses[0]?.id || "";

  function handleNextAction(action: NonNullable<typeof nextActionQuery.data>["data"]) {
    if (action.kind === "upload_material") {
      uploadInputRef.current?.click();
      return;
    }
    if (action.kind === "create_course" && action.material_id) {
      openCourseDialog([action.material_id]);
      return;
    }
    const material = files.find((item) => item.id === action.material_id);
    if (material) {
      openMaterial(material);
      return;
    }
    navigate(learningActionHref(action));
  }
  const latestComparisonQuery = useQuery({
    queryKey: ["materials", "comparison", "latest", parsePositiveId(recentComparisonCourseId)],
    queryFn: () => getLatestMaterialComparison(parsePositiveId(recentComparisonCourseId) ?? 0),
    enabled: drawerMode === "compare" && compareView === "recent" && parsePositiveId(recentComparisonCourseId) !== null,
    staleTime: 10_000
  });
  const displayedComparison = compareView === "recent"
    ? asMaterialComparison(latestComparisonQuery.data?.data)
    : compareResult;

  const filteredFiles = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return files.filter((file) => {
      const matchesFilter = activeFilter === "all" || file.category === activeFilter;
      const matchesSearch = !normalizedSearch || file.title.toLowerCase().includes(normalizedSearch) || file.extension.toLowerCase().includes(normalizedSearch);
      return matchesFilter && matchesSearch;
    });
  }, [activeFilter, files, searchTerm]);

  useEffect(() => {
    if (courseJobId) return;
    const restored = jobs.find((job) => job.workflow === "course_builder" && ["queued", "running", "cancelling", "failed"].includes(job.status));
    if (!restored) return;
    // Restore durable server state after navigation or refresh.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCourseMaterialIds(Array.isArray(restored.request.material_ids) ? restored.request.material_ids.map(String) : []);
    if (typeof restored.request.course_title === "string") setCourseTitle(restored.request.course_title);
    setCourseTitleTouched(true);
    setCourseJobId(restored.job_id);
    setIsCourseDialogOpen(true);
  }, [courseJobId, jobs]);

  useEffect(() => {
    if (!courseJob) return;
    if (courseJob.status === "failed") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCourseDialogFeedback(courseJob.error_message ?? "课程生成失败，请稍后重试。");
      return;
    }
    const courseId = courseJob.result.course_id;
    if (courseJob.status === "completed" && (typeof courseId === "string" || typeof courseId === "number")) {
      setCourseJobId(null);
      setIsCourseDialogOpen(false);
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["courses", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
        invalidateLearningNextActions(queryClient)
      ]);
      navigate(buildCoursePath(String(courseId)));
    }
  }, [courseJob, navigate, queryClient]);

  const removeMaterialParam = useCallback(() => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("material_id");
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  const closeDrawer = useCallback(() => {
    setDrawerMode(null);
    setCompareMaterialIds([]);
    setCompareResult(null);
    setCompareFeedback(null);
    removeMaterialParam();
  }, [removeMaterialParam]);

  function openMaterial(material: MaterialListItem) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("material_id", material.id);
      return next;
    }, { replace: true });
    setDetailTab("overview");
    setDrawerMode("detail");
  }

  async function handleDeleteMaterial() {
    if (!materialPendingDeletion || isDeletingMaterial) return;
    const material = materialPendingDeletion;
    setIsDeletingMaterial(true);
    try {
      await deleteMaterial(Number(material.id));
      setMaterialPendingDeletion(null);
      setCompareMaterialIds((current) => current.filter((id) => id !== material.id));
      setCourseMaterialIds((current) => current.filter((id) => id !== material.id));
      if (selectedMaterialId === Number(material.id)) {
        setDrawerMode(null);
        removeMaterialParam();
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
        queryClient.invalidateQueries({ queryKey: ["courses", "list"] }),
        invalidateLearningNextActions(queryClient)
      ]);
    } catch (error) {
      setLibraryFeedback(getApiErrorMessage(error, "资料删除失败，请稍后再试。"));
    } finally {
      setIsDeletingMaterial(false);
    }
  }

  function startCompare(initialIds: string[] = []) {
    removeMaterialParam();
    setCompareMaterialIds(initialIds);
    setCompareCourseId("");
    setCompareResult(null);
    setCompareFeedback(null);
    setCompareTab("common");
    setCompareView("setup");
    setDrawerMode("compare");
  }

  function openRecentComparison() {
    removeMaterialParam();
    setCompareMaterialIds([]);
    setCompareCourseId(courses[0]?.id ?? "");
    setCompareResult(null);
    setCompareFeedback(null);
    setCompareTab("common");
    setCompareView("recent");
    setDrawerMode("compare");
  }

  function openCourseDialog(materialIds: string[] = []) {
    const selected = materialIds.map((id) => files.find((file) => file.id === id)).filter((material): material is MaterialListItem => Boolean(material));
    if (drawerMode === "detail") {
      setDrawerMode(null);
      removeMaterialParam();
    }
    setCourseMaterialIds(materialIds);
    setCourseTitle(buildSuggestedCourseTitle(selected));
    setCourseTitleTouched(false);
    setCourseDialogFeedback(null);
    setIsCourseDialogOpen(true);
  }

  async function handleUploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUploadingMaterial(true);
    try {
      const response = await uploadMaterial({ file });
      const uploaded = response.data;
      if (uploaded.ingestion_job_id) {
        trackJob(await getAiJob(uploaded.ingestion_job_id));
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
        invalidateLearningNextActions(queryClient)
      ]);
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set("material_id", String(uploaded.material_id));
        return next;
      }, { replace: true });
      setDrawerMode("detail");
      setDetailTab("overview");
      setLibraryFeedback(null);
    } catch (error) {
      setLibraryFeedback(getApiErrorMessage(error, "资料上传失败，请稍后再试。"));
    } finally {
      setIsUploadingMaterial(false);
      event.target.value = "";
    }
  }

  async function applyOutlineOperations(operations: MaterialOutlineOperation[]) {
    if (!selectedMaterialId || !materialOutline || isUpdatingOutline) return;
    setIsUpdatingOutline(true);
    setOutlineFeedback(null);
    try {
      const result = await updateMaterialOutline(selectedMaterialId, materialOutline.version, operations);
      queryClient.setQueryData(["materials", "outline", selectedMaterialId], result);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "detail", selectedMaterialId] }),
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] })
      ]);
    } catch (error) {
      setOutlineFeedback(getApiErrorMessage(error, "目录调整失败，请刷新后重试。"));
    } finally {
      setIsUpdatingOutline(false);
    }
  }

  async function handleConfirmOutline() {
    if (!selectedMaterialId || !materialOutline || isUpdatingOutline) return;
    setIsUpdatingOutline(true);
    setOutlineFeedback(null);
    try {
      const result = await confirmMaterialOutline(selectedMaterialId, materialOutline.version);
      queryClient.setQueryData(["materials", "outline", selectedMaterialId], result);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "detail", selectedMaterialId] }),
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
        invalidateLearningNextActions(queryClient)
      ]);
      setOutlineFeedback(null);
    } catch (error) {
      setOutlineFeedback(getApiErrorMessage(error, "目录确认失败，请检查解析质量后重试。"));
    } finally {
      setIsUpdatingOutline(false);
    }
  }

  async function handleReingestMaterial() {
    if (!selectedMaterialId || isUpdatingOutline) return;
    setIsUpdatingOutline(true);
    setOutlineFeedback(null);
    try {
      const job = await createMaterialIngestionJob(selectedMaterialId, true, createIdempotencyKey("material-ingestion"));
      trackJob(job);
      setOutlineFeedback(null);
      await queryClient.invalidateQueries({ queryKey: ["materials", "list"] });
    } catch (error) {
      setOutlineFeedback(getApiErrorMessage(error, "重新解析任务创建失败，请稍后重试。"));
    } finally {
      setIsUpdatingOutline(false);
    }
  }

  function toggleCompareMaterial(material: MaterialListItem) {
    if (!isComparableMaterial(material)) return;
    setCompareMaterialIds((current) => current.includes(material.id) ? current.filter((id) => id !== material.id) : [...current, material.id]);
    setCompareResult(null);
    setCompareFeedback(null);
  }

  async function handleCompareMaterials() {
    const courseId = parsePositiveId(effectiveCompareCourseId);
    const materialIds = compareMaterialIds.map(Number).filter(Number.isFinite);
    if (courseId === null || materialIds.length < 2 || isComparingMaterials) {
      setCompareFeedback("至少选择两份属于同一课程的已解析资料。");
      return;
    }
    setIsComparingMaterials(true);
    setCompareFeedback(null);
    try {
      const result = await compareMaterials({ course_id: courseId, material_ids: materialIds });
      setCompareResult(result.data);
      setCompareView("result");
      setCompareTab("common");
      queryClient.setQueryData(["materials", "comparison", "latest", courseId], result);
    } catch (error) {
      setCompareFeedback(getApiErrorMessage(error, "资料对比失败，请稍后重试。"));
    } finally {
      setIsComparingMaterials(false);
    }
  }

  function toggleCourseMaterial(materialId: string) {
    const next = courseMaterialIds.includes(materialId)
      ? courseMaterialIds.filter((id) => id !== materialId)
      : [...courseMaterialIds, materialId];
    setCourseMaterialIds(next);
    if (!courseTitleTouched) {
      const selected = next.map((id) => files.find((file) => file.id === id)).filter((material): material is MaterialListItem => Boolean(material));
      setCourseTitle(buildSuggestedCourseTitle(selected));
    }
  }

  async function handleCreateCourse() {
    const materialIds = courseMaterialIds.map(Number).filter(Number.isFinite);
    if (materialIds.length === 0) {
      setCourseDialogFeedback("先至少选择一份已解析资料。");
      return;
    }
    if (isCreatingCourse) return;
    setCourseDialogFeedback(null);
    try {
      const job = await createCourseBuilderJob(
        { material_ids: materialIds, course_title: courseTitle.trim() },
        createIdempotencyKey("library-course")
      );
      setCourseJobId(job.job_id);
      trackJob(job);
    } catch (error) {
      setCourseDialogFeedback(getApiErrorMessage(error, "课程生成失败，请确认选择的是已解析资料。"));
    }
  }

  const detailState = materialDetail ?? selectedMaterial;
  const detailCanUse = Boolean(detailState && detailState.category === "document" && detailState.ingestion_status === "confirmed");
  const parsedCount = files.filter((file) => file.ingestion_status === "confirmed").length;
  return {
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
  };
}

export type LibraryWorkspaceController = ReturnType<typeof useLibraryWorkspaceController>;
