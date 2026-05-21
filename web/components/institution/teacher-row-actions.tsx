"use client";

import * as React from "react";
import { Loader2, MoreHorizontal, Pause, Play, ShieldOff, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useActivateInstitutionTeacher,
  useDeactivateInstitutionTeacher,
  usePauseTeacherAlerts,
  useResumeTeacherAlerts,
} from "@/lib/hooks/use-institution-mutations";
import type { TeacherSummaryItem } from "@/lib/types/institution";

type ActionKind = "deactivate" | "activate" | "pause-alerts" | "resume-alerts";

/**
 * Öğretmen satır eylemleri — Jinja `teachers_list.html:89-117` ile birebir.
 *
 * 2 eylem grubu:
 *   - Uyarı susturma (pause/resume-alerts) — hesap çalışır, alert akışı durur
 *   - Hesap kapatma (deactivate/activate) — giriş engelli
 *
 * Pasif hesabın "Pasife al / Aktif et" (uyarı) butonu görünmez (Jinja paritesi).
 * Tüm destructive eylemler AlertDialog onayı ister; metinler Jinja ile aynı.
 */
export function TeacherRowActions({ teacher }: { teacher: TeacherSummaryItem }) {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [confirm, setConfirm] = React.useState<ActionKind | null>(null);
  const menuRef = React.useRef<HTMLDivElement | null>(null);

  const deactivate = useDeactivateInstitutionTeacher();
  const activate = useActivateInstitutionTeacher();
  const pause = usePauseTeacherAlerts();
  const resume = useResumeTeacherAlerts();

  const isPending =
    deactivate.isPending ||
    activate.isPending ||
    pause.isPending ||
    resume.isPending;

  React.useEffect(() => {
    if (!menuOpen) return;
    function onDoc(e: MouseEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  function ask(kind: ActionKind) {
    setMenuOpen(false);
    setConfirm(kind);
  }

  function execute(kind: ActionKind) {
    const id = teacher.id;
    const after = () => setConfirm(null);
    if (kind === "deactivate") {
      deactivate.mutate(id, { onSuccess: after, onError: after });
    } else if (kind === "activate") {
      activate.mutate(id, { onSuccess: after, onError: after });
    } else if (kind === "pause-alerts") {
      pause.mutate(id, { onSuccess: after, onError: after });
    } else if (kind === "resume-alerts") {
      resume.mutate(id, { onSuccess: after, onError: after });
    }
  }

  return (
    <>
      <div className="relative inline-block" ref={menuRef}>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMenuOpen((v) => !v)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label="Eylemler"
          disabled={isPending}
        >
          {isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <MoreHorizontal className="size-4" aria-hidden />
          )}
        </Button>
        {menuOpen ? (
          <div
            role="menu"
            className="absolute right-0 top-full mt-1 z-30 min-w-[180px] rounded-md border border-border bg-popover shadow-md p-1 text-sm"
          >
            {teacher.is_active && teacher.is_paused && (
              <MenuItem
                icon={<Play className="size-4" aria-hidden />}
                label="Uyarıları aç"
                onClick={() => ask("resume-alerts")}
              />
            )}
            {teacher.is_active && !teacher.is_paused && (
              <MenuItem
                icon={<Pause className="size-4" aria-hidden />}
                label="Pasife al (uyarıları sustur)"
                onClick={() => ask("pause-alerts")}
              />
            )}
            {teacher.is_active && (
              <MenuItem
                icon={<ShieldOff className="size-4" aria-hidden />}
                label="Hesabı kapat"
                danger
                onClick={() => ask("deactivate")}
              />
            )}
            {!teacher.is_active && (
              <MenuItem
                icon={<ShieldCheck className="size-4" aria-hidden />}
                label="Hesabı aç"
                onClick={() => ask("activate")}
              />
            )}
          </div>
        ) : null}
      </div>

      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(o) => !o && setConfirm(null)}
        teacher={teacher}
        kind={confirm}
        pending={isPending}
        onConfirm={() => confirm && execute(confirm)}
      />
    </>
  );
}

function MenuItem({
  icon,
  label,
  onClick,
  danger,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={`flex w-full items-center gap-2 px-2.5 py-1.5 rounded-sm text-left hover:bg-muted ${
        danger ? "text-rose-700 hover:text-rose-800" : ""
      }`}
    >
      {icon}
      <span className="flex-1">{label}</span>
    </button>
  );
}

function ConfirmDialog({
  open,
  onOpenChange,
  teacher,
  kind,
  pending,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  teacher: TeacherSummaryItem;
  kind: ActionKind | null;
  pending: boolean;
  onConfirm: () => void;
}) {
  const info = describeAction(teacher.full_name, kind);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{info.title}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">{info.message}</p>
        <DialogFooter className="gap-2 pt-2">
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={pending}
          >
            Vazgeç
          </Button>
          <Button
            variant={info.destructive ? "destructive" : "default"}
            onClick={onConfirm}
            disabled={pending}
          >
            {pending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            {info.confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function describeAction(name: string, kind: ActionKind | null) {
  // Jinja paritesi — `teachers_list.html:99,109` onconfirm metinleri.
  switch (kind) {
    case "deactivate":
      return {
        title: "Hesabı kapat",
        message: `${name} HESAP devre dışı bırakılsın? Giriş yapamaz, verisi korunur.`,
        confirm: "Hesabı kapat",
        destructive: true,
      };
    case "activate":
      return {
        title: "Hesabı aç",
        message: `${name} hesabı tekrar etkin hale getirilsin?`,
        confirm: "Hesabı aç",
        destructive: false,
      };
    case "pause-alerts":
      return {
        title: "Uyarıları sustur",
        message: `${name} pasife alınsın? Uyarıları susturulur, hesabı çalışmaya devam eder. Öğrencilerinin uyarıları ETKİLENMEZ.`,
        confirm: "Pasife al",
        destructive: false,
      };
    case "resume-alerts":
      return {
        title: "Uyarıları aç",
        message: `${name} için uyarılar tekrar aktif edilsin?`,
        confirm: "Aktif et",
        destructive: false,
      };
    default:
      return {
        title: "",
        message: "",
        confirm: "",
        destructive: false,
      };
  }
}
