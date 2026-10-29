"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePanelVisitTracker } from "@/lib/hooks/use-panel-visit-tracker";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ChevronDown,
  BookOpen,
  CalendarRange,
  Compass,
  Gauge,
  Gem,
  Inbox,
  LayoutDashboard,
  LifeBuoy,
  Link2,
  Loader2,
  LogOut,
  Menu,
  MessageSquare,
  Settings,
  UserCog,
  Users,
  Video,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ShellBrand } from "@/components/shell-brand";
import type { BrandRef } from "@/lib/types/me";
import type { InstitutionRef } from "@/lib/types/me";
import { useLogout } from "@/lib/hooks/use-logout";
import { getTeacherBadges, teacherKeys } from "@/lib/api/teacher";
import { TrialBanner } from "@/components/teacher/trial-banner";
import { GuideWelcomeDialog } from "@/components/guide/guide-welcome-dialog";
import { PhoneVerifyBanner } from "@/components/me/phone-verify-banner";
import { ImpersonationBanner } from "@/components/impersonation-banner";
import { AiJobsTracker } from "@/components/shared/ai-jobs-tracker";
import type { TeacherBadgesResponse } from "@/lib/types/teacher";
import type { UserPublic } from "@/lib/types/me";
import { ROLE_LABELS_TR } from "@/lib/types/me";

interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
  // Badge gösterimi için anahtar — badges response'unun field adı
  badgeKey?:
    | "pending_request_count"
    | "at_risk_count"
    | "support_answered_count"
    | "support_inbox_pending"
    | "unlinked_test_tasks";
  /** Yalnız kuruma bağlı öğretmende görünür. */
  institutionOnly?: boolean;
}

/**
 * Menü grupları (2026-10-29 yeniden tasarım): düz 16 maddelik liste yerine işleve
 * göre gruplar. Günlük işler en üstte etiketsiz; seyrek kullanılan yönetim
 * sayfaları katlanır grupta (aktif sayfa içindeyse kendiliğinden açık).
 */
interface NavGroup {
  label: string | null;
  items: NavLink[];
  collapsible?: boolean;
}

const TEACHER_GROUPS: NavGroup[] = [
  {
    label: null,
    items: [
      { href: "/teacher/dashboard", label: "Pano", icon: LayoutDashboard },
      { href: "/teacher/students", label: "Öğrenciler", icon: Users, badgeKey: "at_risk_count" },
      { href: "/teacher/appointments", label: "Görüşmeler", icon: Video },
    ],
  },
  {
    label: "İletişim",
    items: [
      { href: "/teacher/requests", label: "Öğrenci talepleri", icon: Inbox, badgeKey: "pending_request_count" },
      { href: "/teacher/bulk-wa", label: "Toplu WhatsApp", icon: MessageSquare },
      { href: "/teacher/support-inbox", label: "Kurumdan gelenler", icon: Inbox, badgeKey: "support_inbox_pending", institutionOnly: true },
      { href: "/teacher/support", label: "Destek", icon: LifeBuoy, badgeKey: "support_answered_count" },
    ],
  },
  {
    label: "Program ve kaynak",
    items: [
      { href: "/teacher/library", label: "Kitaplar", icon: BookOpen },
      { href: "/teacher/unlinked-tasks", label: "Konusuz görevler", icon: Link2, badgeKey: "unlinked_test_tasks" },
    ],
  },
  {
    label: "İşletme",
    items: [
      { href: "/teacher/billing", label: "Tahsilat", icon: Wallet },
      { href: "/teacher/plan", label: "Paket", icon: Gem },
      { href: "/teacher/usage", label: "Kullanım", icon: Gauge },
    ],
  },
  {
    label: "Yönetim",
    collapsible: true,
    items: [
      { href: "/teacher/academic-years", label: "Akademik yıllar", icon: CalendarRange },
      { href: "/teacher/grade-advance", label: "Sınıf yükseltme", icon: ArrowUpRight },
      { href: "/teacher/settings", label: "Ayarlar", icon: Settings },
      { href: "/teacher/guide", label: "Rehber", icon: Compass },
    ],
  },
];

/** Alarm rozeti kırmızı; yapılacak-iş sayıları marka renginde (her sayı alarm değildir). */
const ALARM_BADGES: NonNullable<NavLink["badgeKey"]>[] = ["at_risk_count"];

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function visibleGroups(hasInstitution: boolean): NavGroup[] {
  return TEACHER_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => !i.institutionOnly || hasInstitution),
  })).filter((g) => g.items.length > 0);
}

interface Props {
  user: UserPublic;
  institution?: InstitutionRef | null;
  /** Kurumsal kimlik — kuruma bağlı öğretmende kurum logosu/adı. */
  brand?: BrandRef | null;
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
export function TeacherShell({ user, institution, brand, children }: Props) {
  const pathname = usePathname();
  usePanelVisitTracker();
  const logout = useLogout();
  const [navOpen, setNavOpen] = React.useState(false);

  const groups = visibleGroups(!!institution);
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
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:shrink-0 lg:sticky lg:top-0 lg:h-screen border-r border-border bg-card">
        <div className="px-4 min-h-14 py-3 flex items-center border-b border-border">
          <ShellBrand brand={brand ?? null} href="/teacher/dashboard" size={28} variant="sidebar" />
        </div>
        <NavGroups groups={groups} pathname={pathname} badges={badges.data} />
        <UserCard
          user={user}
          onLogout={() => logout.mutate()}
          isLoggingOut={logout.isPending}
        />
      </aside>

      {/* Topbar (lg-) */}
      <header className="lg:hidden sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="flex min-h-16 items-center gap-3 px-4 py-1.5">
          <ShellBrand brand={brand ?? null} href="/teacher/dashboard" size={28} className="shrink-0" />
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
        <ImpersonationBanner />
        <AiJobsTracker audience="teacher" />
        <PhoneVerifyBanner phoneVerified={user.phone_verified ?? true} />
        <TrialBanner enabled={user.role === "teacher"} />
        <GuideWelcomeDialog
          enabled={user.role === "teacher"}
          guideKey="coach_onboarding"
          guideHref="/teacher/guide"
          brandName={brand?.name ?? null}
          description="Sana sistemi adım adım, sesli anlatımla göstereceğim: kitap eklemekten haftalık program kurmaya, veli bilgilendirmesinden deneme analizine. Kurulum adımlarında sıra sana da geçer — sen yaparsın, ben kontrol ederim. Bölüm bölüm ilerler; istediğin an ara verip kaldığın yerden devam edersin."
          menuHint="Sol menüdeki Rehber bağlantısından dilediğin an başlatabilirsin."
        />
        <div className="mx-auto max-w-6xl px-4 py-6 sm:py-8">{children}</div>
      </main>

      {navOpen ? (
        <MobileDrawer
          onClose={() => setNavOpen(false)}
          pathname={pathname}
          user={user}
          badges={badges.data}
          groups={groups}
          onLogout={() => logout.mutate()}
        />
      ) : null}
    </div>
  );
}

function NavGroups({
  groups,
  pathname,
  badges,
  onNavigate,
}: {
  groups: NavGroup[];
  pathname: string;
  badges: TeacherBadgesResponse | undefined;
  onNavigate?: () => void;
}) {
  return (
    <nav className="flex-1 overflow-y-auto px-3 py-3" aria-label="Öğretmen paneli">
      {groups.map((g, gi) => (
        <NavSection
          key={g.label ?? gi}
          group={g}
          pathname={pathname}
          badges={badges}
          onNavigate={onNavigate}
          first={gi === 0}
        />
      ))}
    </nav>
  );
}

function NavSection({
  group,
  pathname,
  badges,
  onNavigate,
  first,
}: {
  group: NavGroup;
  pathname: string;
  badges: TeacherBadgesResponse | undefined;
  onNavigate?: () => void;
  first: boolean;
}) {
  const hasActive = group.items.some((i) => isActive(pathname, i.href));
  const [manualOpen, setManualOpen] = React.useState(false);
  const open = !group.collapsible || manualOpen || hasActive;
  return (
    <div className={cn(!first && "mt-4")}>
      {group.label ? (
        group.collapsible ? (
          <button
            type="button"
            onClick={() => setManualOpen((v) => !v)}
            aria-expanded={open}
            className="mb-1 flex w-full items-center justify-between rounded-md px-2 py-1 text-[11px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground"
          >
            {group.label}
            <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} aria-hidden />
          </button>
        ) : (
          <p className="mb-1 px-2 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            {group.label}
          </p>
        )
      ) : null}
      {open ? (
        <ul className="space-y-0.5">
          {group.items.map((n) => (
            <li key={n.href}>
              <SidebarLink
                link={n}
                pathname={pathname}
                badgeValue={n.badgeKey ? badges?.[n.badgeKey] ?? 0 : 0}
                onNavigate={onNavigate}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SidebarLink({
  link,
  pathname,
  badgeValue,
  onNavigate,
}: {
  link: NavLink;
  pathname: string;
  badgeValue: number;
  onNavigate?: () => void;
}) {
  const active = isActive(pathname, link.href);
  const Icon = link.icon;
  const alarm = link.badgeKey ? ALARM_BADGES.includes(link.badgeKey) : false;
  return (
    <Link
      href={link.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors",
        active ? "bg-accent font-semibold text-accent-foreground" : "text-foreground hover:bg-muted",
      )}
    >
      {active ? (
        <span className="absolute -left-3 top-1.5 bottom-1.5 w-1 rounded-r-full bg-primary" aria-hidden />
      ) : null}
      <Icon
        className={cn(
          "size-[18px] shrink-0",
          active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
        )}
        aria-hidden
      />
      <span className="flex-1 break-words leading-snug">{link.label}</span>
      {badgeValue > 0 ? (
        <span
          className={cn(
            "inline-flex h-5 min-w-[1.375rem] items-center justify-center rounded-full px-1.5 text-[11px] font-bold leading-none",
            alarm ? "bg-destructive text-destructive-foreground" : "bg-primary text-primary-foreground",
          )}
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
  const initials = user.full_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toLocaleUpperCase("tr-TR"))
    .join("");
  return (
    <div className="border-t border-border p-3">
      <div className="flex items-center gap-2.5 px-1.5 py-1">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
          {initials}
        </span>
        <div className="min-w-0 flex-1 leading-tight">
          <p className="break-words text-sm font-semibold">{user.full_name}</p>
          <p className="text-xs text-muted-foreground">{ROLE_LABELS_TR[user.role]}</p>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <Button variant="outline" size="sm" className="justify-center" asChild>
          <Link href="/me/account" title="Hesabım ve şifre">
            <UserCog className="size-4" aria-hidden />
            <span>Hesabım</span>
          </Link>
        </Button>
        <Button variant="outline" size="sm" className="justify-center" onClick={onLogout} disabled={isLoggingOut}>
          {isLoggingOut ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <LogOut className="size-4" aria-hidden />
          )}
          <span>Çıkış</span>
        </Button>
      </div>
    </div>
  );
}

function MobileDrawer({
  onClose,
  pathname,
  user,
  badges,
  groups,
  onLogout,
}: {
  onClose: () => void;
  pathname: string;
  user: UserPublic;
  badges: TeacherBadgesResponse | undefined;
  groups: NavGroup[];
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
        <NavGroups groups={groups} pathname={pathname} badges={badges} onNavigate={onClose} />
        <div className="p-3 border-t border-border space-y-2">
          <Button variant="ghost" className="w-full justify-start" asChild>
            <Link href="/me/account" onClick={onClose}>
              <UserCog className="size-4" aria-hidden />
              <span>Hesabım &amp; Şifre</span>
            </Link>
          </Button>
          <Button variant="outline" className="w-full" onClick={onLogout}>
            <LogOut className="size-4" aria-hidden />
            <span>Çıkış yap</span>
          </Button>
        </div>
      </div>
    </div>
  );
}

