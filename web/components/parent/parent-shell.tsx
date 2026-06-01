"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, HeartHandshake, LayoutDashboard, LogOut, Settings, X, Menu } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { useLogout } from "@/lib/hooks/use-logout";
import { PhoneVerifyBanner } from "@/components/me/phone-verify-banner";
import { ImpersonationBanner } from "@/components/impersonation-banner";
import type { UserPublic } from "@/lib/types/me";

/**
 * Veli paneli shell — teal-accent header + sade nav.
 *
 * Jinja parite: `app/templates/parent/base_parent.html` 3 link
 * (Panel / Bildirimler / Ayarlar). Veli teknik kullanıcı değil — sticky
 * sidebar yerine üst-bant header (mobil dostu + tek-bakışta).
 *
 * Fresh Next.js yaklaşımı: shadcn flavored, ETÜTKOÇ teal #117A86 brand
 * elementi korunur ama tasarım Jinja'dan kopya değil.
 */

interface Props {
  user: UserPublic;
  children: React.ReactNode;
}

interface NavLink {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  exact?: boolean;
}

const NAV_LINKS: NavLink[] = [
  { href: "/parent", label: "Panel", icon: LayoutDashboard, exact: true },
  { href: "/parent/notifications", label: "Bildirimler", icon: Bell },
  { href: "/parent/settings", label: "Ayarlar", icon: Settings },
];

export function ParentShell({ user, children }: Props) {
  const pathname = usePathname();
  const logout = useLogout();
  const [navOpen, setNavOpen] = React.useState(false);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Üst bant — teal accent (ETÜTKOÇ brand) */}
      <header className="sticky top-0 z-30 bg-gradient-to-r from-[#117A86] to-[#0E5F69] text-white shadow-sm">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2 min-w-0">
            <BrandLogo href="/parent" size={28} className="shrink-0" wordmarkClassName="text-white" />
            <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider bg-white/20 text-white">
              <HeartHandshake className="size-3" aria-hidden />
              Veli
            </span>
            <span className="text-white/80 text-xs truncate ml-1 hidden md:inline">
              {user.full_name}
            </span>
          </div>

          {/* Nav (md+) */}
          <nav
            className="hidden md:flex items-center gap-1 flex-1 justify-end"
            aria-label="Veli paneli"
          >
            {NAV_LINKS.map((link) => (
              <NavItem
                key={link.href}
                link={link}
                pathname={pathname}
              />
            ))}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              className="text-white/90 hover:bg-white/10 hover:text-white"
            >
              <LogOut className="size-4" aria-hidden />
              {logout.isPending ? "Çıkılıyor…" : "Çıkış"}
            </Button>
          </nav>

          {/* Mobile hamburger */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setNavOpen(true)}
            className="md:hidden text-white hover:bg-white/10 ml-auto"
            aria-label="Menüyü aç"
          >
            <Menu className="size-5" aria-hidden />
          </Button>
        </div>
      </header>

      <main className="flex-1">
        <ImpersonationBanner />
        <PhoneVerifyBanner phoneVerified={user.phone_verified ?? true} />
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
          {children}
        </div>
      </main>

      {navOpen && (
        <MobileDrawer
          onClose={() => setNavOpen(false)}
          pathname={pathname}
          user={user}
          onLogout={() => logout.mutate()}
          isLoggingOut={logout.isPending}
        />
      )}
    </div>
  );
}

function NavItem({
  link,
  pathname,
}: {
  link: NavLink;
  pathname: string;
}) {
  const Icon = link.icon;
  const active = link.exact
    ? pathname === link.href
    : pathname === link.href || pathname.startsWith(`${link.href}/`);
  return (
    <Link
      href={link.href}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "bg-white/20 text-white"
          : "text-white/85 hover:bg-white/10 hover:text-white",
      )}
    >
      <Icon className="size-4" aria-hidden />
      {link.label}
    </Link>
  );
}

function MobileDrawer({
  onClose,
  pathname,
  user,
  onLogout,
  isLoggingOut,
}: {
  onClose: () => void;
  pathname: string;
  user: UserPublic;
  onLogout: () => void;
  isLoggingOut: boolean;
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
      className="md:hidden fixed inset-0 z-40"
    >
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-hidden
      />
      <div className="absolute right-0 top-0 h-full w-72 max-w-[85vw] bg-card shadow-xl border-l border-border flex flex-col">
        <div className="flex items-center justify-between px-4 h-14 border-b border-border bg-gradient-to-r from-[#117A86] to-[#0E5F69] text-white">
          <div className="leading-tight">
            <p className="text-sm font-medium truncate">{user.full_name}</p>
            <p className="text-xs text-white/80">Veli görünümü</p>
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
        <nav className="flex-1 p-3 space-y-1" aria-label="Veli paneli">
          {NAV_LINKS.map((link) => {
            const Icon = link.icon;
            const active = link.exact
              ? pathname === link.href
              : pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors",
                  active
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden />
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border">
          <Button
            variant="outline"
            className="w-full"
            onClick={onLogout}
            disabled={isLoggingOut}
          >
            <LogOut className="size-4" aria-hidden />
            <span>{isLoggingOut ? "Çıkılıyor…" : "Çıkış yap"}</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
