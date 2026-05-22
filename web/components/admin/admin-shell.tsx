"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertOctagon,
  BellRing,
  Building2,
  CalendarDays,
  KeyRound,
  CircleDollarSign,
  ClipboardList,
  DatabaseZap,
  FileText,
  Flame,
  Gauge,
  Heart,
  Inbox,
  LayoutDashboard,
  Lightbulb,
  ListChecks,
  LogOut,
  Megaphone,
  Menu,
  Scale,
  Send,
  Settings,
  Shield,
  ShieldAlert,
  Sparkles,
  Stethoscope,
  Target,
  Telescope,
  TrendingUp,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { useLogout } from "@/lib/hooks/use-logout";
import type { UserPublic } from "@/lib/types/me";
import { ROLE_LABELS_TR } from "@/lib/types/me";

interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
  /**
   * P1 dışı sayfalar (P2+) — disabled görünür ama sidebar iskeletini
   * erkenden gösterir. Her paket teslim oldukça disabled kalkar.
   */
  disabled?: boolean;
}

interface NavSection {
  title: string;
  links: NavLink[];
}

/**
 * Süper Admin shell — sticky sidebar (lg+) + üst topbar (mobil drawer).
 *
 * Jinja parite: `base.html:482-515` (3 dropdown: Kuruluşlar/Sistem/Denetim)
 * + dashboard'daki Ticari ve Güvenlik kart grupları sidebar'a entegre.
 *
 * Tasarım yaklaşımı: kullanıcı "menü sistemleri özgür" dedi — fresh shadcn
 * sticky sidebar (institution shell pattern'i ile aynı yapı), 5 mantıksal
 * grup. Disabled item'lar P2-P14'te aktive olur.
 */
const NAV_SECTIONS: NavSection[] = [
  {
    title: "",
    links: [
      { href: "/admin", label: "Panel", icon: LayoutDashboard },
    ],
  },
  {
    title: "Kuruluşlar",
    links: [
      { href: "/admin/institutions", label: "Kurumlar", icon: Building2 },
      { href: "/admin/users", label: "Kullanıcılar", icon: Users },
      { href: "/admin/independent-teachers", label: "Bağımsız Öğretmenler", icon: Users },
    ],
  },
  {
    title: "Denetim",
    links: [
      { href: "/admin/audit", label: "Audit Log", icon: FileText },
      { href: "/admin/kvkk", label: "KVKK", icon: Scale },
      { href: "/admin/system-health", label: "Sistem Sağlığı", icon: Stethoscope },
      { href: "/admin/announcements", label: "Duyurular", icon: Megaphone },
    ],
  },
  {
    title: "Limitler & Kullanım",
    links: [
      { href: "/admin/usage", label: "Kredi Kullanımı", icon: Wallet },
      { href: "/admin/quota", label: "Limitler", icon: Gauge },
      { href: "/admin/feature-flags", label: "Özellik Bayrakları", icon: Sparkles },
    ],
  },
  {
    title: "Vitrin",
    links: [
      { href: "/admin/feature-catalog", label: "Kartlar", icon: Lightbulb },
      { href: "/admin/feature-catalog/dashboard", label: "Vitrin Yönetimi", icon: Telescope },
      { href: "/admin/feature-catalog/experiments", label: "Deneyler", icon: ListChecks },
    ],
  },
  {
    title: "Ticari Pano",
    links: [
      { href: "/admin/security-monitor/revenue", label: "Genel Bakış", icon: CircleDollarSign },
      { href: "/admin/revenue/action-center", label: "Aksiyon Merkezi", icon: Target },
      { href: "/admin/revenue/forecast", label: "Tahmin", icon: TrendingUp },
      { href: "/admin/revenue/cohort", label: "Kohort & LTV", icon: Heart },
      { href: "/admin/revenue/campaigns", label: "Kampanyalar", icon: Send },
      { href: "/admin/revenue/action-templates", label: "Şablonlar", icon: ClipboardList },
    ],
  },
  {
    title: "Güvenlik Kamarası",
    links: [
      { href: "/admin/security-monitor", label: "Genel Bakış", icon: Shield },
      { href: "/admin/security-monitor/integrity", label: "Veri Bütünlüğü", icon: DatabaseZap },
      { href: "/admin/security-monitor/system", label: "Sistem Sağlığı", icon: Stethoscope },
      { href: "/admin/security-monitor/notifications", label: "Bildirim Sağlığı", icon: BellRing },
      { href: "/admin/security-monitor/live", label: "Canlı Akış", icon: Activity },
      { href: "/admin/security-monitor/sessions", label: "Oturumlar", icon: ShieldAlert },
      { href: "/admin/security-monitor/alarms", label: "Alarmlar", icon: AlertOctagon },
      { href: "/admin/security-monitor/abuse", label: "Suistimal", icon: Flame },
      { href: "/admin/security-monitor/activity", label: "Aktivite", icon: CalendarDays },
    ],
  },
  {
    title: "Sistem",
    links: [
      { href: "/admin/settings", label: "AI Ayarları", icon: KeyRound },
      { href: "/admin/pricing", label: "Ücretlendirme", icon: CircleDollarSign },
      { href: "/admin/contact-requests", label: "İletişim Talepleri", icon: Inbox },
    ],
  },
];

interface Props {
  user: UserPublic;
  children: React.ReactNode;
}

export function AdminShell({ user, children }: Props) {
  const pathname = usePathname();
  const logout = useLogout();
  const [navOpen, setNavOpen] = React.useState(false);

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row">
      {/* Sidebar (lg+) */}
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:shrink-0 lg:sticky lg:top-0 lg:h-screen border-r border-border bg-card/40">
        <div className="px-4 h-14 flex items-center border-b border-border bg-gradient-to-r from-slate-900 to-slate-800 text-white">
          <BrandLogo href="/admin" size={28} wordmarkClassName="text-white" />
          <span className="ml-2 text-[10px] uppercase tracking-wider font-semibold bg-amber-400/20 text-amber-100 px-1.5 py-0.5 rounded">
            Süper
          </span>
        </div>
        <nav
          className="flex-1 overflow-y-auto p-2 space-y-3"
          aria-label="Süper admin paneli"
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
      <header className="lg:hidden sticky top-0 z-30 border-b border-border bg-slate-900 text-white">
        <div className="flex h-14 items-center gap-3 px-4">
          <BrandLogo href="/admin" size={28} className="shrink-0" wordmarkClassName="text-white" />
          <span className="text-[10px] uppercase tracking-wider font-semibold bg-amber-400/20 text-amber-100 px-1.5 py-0.5 rounded">
            Süper
          </span>
          <div className="flex-1" />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setNavOpen(true)}
            className="text-white hover:bg-white/10"
            aria-label="Menüyü aç"
          >
            <Menu className="size-5" aria-hidden />
          </Button>
        </div>
      </header>

      <main className="flex-1 min-w-0">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:py-8">{children}</div>
      </main>

      {navOpen ? (
        <MobileDrawer
          onClose={() => setNavOpen(false)}
          pathname={pathname}
          user={user}
          onLogout={() => logout.mutate()}
        />
      ) : null}
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
  const active =
    link.href === "/admin"
      ? pathname === "/admin"
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
        <p className="text-xs text-muted-foreground inline-flex items-center gap-1">
          <Settings className="size-3" aria-hidden />
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
  onLogout,
}: {
  onClose: () => void;
  pathname: string;
  user: UserPublic;
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
        <div className="flex items-center justify-between px-4 h-14 border-b border-border bg-gradient-to-r from-slate-900 to-slate-800 text-white">
          <div className="leading-tight">
            <p className="text-sm font-medium truncate">{user.full_name}</p>
            <p className="text-xs text-white/70 inline-flex items-center gap-1">
              <Shield className="size-3 text-amber-400" aria-hidden />
              {ROLE_LABELS_TR[user.role]}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="text-white hover:bg-white/10"
            aria-label="Kapat"
          >
            <X className="size-5" aria-hidden />
          </Button>
        </div>
        <nav
          className="flex-1 overflow-y-auto p-2 space-y-3"
          aria-label="Süper admin paneli"
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
