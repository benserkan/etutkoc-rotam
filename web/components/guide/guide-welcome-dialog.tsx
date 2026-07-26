"use client";

import { usePathname, useRouter } from "next/navigation";
import { Compass, Play } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { GuideAvatar } from "@/components/guide/guide-avatar";
import { useGuide, useGuideProgress } from "@/lib/hooks/use-guide";

interface Props {
  enabled: boolean;
  /** Rehber anahtarı (coach_onboarding | student_onboarding). */
  guideKey: string;
  /** Rehber sayfası (örn. /teacher/guide) — bu sayfadayken diyalog açılmaz. */
  guideHref: string;
  /** Rota'nın karşılama paragrafı (rol bazlı). */
  description: string;
  /** "Rehber bağlantısı nerede" ipucu (menü rol bazlı değişir). */
  menuHint: string;
}

/**
 * İlk giriş karşılaması — Rota, rehberi hiç görmemiş kullanıcıyı karşılar.
 *
 * Durum SUNUCUDA tutulur (user_guide_states): yalnız status=not_started iken
 * görünür; "Daha sonra" = dismiss (bir daha kendiliğinden açılmaz; menüdeki
 * Rehber bağlantısı her zaman durur). Başka cihazdan girse de aynı davranış.
 */
export function GuideWelcomeDialog({ enabled, guideKey, guideHref, description, menuHint }: Props) {
  const pathname = usePathname();
  const onGuidePage = pathname?.startsWith(guideHref) ?? false;
  const q = useGuide(guideKey, enabled && !onGuidePage);
  const progress = useGuideProgress(guideKey);
  const router = useRouter();

  if (!enabled || onGuidePage) return null;
  const status = q.data?.state.status;
  if (status !== "not_started") return null;

  const dismiss = () => {
    progress.mutate({ action: "dismiss" });
    toast.info("Rehber her zaman burada", {
      description: menuHint,
    });
  };

  return (
    <Dialog open onOpenChange={(open) => (!open ? dismiss() : undefined)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <GuideAvatar size={72} speaking={false} />
            <div>
              <DialogTitle>Merhaba, ben Rota!</DialogTitle>
              <DialogDescription className="mt-1">
                Etütkoç Rotam rehberin
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" onClick={dismiss} disabled={progress.isPending}>
            Daha sonra
          </Button>
          <Button
            className="bg-cyan-600 hover:bg-cyan-700"
            disabled={progress.isPending}
            onClick={() => {
              progress.mutate({ action: "start" });
              router.push(guideHref);
            }}
          >
            <Play className="mr-1.5 h-4 w-4" />
            Rehberi başlat
          </Button>
        </DialogFooter>
        <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Compass className="h-3.5 w-3.5" />
          {menuHint}
        </p>
      </DialogContent>
    </Dialog>
  );
}
