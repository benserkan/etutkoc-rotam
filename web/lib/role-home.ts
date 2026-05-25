import type { UserRole } from "@/lib/types/me";

/**
 * Rol bazlı varsayılan panel girişi — login sonrası landing VE layout
 * rol-uyuşmazlığı fallback'i için TEK kaynak. Asla /me/account'a düşürmez
 * (kullanıcıyı dead-end'e atmaz; her rol kendi paneline gider).
 */
export function roleHome(role: UserRole): string {
  switch (role) {
    case "super_admin":
      return "/admin";
    case "institution_admin":
      return "/institution";
    case "teacher":
      return "/teacher/dashboard";
    case "parent":
      return "/parent";
    default:
      return "/student";
  }
}

/** Her rolün erişebildiği panel kök alanı (returnUrl doğrulaması için). */
const ROLE_AREA: Record<UserRole, string> = {
  super_admin: "/admin",
  institution_admin: "/institution",
  teacher: "/teacher",
  parent: "/parent",
  student: "/student",
};

/**
 * returnUrl yalnızca kullanıcının kendi panel alanı (veya paylaşılan /me) ise
 * güvenli kabul edilir; aksi halde null döner. Bu hem:
 *   - rol-uyuşmazlığını (süper admin → /teacher/settings → /me/account dead-end)
 *   - open-redirect'i (//evil.com, https://evil.com gibi)
 * engeller. Yol kısmı eşleştirilir; sorgu/hash korunur.
 */
export function safeReturnUrl(
  returnUrl: string | null | undefined,
  role: UserRole,
): string | null {
  if (!returnUrl) return null;
  if (!returnUrl.startsWith("/") || returnUrl.startsWith("//")) return null;
  const path = returnUrl.split(/[?#]/)[0];
  const area = ROLE_AREA[role];
  const inOwnArea = path === area || path.startsWith(area + "/");
  const inShared = path === "/me" || path.startsWith("/me/");
  return inOwnArea || inShared ? returnUrl : null;
}
