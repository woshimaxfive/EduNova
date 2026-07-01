export const PATHS = {
  root: "/",
  login: "/login",
  register: "/register",
  demo: "/demo",
  app: "/app",
  library: "/app/library",
  studio: "/app/studio",
  profile: "/app/profile",
  tutor: "/app/tutor",
  practice: "/app/practice",
  reports: "/app/reports",
  settings: "/app/settings"
} as const;

export type AppPath = (typeof PATHS)[keyof typeof PATHS];
