"use client";

import { AlertTriangle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * RoleBanner — kullanıcının "olağan dışı" bir rolde gezindiğine dair sürekli
 * görünür uyarı. Tipik kullanım: impersonation, trial yaklaşan bitiş,
 * sistem duyurusu, askıya alınmış hesap.
 *
 * Eşdeğer: base.html role-ambient + impersonate-warning şeritleri.
 *
 * Dalga 0'da iskelet hâlinde — Dalga 5 (admin impersonation) ile aktif
 * akışa bağlanacak.
 */
export type RoleBannerSeverity = "info" | "warning" | "critical";

interface RoleBannerProps {
  severity?: RoleBannerSeverity;
  message: string;
  detail?: string;
  /** Aksiyon butonu (örn. "Sona erdir"). */
  action?: { label: string; onClick: () => void };
  /** Kapatılabilir mi (info için true, critical için false önerilir). */
  dismissible?: boolean;
  onDismiss?: () => void;
}

const SEVERITY_STYLES: Record<RoleBannerSeverity, string> = {
  info: "bg-accent/10 text-accent-foreground border-accent/30",
  warning: "bg-status-dikkat/15 text-foreground border-status-dikkat/40",
  critical: "bg-status-risk/15 text-foreground border-status-risk/40",
};

export function RoleBanner({
  severity = "info",
  message,
  detail,
  action,
  dismissible = false,
  onDismiss,
}: RoleBannerProps) {
  return (
    <div
      role={severity === "critical" ? "alert" : "status"}
      className={cn(
        "w-full border-b px-4 py-2 text-sm flex items-center gap-3",
        SEVERITY_STYLES[severity]
      )}
    >
      <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
      <div className="flex-1 flex items-center gap-2 flex-wrap">
        <span className="font-medium">{message}</span>
        {detail ? <span className="text-muted-foreground">— {detail}</span> : null}
      </div>
      {action ? (
        <Button size="sm" variant="outline" onClick={action.onClick}>
          {action.label}
        </Button>
      ) : null}
      {dismissible ? (
        <Button
          size="icon"
          variant="ghost"
          onClick={onDismiss}
          aria-label="Bildirimi kapat"
          className="h-7 w-7"
        >
          <X className="size-4" />
        </Button>
      ) : null}
    </div>
  );
}
