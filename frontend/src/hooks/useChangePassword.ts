import { authService } from "@/services/authService"

export function useChangePassword() {
  async function changePassword(currentPassword: string, newPassword: string) {
    await authService.changePassword({
      current_password: currentPassword,
      new_password: newPassword,
    })
  }

  return { changePassword }
}
