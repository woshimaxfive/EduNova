export const PATHS = {
  root: "/",
  login: "/login",
  register: "/register",
  app: "/app",
  library: "/app/library",
  path: "/app/path",
  courses: "/app/courses",
  courseDetail: "/app/courses/:courseId",
  coursePath: "/app/courses/:courseId/path",
  coursePractice: "/app/courses/:courseId/practice",
  courseReports: "/app/courses/:courseId/reports",
  studio: "/app/studio",
  profile: "/app/profile",
  practice: "/app/practice",
  reports: "/app/reports",
  settings: "/app/settings"
} as const;

export type AppPath = (typeof PATHS)[keyof typeof PATHS];

export function buildCoursePath(courseId: string | number) {
  return `${PATHS.courses}/${courseId}`;
}

export function buildCoursePathWorkspacePath(courseId: string | number) {
  return `${buildCoursePath(courseId)}/path`;
}

export function buildCoursePracticeWorkspacePath(courseId: string | number) {
  return `${buildCoursePath(courseId)}/practice`;
}

export function buildCourseReportsWorkspacePath(courseId: string | number) {
  return `${buildCoursePath(courseId)}/reports`;
}
