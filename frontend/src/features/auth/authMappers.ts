import { type ApiUser } from "../../types/api";
import { type StudentUser } from "./authStore";


export function mapApiUserToStudentUser(user: ApiUser): StudentUser {
  return {
    id: user.id,
    account: user.account,
    displayName: user.display_name,
    role: user.role,
    starterMode: user.starter_mode
  };
}
