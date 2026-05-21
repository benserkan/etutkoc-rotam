"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardCheck,
  GraduationCap,
  HeartHandshake,
  Siren,
  Building2,
  CalendarDays,
  Flame,
  Gauge,
  LayoutDashboard,
  LineChart,
  LogOut,
  Mail,
  Menu,
  ScrollText,
  Target,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { useLogout } from "@/lib/hooks/use-logout";
import type { InstitutionRef, UserPublic } from "@/lib/types/me";
import { ROLE_LABELS_TR } from "@/lib/types/me";

interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
  /**
   * P4 dışı sayfalar (P5+P6+P7'de gelecek) — disabled görünür ama
   * sidebar iskeletini erkenden gösterir, kullanıcı "yakında" sezer.
   */
  disabled?: boolean;
}

interface NavSection {
  title: string;
  links: NavLink[];
}

/**
 * 13 menü item'ı Jinja `base.html:516-552`'deki 3 grup ile birebir uyumlu.
 * Dropdown YOK; düz section header → 1 tıkla erişim. Disabled item'lar
 * P4 sonrası paketlerde aktive olur.
 */
const NAV_SECTIONS: NavSection[] = [
  {
    title: "",
    links: [
      { href: "/institution", label: "Panel", icon: LayoutDashboard },
    ],
  },
  {
    title: "Kişiler",
    links: [
      { href: "/institution/teachers", label: "Öğretmenler", icon: Users },
      { href: "/institution/invitations", label: "Davet", icon: Mail },
      { href: "/institution/roster", label: "Roster", icon: ScrollText },
    ],
  },
  {
    title: "Analiz",
    links: [
      {
        href: "/institution/action-center",
        label: "Müdahale Merkezi",
        icon: Siren,
      },
      {
        href: "/institution/compliance",
        label: "Program Uyumu",
        icon: ClipboardCheck,
      },
      {
        href: "/institution/academic",
        label: "Akademik Çıktı",
        icon: LineChart,
      },
      {
        href: "/institution/at-risk",
        label: "Risk Paneli",
        icon: AlertTriangle,
      },
      { href: "/institution/cohorts", label: "Kohort", icon: BarChart3 },
      {
        href: "/institution/activity-heatmap",
        label: "Aktivite",
        icon: Activity,
      },
      { href: "/institution/burnout", label: "Tükenmişlik", icon: Flame },
      {
        href: "/institution/teacher-scorecard",
        label: "Öğretmen Karnesi",
        icon: GraduationCap,
      },
      { href: "/institution/goals", label: "Hedef Analizi", icon: Target },
      {
        href: "/institution/admin-digest",
        label: "Haftalık Özet",
        icon: Mail,
      },
      {
        href: "/institution/parent-trust",
        label: "Veli Güveni",
        icon: HeartHandshake,
      },
    ],
  },
  {
    title: "Üyelik",
    links: [
      {
        href: "/institution/subscription",
        label: "Abonelik",
        icon: CalendarDays,
      },
      {
        href: "/institution/usage",
        label: "Kredi Kullanımı",
        icon: Wallet,
      },
      {
        href: "/institution/quota",
        label: "Limitler",
        icon: Gauge,
      },
    ],
  },
];

interface Props {
  user: UserPublic;
  institution: InstitutionRef | null;
  children: React.ReactNode;
}

/**
 * Kurum Yöneticisi shell — sticky sidebar (lg+) + üst topbar (mobil drawer).
 *
 * Jinja parite:
 *   - 13 menü linki Jinja `base.html:516-552`'deki 3 grup yapısında
 *   - Kurum bağlam chip'i (header — Jinja'da emerald accent)
 *   - "Yeni öğretmen ekle" ve diğer eylemler her sayfada kendi içinde
 */
export function InstitutionShell({ user, institution, children }: Props) {
  const pathname = usePathname();
  const logout = useLogout();
  const [navOpen, setNavOpen] = React.useState(false);

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row">
      {/* Sidebar (lg+) */}
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:shrink-0 lg:sticky lg:top-0 lg:h-screen border-r border-border bg-card/40">
        <div className="px-4 h-14 flex items-center border-b border-border">
          <BrandLogo href="/institution" size={28} />
        </div>
        {institution ? (
          <InstitutionChip institution={institution} />
        ) : null}
        <nav
          className="flex-1 overflow-y-auto p-2 space-y-3"
          aria-label="Kurum yöneticisi paneli"
        >
          {NAV_SECTIONS.map((section, idx) => (
            <NavGroup
              key={`${section.title}-${idx}`}
              section={section}
              pathname={pathname}
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
          <BrandLogo href="/institution" size={28} className="shrink-0" />
          {institution ? (
            <span
              className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 truncate max-w-[200px]"
              title={institution.name}
            >
              <Building2 className="size-3" aria-hidden />
              {institution.name}
            </span>
          ) : null}
          <div className="flex-1" />
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
          institution={institution}
          onLogout={() => logout.mutate()}
        />
      ) : null}
    </div>
  );
}

function InstitutionChip({ institution }: { institution: InstitutionRef }) {
  return (
    <div className="px-4 py-2 border-b border-border">
      <div
        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 max-w-full"
        title={institution.name}
      >
        <Building2 className="size-3 shrink-0" aria-hidden />
        <span className="truncate">{institution.name}</span>
      </div>
    </div>
  );
}

function NavGroup({
  section,
  pathname,
  onItemClick,
}: {
  section: NavSection;
  pathname: string;
  onItemClick?: () => void;
}) {
  return (
    <div>
      {section.title ? (
        <p className="px-3 mb-1 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
          {section.title}
        </p>
      ) : null}
      <div className="space-y-0.5">
        {section.links.map((link) => (
          <SidebarLink
            key={link.href}
            link={link}
            pathname={pathname}
            onClick={onItemClick}
          />
        ))}
      </div>
    </div>
  );
}

function SidebarLink({
  link,
  pathname,
  onClick,
}: {
  link: NavLink;
  pathname: string;
  onClick?: () => void;
}) {
  const Icon = link.icon;
  // /institution (panel) sadece exact match; sub-route'lar (teachers vs.) startsWith
  const active =
    link.href === "/institution"
      ? pathname === "/institution"
      : pathname === link.href || pathname.startsWith(`${link.href}/`);

  if (link.disabled) {
    return (
      <div
        className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground/60 cursor-not-allowed"
        title="Yakında — bir sonraki pakette gelecek"
      >
        <Icon className="size-4 shrink-0" aria-hidden />
        <span className="flex-1 truncate">{link.label}</span>
        <span className="text-[10px] uppercase tracking-wider opacity-60">
          yakında
        </span>
      </div>
    );
  }

  return (
    <Link
      href={link.href}
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-muted font-medium text-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      <span className="flex-1 truncate">{link.label}</span>
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
        <LogOut className="size-4" aria-hidden />
        <span>{isLoggingOut ? "Çıkılıyor…" : "Çıkış"}</span>
      </Button>
    </div>
  );
}

function MobileDrawer({
  onClose,
  pathname,
  user,
  institution,
  onLogout,
}: {
  onClose: () => void;
  pathname: string;
  user: UserPublic;
  institution: InstitutionRef | null;
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
        {institution ? (
          <div className="px-4 py-2 border-b border-border">
            <div
              className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 max-w-full"
              title={institution.name}
            >
              <Building2 className="size-3 shrink-0" aria-hidden />
              <span className="truncate">{institution.name}</span>
            </div>
          </div>
        ) : null}
        <nav
          className="flex-1 overflow-y-auto p-2 space-y-3"
          aria-label="Kurum yöneticisi paneli"
        >
          {NAV_SECTIONS.map((section, idx) => (
            <NavGroup
              key={`${section.title}-${idx}`}
              section={section}
              pathname={pathname}
              onItemClick={onClose}
            />
          ))}
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

