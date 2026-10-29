"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePanelVisitTracker } from "@/lib/hooks/use-panel-visit-tracker";
import {
  Bug,
  ChevronDown,
  Search,
  Activity,
  AlertOctagon,
  BarChart3,
  BellRing,
  BookOpen,
  Building2,
  CalendarDays,
  FlaskConical,
  KeyRound,
  CircleDollarSign,
  ClipboardList,
  DatabaseZap,
  FileText,
  Flame,
  Gauge,
  Heart,
  Inbox,
  Bot,
  LayoutDashboard,
  LifeBuoy,
  Lightbulb,
  Link2,
  ListChecks,
  LogOut,
  UserCog,
  Megaphone,
  Menu,
  MessageSquare,
  MessagesSquare,
  Scale,
  Send,
  Settings,
  Shield,
  ShieldAlert,
  Sparkles,
  Star,
  Stethoscope,
  Share2,
  Target,
  Telescope,
  TrendingDown,
  TrendingUp,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";

import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { PhoneVerifyBanner } from "@/components/me/phone-verify-banner";
import { useLogout } from "@/lib/hooks/use-logout";
import { adminKeys, getAdminBadges } from "@/lib/api/admin";
import type { AdminBadgesResponse } from "@/lib/types/admin";
import type { UserPublic } from "@/lib/types/me";
import { ROLE_LABELS_TR } from "@/lib/types/me";

type AdminBadgeKey =
  | "support_pending"
  | "contact_new"
  | "unack_alarms"
  | "book_catalog_pending";

function adminBadgeValue(
  badges: AdminBadgesResponse | undefined,
  key: AdminBadgeKey | undefined,
): number {
  if (!key || !badges) return 0;
  return badges[key] ?? 0;
}

interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
  /**
   * P1 dışı sayfalar (P2+) — disabled görünür ama sidebar iskeletini
   * erkenden gösterir. Her paket teslim oldukça disabled kalkar.
   */
  disabled?: boolean;
  badgeKey?: AdminBadgeKey;
}

interface NavSection {
  title: string;
  icon?: LucideIcon;
  links: NavLink[];
  /** false → her zaman açık (Genel + Bekleyenler). */
  collapsible?: boolean;
}

/**
 * Süper Admin menüsü (2026-10-29 yeniden tasarım): 60'a yakın madde 8 düz
 * grupta hep açıktı → işleve göre gruplar, yalnız aktif sayfanın grubu açık,
 * kapalı grup başlığında bekleyen iş toplamı, üstte arama. Bekleyen işler
 * (talep/alarm) en üstte "Bekleyenler" grubunda.
 */
const NAV_SECTIONS: NavSection[] = [
  {
    title: "",
    collapsible: false,
    links: [
      { href: "/admin", label: "Panel", icon: LayoutDashboard },
      { href: "/admin/activity-stream", label: "Aktivite akışı", icon: Activity },
    ],
  },
  {
    title: "Bekleyenler",
    collapsible: false,
    links: [
      { href: "/admin/contact-requests", label: "İletişim talepleri", icon: Inbox, badgeKey: "contact_new" },
      { href: "/admin/support", label: "Destek talepleri", icon: LifeBuoy, badgeKey: "support_pending" },
      { href: "/admin/security-monitor/alarms", label: "Alarmlar", icon: AlertOctagon, badgeKey: "unack_alarms" },
    ],
  },
  {
    title: "Müşteriler",
    icon: Building2,
    links: [
      { href: "/admin/institutions", label: "Kurumlar", icon: Building2 },
      { href: "/admin/independent-teachers", label: "Bağımsız koçlar", icon: Users },
      { href: "/admin/users", label: "Tüm kullanıcılar", icon: Users },
      { href: "/admin/demo-sessions", label: "Demo hesaplar", icon: FlaskConical },
    ],
  },
  {
    title: "Gelir",
    icon: CircleDollarSign,
    links: [
      { href: "/admin/security-monitor/revenue", label: "Ticari genel bakış", icon: CircleDollarSign },
      { href: "/admin/revenue/action-center", label: "Aksiyon merkezi", icon: Target },
      { href: "/admin/revenue/forecast", label: "Gelir tahmini", icon: TrendingUp },
      { href: "/admin/revenue/cohort", label: "Kohort ve yaşam değeri", icon: Heart },
      { href: "/admin/payment-links", label: "Ödeme linkleri", icon: Link2 },
      { href: "/admin/pricing", label: "Ücretlendirme", icon: Wallet },
    ],
  },
  {
    title: "Pazarlama",
    icon: Send,
    links: [
      { href: "/admin/prospects", label: "Hedef havuzu", icon: Target },
      { href: "/admin/revenue/campaigns", label: "Kampanyalar", icon: Send },
      { href: "/admin/campaign-links", label: "Kampanya linkleri", icon: Share2 },
      { href: "/admin/membership-offers", label: "Üyelik teklifleri", icon: MessageSquare },
      { href: "/admin/revenue/action-templates", label: "Aksiyon şablonları", icon: ClipboardList },
      { href: "/admin/testimonials", label: "Yorumlar", icon: Star },
      { href: "/admin/analytics", label: "Site analitiği", icon: BarChart3 },
      { href: "/admin/conversion", label: "Dönüşüm hunisi", icon: TrendingDown },
    ],
  },
  {
    title: "Vitrin",
    icon: Lightbulb,
    links: [
      { href: "/admin/feature-catalog", label: "Kartlar", icon: Lightbulb },
      { href: "/admin/feature-catalog/dashboard", label: "Vitrin yönetimi", icon: Telescope },
      { href: "/admin/feature-catalog/experiments", label: "Deneyler", icon: ListChecks },
    ],
  },
  {
    title: "İletişim",
    icon: MessagesSquare,
    links: [
      { href: "/admin/announcements", label: "Duyurular", icon: Megaphone },
      { href: "/admin/whatsapp-templates", label: "WhatsApp şablonları", icon: MessageSquare },
      { href: "/admin/whatsapp-dispatch-log", label: "WhatsApp kayıtları", icon: Activity },
      { href: "/admin/communication-health", label: "İletişim sağlığı", icon: MessagesSquare },
      { href: "/admin/security-monitor/notifications", label: "Bildirim sağlığı", icon: BellRing },
      { href: "/admin/assistant", label: "Asistan soruları", icon: Bot },
    ],
  },
  {
    title: "Güvenlik",
    icon: Shield,
    links: [
      { href: "/admin/security-monitor", label: "Güvenlik kamarası", icon: Shield },
      { href: "/admin/security-monitor/live", label: "Canlı akış", icon: Activity },
      { href: "/admin/security-monitor/sessions", label: "Oturumlar", icon: ShieldAlert },
      { href: "/admin/security-monitor/abuse", label: "Suistimal", icon: Flame },
      { href: "/admin/security-monitor/activity", label: "Kullanım aktivitesi", icon: CalendarDays },
      { href: "/admin/audit", label: "Denetim kaydı", icon: FileText },
      { href: "/admin/kvkk", label: "KVKK", icon: Scale },
    ],
  },
  {
    title: "Sistem",
    icon: Settings,
    links: [
      { href: "/admin/system-health", label: "Altyapı sağlığı", icon: Stethoscope },
      { href: "/admin/security-monitor/system", label: "Uygulama hataları", icon: Bug },
      { href: "/admin/security-monitor/integrity", label: "Veri bütünlüğü", icon: DatabaseZap },
      { href: "/admin/book-catalog", label: "Kitap kataloğu", icon: BookOpen, badgeKey: "book_catalog_pending" },
      { href: "/admin/usage", label: "Kredi kullanımı", icon: Wallet },
      { href: "/admin/quota", label: "Limitler", icon: Gauge },
      { href: "/admin/feature-flags", label: "Özellik bayrakları", icon: Sparkles },
      { href: "/admin/settings", label: "AI ayarları", icon: KeyRound },
    ],
  },
];

/** Alarm niteliğindeki rozetler kırmızı; diğer bekleyen işler marka renginde. */
const ALARM_BADGES: AdminBadgeKey[] = ["unack_alarms"];

/** En uzun eşleşen href aktif sayılır (/admin/security-monitor ile alt sayfaları karışmasın). */
function activeHrefFor(pathname: string): string | null {
  let best: string | null = null;
  for (const sec of NAV_SECTIONS) {
    for (const l of sec.links) {
      const hit = l.href === "/admin" ? pathname === "/admin" : pathname === l.href || pathname.startsWith(`${l.href}/`);
      if (hit && (!best || l.href.length > best.length)) best = l.href;
    }
  }
  return best;
}

function normTr(s: string) {
  return s.toLocaleLowerCase("tr-TR").replace(/ı/g, "i").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

interface Props {
  user: UserPublic;
  children: React.ReactNode;
}

export function AdminShell({ user, children }: Props) {
  const pathname = usePathname();
  usePanelVisitTracker();
  const logout = useLogout();
  const [navOpen, setNavOpen] = React.useState(false);

  const badgesQ = useQuery<AdminBadgesResponse>({
    queryKey: adminKeys.badges(),
    queryFn: getAdminBadges,
    enabled: user.role === "super_admin",
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const badges = badgesQ.data;

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row">
      {/* Sidebar (lg+) */}
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:shrink-0 lg:sticky lg:top-0 lg:h-screen border-r border-border bg-card">
        <div className="px-4 h-14 flex items-center border-b border-border bg-background">
          <BrandLogo href="/admin" size={28} />
          <span className="ml-2 text-[10px] uppercase tracking-wider font-semibold bg-amber-100 text-amber-900 px-1.5 py-0.5 rounded">
            Süper
          </span>
        </div>
        <AdminNav pathname={pathname} badges={badges} />
        <UserCard
          user={user}
          onLogout={() => logout.mutate()}
          isLoggingOut={logout.isPending}
        />
      </aside>

      {/* Topbar (lg-) */}
      <header className="lg:hidden sticky top-0 z-30 border-b border-border bg-background">
        <div className="flex h-14 items-center gap-3 px-4">
          <BrandLogo href="/admin" size={28} className="shrink-0" />
          <span className="text-[10px] uppercase tracking-wider font-semibold bg-amber-100 text-amber-900 px-1.5 py-0.5 rounded">
            Süper
          </span>
          <div className="flex-1" />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setNavOpen(true)}
            className=""
            aria-label="Menüyü aç"
          >
            <Menu className="size-5" aria-hidden />
          </Button>
        </div>
      </header>

      <main className="flex-1 min-w-0">
        <PhoneVerifyBanner phoneVerified={user.phone_verified ?? true} />
        <div className="mx-auto max-w-7xl px-4 py-6 sm:py-8">{children}</div>
      </main>

      {navOpen ? (
        <MobileDrawer
          onClose={() => setNavOpen(false)}
          pathname={pathname}
          user={user}
          onLogout={() => logout.mutate()}
          badges={badges}
        />
      ) : null}
    </div>
  );
}

function AdminNav({
  pathname,
  badges,
  onItemClick,
}: {
  pathname: string;
  badges?: AdminBadgesResponse;
  onItemClick?: () => void;
}) {
  const activeHref = activeHrefFor(pathname);
  const [q, setQ] = React.useState("");
  const [opened, setOpened] = React.useState<Record<string, boolean>>({});
  const query = normTr(q.trim());

  const sections = query
    ? NAV_SECTIONS.map((sec) => ({
        ...sec,
        links: sec.links.filter((l) => normTr(`${l.label} ${sec.title}`).includes(query)),
      })).filter((sec) => sec.links.length > 0)
    : NAV_SECTIONS;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="px-3 pt-3">
        <label className="relative block">
          <span className="sr-only">Menüde ara</span>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Menüde ara…"
            className="h-9 w-full rounded-lg border border-input bg-background pl-8 pr-2 text-sm outline-none placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-ring/30"
          />
        </label>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-3" aria-label="Süper admin paneli">
        {sections.length === 0 ? (
          <p className="px-2 text-sm text-muted-foreground">Eşleşen sayfa yok.</p>
        ) : null}
        {sections.map((sec, idx) => {
          const hasActive = sec.links.some((l) => l.href === activeHref);
          const collapsible = sec.collapsible !== false && !query;
          const key = sec.title || `s${idx}`;
          const open = !collapsible || (opened[key] ?? hasActive);
          const pending = sec.links.reduce((n, l) => n + adminBadgeValue(badges, l.badgeKey), 0);
          const SecIcon = sec.icon;
          return (
            <div key={key} className={cn(idx > 0 && "mt-3")}>
              {sec.title ? (
                collapsible ? (
                  <button
                    type="button"
                    onClick={() => setOpened((o) => ({ ...o, [key]: !open }))}
                    aria-expanded={open}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-semibold transition-colors hover:bg-muted",
                      hasActive ? "text-primary" : "text-foreground",
                    )}
                  >
                    {SecIcon ? <SecIcon className="size-[18px] shrink-0" aria-hidden /> : null}
                    <span className="flex-1 text-left">{sec.title}</span>
                    {!open && pending > 0 ? <NavBadge count={pending} /> : null}
                    <ChevronDown className={cn("size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
                  </button>
                ) : (
                  <p className="mb-1 px-2 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    {sec.title}
                  </p>
                )
              ) : null}
              {open ? (
                <ul className={cn("space-y-0.5", collapsible && "mt-0.5 ml-[18px] border-l border-border pl-2")}>
                  {sec.links.map((link) => (
                    <li key={link.href}>
                      <SidebarLink
                        link={link}
                        active={link.href === activeHref}
                        onClick={onItemClick}
                        badge={adminBadgeValue(badges, link.badgeKey)}
                        nested={collapsible}
                      />
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
      </nav>
    </div>
  );
}

function NavBadge({ count, alarm = false }: { count: number; alarm?: boolean }) {
  if (count <= 0) return null;
  return (
    <span
      className={cn(
        "inline-flex h-5 min-w-[1.375rem] items-center justify-center rounded-full px-1.5 text-[11px] font-bold leading-none",
        alarm ? "bg-destructive text-destructive-foreground" : "bg-primary text-primary-foreground",
      )}
      aria-label={`${count} bekliyor`}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}

function SidebarLink({
  link,
  active,
  onClick,
  badge = 0,
  nested = false,
}: {
  link: NavLink;
  active: boolean;
  onClick?: () => void;
  badge?: number;
  nested?: boolean;
}) {
  const Icon = link.icon;
  return (
    <Link
      href={link.href}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex items-center gap-3 rounded-lg px-2.5 text-sm transition-colors",
        nested ? "py-1.5" : "py-2",
        active ? "bg-accent font-semibold text-accent-foreground" : "text-foreground hover:bg-muted",
      )}
    >
      {nested ? null : (
        <Icon
          className={cn("size-[18px] shrink-0", active ? "text-primary" : "text-muted-foreground group-hover:text-foreground")}
          aria-hidden
        />
      )}
      <span className="flex-1 break-words leading-snug">{link.label}</span>
      <NavBadge count={badge} alarm={!!link.badgeKey && ALARM_BADGES.includes(link.badgeKey)} />
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
          <Link href="/me/account" title="Hesabım, şifre ve iki aşamalı doğrulama">
            <UserCog className="size-4" aria-hidden />
            <span>Hesabım</span>
          </Link>
        </Button>
        <Button variant="outline" size="sm" className="justify-center" onClick={onLogout} disabled={isLoggingOut}>
          <LogOut className="size-4" aria-hidden />
          <span>{isLoggingOut ? "Çıkılıyor…" : "Çıkış"}</span>
        </Button>
      </div>
    </div>
  );
}

function MobileDrawer({
  onClose,
  pathname,
  user,
  onLogout,
  badges,
}: {
  onClose: () => void;
  pathname: string;
  user: UserPublic;
  onLogout: () => void;
  badges?: AdminBadgesResponse;
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
        <div className="flex items-center justify-between px-4 h-14 border-b border-border bg-background">
          <div className="leading-tight">
            <p className="text-sm font-medium truncate">{user.full_name}</p>
            <p className="text-xs text-muted-foreground inline-flex items-center gap-1">
              <Shield className="size-3 text-amber-400" aria-hidden />
              {ROLE_LABELS_TR[user.role]}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className=""
            aria-label="Kapat"
          >
            <X className="size-5" aria-hidden />
          </Button>
        </div>
        <AdminNav pathname={pathname} badges={badges} onItemClick={onClose} />
        <div className="p-3 border-t border-border space-y-2">
          <Button variant="ghost" className="w-full justify-start" asChild>
            <Link href="/me/account" onClick={onClose}>
              <UserCog className="size-4" aria-hidden />
              <span>Hesabım · Şifre · 2FA</span>
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
