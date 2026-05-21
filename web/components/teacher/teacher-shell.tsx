"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  BookOpen,
  CalendarRange,
  Gauge,
  Gem,
  Inbox,
  LayoutDashboard,
  Loader2,
  LogOut,
  Menu,
  Settings,
  Sparkles,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { useLogout } from "@/lib/hooks/use-logout";
import { getTeacherBadges, teacherKeys } from "@/lib/api/teacher";
import type { TeacherBadgesResponse } from "@/lib/types/teacher";
import type { UserPublic } from "@/lib/types/me";
import { ROLE_LABELS_TR } from "@/lib/types/me";

interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
  // Badge gösterimi için anahtar — badges response'unun field adı
  badgeKey?: "pending_request_count" | "at_risk_count";
}

const TEACHER_NAV: NavLink[] = [
  { href: "/teacher/dashboard", label: "Pano", icon: LayoutDashboard },
  { href: "/teacher/students", label: "Öğrenciler", icon: Users, badgeKey: "at_risk_count" },
  { href: "/teacher/requests", label: "Talepler", icon: Inbox, badgeKey: "pending_request_count" },
  { href: "/teacher/billing", label: "Tahsilat", icon: Wallet },
  { href: "/teacher/plan", label: "Paket", icon: Gem },
  { href: "/teacher/library", label: "Kitaplar", icon: BookOpen },
  { href: "/teacher/insights", label: "AI İçgörü", icon: Sparkles },
  { href: "/teacher/academic-years", label: "Akademik Yıllar", icon: CalendarRange },
  { href: "/teacher/grade-advance", label: "Sınıf Yükseltme", icon: ArrowUpRight },
  { href: "/teacher/usage", label: "Kullanım", icon: Gauge },
  { href: "/teacher/settings", label: "Ayarlar", icon: Settings },
];

interface Props {
  user: UserPublic;
  children: React.ReactNode;
}

/**
 * Öğretmen paneli ana shell — sticky sidebar (lg+) + üst topbar (mobil drawer).
 *
 * Badge polling sözleşmesi:
 *   - 60 saniye refetchInterval
 *   - QueryKey: ['teacher', 'me', 'badges']
 *   - Backend `teacher:{id}:badges` invalidate'i bu prefix'i bayatlar
 *
 * Bu component sadece NAVIGATION sunar; her sayfa kendi içeriğini render eder.
 */
export function TeacherShell({ user, children }: Props) {
  const pathname = usePathname();
  const logout = useLogout();
  const [navOpen, setNavOpen] = React.useState(false);

  const badges = useQuery<TeacherBadgesResponse>({
    queryKey: teacherKeys.badges(),
    queryFn: () => getTeacherBadges(),
    enabled: user.role === "teacher",
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row">
      {/* Sidebar (lg+) */}
      <aside className="hidden lg:flex lg:flex-col lg:w-60 lg:shrink-0 lg:sticky lg:top-0 lg:h-screen border-r border-border bg-card/40">
        <div className="px-4 h-14 flex items-center border-b border-border">
          <BrandLogo href="/teacher/dashboard" size={28} />
        </div>
        <nav
          className="flex-1 overflow-y-auto p-2 space-y-0.5"
          aria-label="Öğretmen paneli"
        >
          {TEACHER_NAV.map((n) => (
            <SidebarLink
              key={n.href}
              link={n}
              pathname={pathname}
              badgeValue={n.badgeKey ? badges.data?.[n.badgeKey] ?? 0 : 0}
            />
          ))}
        </nav>
        <UserCard
          user={user}
          onLogout={() => logout.mutate()}
          isLoggingOut={logout.isPending}
        />
      </aside>

      {/* Topbar (lg-) */}
      <header className="lg:hidden sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="flex h-14 items-center gap-3 px-4">
          <BrandLogo href="/teacher/dashboard" size={28} className="shrink-0" />
          <div className="flex-1" />
          <span className="hidden sm:inline text-sm text-muted-foreground truncate max-w-[160px]">
            {user.full_name}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setNavOpen(true)}
            aria-label="Menüyü aç"
          >
            <Menu className="size-5" aria-hidden />
          </Button>
        </div>
      </header>

      <main className="flex-1 min-w-0">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:py-8">{children}</div>
      </main>

      {navOpen ? (
        <MobileDrawer
          onClose={() => setNavOpen(false)}
          pathname={pathname}
          user={user}
          badges={badges.data}
          onLogout={() => logout.mutate()}
        />
      ) : null}
    </div>
  );
}

function SidebarLink({
  link,
  pathname,
  badgeValue,
}: {
  link: NavLink;
  pathname: string;
  badgeValue: number;
}) {
  const active =
    pathname === link.href || pathname.startsWith(`${link.href}/`);
  const Icon = link.icon;
  return (
    <Link
      href={link.href}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-muted font-medium text-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      <span className="flex-1 truncate">{link.label}</span>
      {badgeValue > 0 ? (
        <span
          className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground"
          aria-label={`${badgeValue} bekliyor`}
        >
          {badgeValue > 99 ? "99+" : badgeValue}
        </span>
      ) : null}
    </Link>
  );
}

function UserCard({
  user,
  onLogout,
  isLoggingOut,
}: {
  user: UserPublic;
  onLogout: () => void;
  isLoggingOut: boolean;
}) {
  return (
    <div className="border-t border-border p-3 space-y-2">
      <div className="leading-tight">
        <p className="text-sm font-medium truncate" title={user.full_name}>
          {user.full_name}
        </p>
        <p className="text-xs text-muted-foreground">
          {ROLE_LABELS_TR[user.role]}
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        className="w-full justify-start"
        onClick={onLogout}
        disabled={isLoggingOut}
      >
        {isLoggingOut ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <LogOut className="size-4" aria-hidden />
        )}
        <span>Çıkış</span>
      </Button>
    </div>
  );
}

function MobileDrawer({
  onClose,
  pathname,
  user,
  badges,
  onLogout,
}: {
  onClose: () => void;
  pathname: string;
  user: UserPublic;
  badges: TeacherBadgesResponse | undefined;
  onLogout: () => void;
}) {
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
            <p className="text-xs text-muted-foreground">
              {ROLE_LABELS_TR[user.role]}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Kapat">
            <X className="size-5" aria-hidden />
          </Button>
        </div>
        <nav
          className="flex-1 overflow-y-auto p-2 space-y-0.5"
          aria-label="Öğretmen paneli"
        >
          {TEACHER_NAV.map((n) => {
            const active =
              pathname === n.href || pathname.startsWith(`${n.href}/`);
            const Icon = n.icon;
            const badgeValue = n.badgeKey ? badges?.[n.badgeKey] ?? 0 : 0;
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
                <span className="flex-1 truncate">{n.label}</span>
                {badgeValue > 0 ? (
                  <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground">
                    {badgeValue > 99 ? "99+" : badgeValue}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border">
          <Button variant="outline" className="w-full" onClick={onLogout}>
            <LogOut className="size-4" aria-hidden />
            <span>Çıkış yap</span>
          </Button>
        </div>
      </div>
    </div>
  );
}

