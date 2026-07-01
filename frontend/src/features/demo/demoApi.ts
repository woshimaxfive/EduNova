import { type AuthSession } from "../auth/authStore";

export async function startDemoSession(): Promise<AuthSession> {
  return {
    token: "demo-token",
    user: {
      id: 1,
      email: "demo@edunova.local",
      displayName: "演示学生",
      role: "student"
    }
  };
}
