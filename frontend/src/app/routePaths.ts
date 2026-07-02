export const PATHS = {
  root: "/",
  login: "/login",
  register: "/register",
  demo: "/demo",
  app: "/app",
  library: "/app/library",
  courses: "/app/courses",
  courseDetail: "/app/courses/:courseId",
  designLab: "/app/design-lab",
  studio: "/app/studio",
  profile: "/app/profile",
  tutor: "/app/tutor",
  practice: "/app/practice",
  reports: "/app/reports",
  settings: "/app/settings"
} as const;

export type AppPath = (typeof PATHS)[keyof typeof PATHS];

export function buildCoursePath(courseId: string | number) {
  return `${PATHS.courses}/${courseId}`;
}
