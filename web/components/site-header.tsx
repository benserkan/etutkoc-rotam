"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandLogo } from "@/components/brand-logo";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Bell,
  BookOpenCheck,
  CalendarDays,
  CalendarRange,
  ListChecks,
  Loader2,
  LogOut,
  Menu,
  RotateCcw,
  Target,
  Timer,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/lib/hooks/use-logout";
import { getStudentBadges, studentKeys } from "@/lib/api/student";
import type { PendingBadgesResponse } from "@/lib/types/student";
import type { UserPublic } from "@/lib/types/me";
import { ROLE_LABELS_TR } from "@/lib/types/me";

interface Props {
  /** Server Component'in fetch ettiği oturum kullanıcısı — header hidrasyon hızı. */
  user: UserPublic;
  /** Badge polling aktif edilsin mi? Default true (yalnız öğrenci sayfalarında). */
  enableBadges?: boolean;
}

type StudentBadgeKey = "pending_count" | "today_open_count";

interface NavLink {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  badgeKey?: StudentBadgeKey;
}

const STUDENT_NAV: NavLink[] = [
  { href: "/student/day", label: "Bugün", icon: CalendarDays, badgeKey: "today_open_count" },
  { href: "/student/week", label: "Hafta", icon: CalendarRange },
  { href: "/student/books", label: "Kitaplar", icon: BookOpenCheck },
  { href: "/student/requests", label: "Talepler", icon: ListChecks, badgeKey: "pending_count" },
  { href: "/student/focus", label: "Odak", icon: Timer },
  { href: "/student/dna", label: "Çalışma DNA", icon: BarChart3 },
  { href: "/student/review", label: "Tekrar", icon: RotateCcw },
  { href: "/student/goals", label: "Hedefler", icon: Target },
];

/**
 * Site başlığı — ETÜTKOÇ logosu + yatay öğrenci navigasyonu + bekleyen rozet
 * + ad-soyad + çıkış.
 *
 * Badge polling sözleşmesi (kullanıcı onayı: Paket 5 planı):
 *   - 60 saniye polling — refetchInterval
 *   - QueryKey: ['badges', 'student', 'me', 'pending']
 *
 * Mobil (< lg): hamburger drawer; aynı linkler liste şeklinde.
 */
export function SiteHeader({ user, enableBadges = true }: Props) {
  const pathname = usePathname();
  const logout = useLogout();
  const [navOpen, setNavOpen] = React.useState(false);
  const badges = useQuery<PendingBadgesResponse>({
    queryKey: studentKeys.badges(),
    queryFn: () => getStudentBadges(),
    enabled: enableBadges && user.role === "student",
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const pendingCount = badges.data?.pending_count ?? 0;
  const isStudent = user.role === "student";

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
        <BrandLogo
          href={isStudent ? "/student/day" : "/me/account"}
          size={28}
          className="shrink-0"
        />

        {isStudent ? (
          <nav className="hidden lg:flex items-center gap-1 flex-1 ml-2" aria-label="Öğrenci paneli">
            {STUDENT_NAV.map((n) => {
              const active =
                pathname === n.href || pathname.startsWith(`${n.href}/`);
              const Icon = n.icon;
              const count = n.badgeKey ? badges.data?.[n.badgeKey] ?? 0 : 0;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                    active
                      ? "bg-muted font-medium text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="size-3.5" aria-hidden />
                  {n.label}
                  {count > 0 ? (
                    <span className="inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground">
                      {count > 99 ? "99+" : count}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </nav>
        ) : (
          <div className="flex-1" />
        )}

        {isStudent ? (
          <Link
            href="/student/requests"
            className="relative inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            aria-label={
              pendingCount > 0
                ? `${pendingCount} bekleyen koç yanıtı`
                : "Koç yanıtı bekleyen talep yok"
            }
          >
            <Bell className="size-4" aria-hidden />
            {pendingCount > 0 ? (
              <span
                className="absolute -right-1 -top-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground"
                aria-hidden
              >
                {pendingCount > 99 ? "99+" : pendingCount}
              </span>
            ) : null}
          </Link>
        ) : null}

        <div className="hidden sm:flex flex-col items-end leading-tight">
          <span className="text-sm font-medium truncate max-w-[180px]">
            {user.full_name}
          </span>
          <span className="text-xs text-muted-foreground">
            {ROLE_LABELS_TR[user.role]}
          </span>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          aria-label="Çıkış yap"
          className="hidden sm:inline-flex"
        >
          {logout.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <LogOut aria-hidden />
          )}
          <span className="hidden sm:inline">Çıkış</span>
        </Button>

        {isStudent ? (
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setNavOpen(true)}
            aria-label="Menüyü aç"
          >
            <Menu className="size-5" aria-hidden />
          </Button>
        ) : null}
      </div>

      {/* Mobil drawer — basit overlay + sağdan kayan panel */}
      {isStudent && navOpen ? (
        <MobileDrawer onClose={() => setNavOpen(false)} pathname={pathname} user={user} onLogout={() => logout.mutate()} />
      ) : null}
    </header>
  );
}

function MobileDrawer({
  onClose,
  pathname,
  user,
  onLogout,
}: {
  onClose: () => void;
  pathname: string;
  user: UserPublic;
  onLogout: () => void;
}) {
  // Esc ile kapat + body scroll lock
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal
      aria-label="Mobil menü"
      className="lg:hidden fixed inset-0 z-40"
    >
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-hidden
      />
      <div className="absolute right-0 top-0 h-full w-72 max-w-[85vw] bg-card shadow-xl border-l border-border flex flex-col">
        <div className="flex items-center justify-between px-4 h-14 border-b border-border">
          <div className="leading-tight">
            <p className="text-sm font-medium truncate">{user.full_name}</p>
            <p className="text-xs text-muted-foreground">{ROLE_LABELS_TR[user.role]}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Kapat">
            <X className="size-5" aria-hidden />
          </Button>
        </div>
        <nav className="flex-1 overflow-y-auto p-2 space-y-0.5" aria-label="Öğrenci paneli">
          {STUDENT_NAV.map((n) => {
            const active =
              pathname === n.href || pathname.startsWith(`${n.href}/`);
            const Icon = n.icon;
            return (
              <Link
                key={n.href}
                href={n.href}
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors",
                  active
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="size-4" aria-hidden />
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border">
          <Button variant="outline" className="w-full" onClick={onLogout}>
            <LogOut className="size-4" aria-hidden /> Çıkış yap
          </Button>
        </div>
      </div>
    </div>
  );
}
