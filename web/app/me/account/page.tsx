import { redirect } from "next/navigation";
import { CalendarClock, Building2, Users, ShieldCheck, FileText } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { MyAccountResponse } from "@/lib/types/me";
import { ROLE_LABELS_TR } from "@/lib/types/me";
import { formatDate, formatDateShort, formatRelative } from "@/lib/locale";
import { SectionPanel } from "@/components/section-panel";
import { JargonTooltip } from "@/components/jargon-tooltip";
import { Separator } from "@/components/ui/separator";

import { MeActions } from "./me-actions";
import { PasswordChangeCard } from "@/components/password-change-card";
import { TwoFactorCard } from "@/components/me/two-factor-card";
import { SessionsCard } from "@/components/me/sessions-card";
import { EmailVerifyBanner } from "@/components/me/email-verify-banner";

export const metadata = {
  title: "Hesabım",
};

/** R-007 — App Router agresif cache yasak; sayfa her istekte taze. */
export const dynamic = "force-dynamic";

export default async function MeAccountPage() {
  let data: MyAccountResponse;
  try {
    data = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch (e) {
    // 401/403 → cookie eksik veya geçersiz → /login'e yönlendir
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect(`/login?returnUrl=${encodeURIComponent("/me/account")}`);
    }
    throw e;
  }

  const { user, institution, parent_links, kvkk_status, recent_requests } = data;

  return (
    <main className="max-w-4xl mx-auto px-4 py-10 space-y-6">
      {/* Sayfa başlığı + ana eylemler */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="font-display text-3xl font-bold tracking-tight">Hesabım</h1>
          <p className="text-sm text-muted-foreground">
            Profil bilgileriniz, kurum bağlantınız ve{" "}
            <JargonTooltip
              term="KVKK"
              content="Kişisel Verilerin Korunması Kanunu — verilerinizi görme, indirme ve silme haklarınız bu sayfadan kullanılır."
            />{" "}
            haklarınız.
          </p>
        </div>
        <MeActions kvkk={kvkk_status} />
      </header>

      {/* Soft e-posta doğrulama uyarısı (doğrulanmamışsa) */}
      <EmailVerifyBanner emailVerified={user.email_verified ?? true} />

      {/* Profil */}
      <SectionPanel
        title="Profil"
        description="Sistemde kayıtlı kişisel bilgileriniz. Değişiklikler için sistem yöneticisiyle iletişime geçin."
        accent="lacivert"
        meta={
          user.last_login_at ? (
            <span className="inline-flex items-center gap-1.5">
              <CalendarClock className="size-3.5" />
              Son giriş: {formatRelative(user.last_login_at)}
            </span>
          ) : null
        }
      >
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Ad soyad</dt>
            <dd className="font-medium">{user.full_name}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">E-posta</dt>
            <dd className="font-medium break-all">{user.email}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Rol</dt>
            <dd className="font-medium">{ROLE_LABELS_TR[user.role]}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Hesap durumu</dt>
            <dd className="font-medium">
              {user.is_active ? (
                <span className="inline-flex items-center gap-1.5 text-status-yolunda">
                  <ShieldCheck className="size-4" /> Aktif
                </span>
              ) : (
                <span className="text-status-risk">Pasif</span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Kayıt tarihi</dt>
            <dd className="font-medium">{formatDate(user.created_at)}</dd>
          </div>
        </dl>
      </SectionPanel>

      {/* Kurum (varsa) */}
      {institution ? (
        <SectionPanel
          title="Bağlı olduğu kurum"
          description="Hesabınız bir kuruma bağlı; planınız ve veri sahibi tarafınız bu kurumdur."
          accent="haki"
          meta={
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="size-3.5" />
              Kurum kimliği #{institution.id}
            </span>
          }
        >
          <p className="text-base font-medium">{institution.name}</p>
          {institution.slug ? (
            <p className="text-xs text-muted-foreground mt-1">/{institution.slug}</p>
          ) : null}
        </SectionPanel>
      ) : null}

      {/* Veli/öğrenci bağları */}
      {parent_links.length > 0 ? (
        <SectionPanel
          title={user.role === "parent" ? "Çocuklarınız" : "Velileriniz"}
          description={
            user.role === "parent"
              ? "Velisi olduğunuz öğrenciler — bildirim ve rapor erişiminiz var."
              : "Sizinle eşleştirilen veliler — günlük özet ve rapor bunlara gider."
          }
          accent="lacivert"
        >
          <ul className="space-y-3">
            {parent_links.map((link) => (
              <li
                key={link.link_id}
                className="flex items-center gap-3 rounded-md border border-border bg-muted/30 px-4 py-2.5"
              >
                <Users className="size-4 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{link.counterpart_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {link.relation_label_tr}
                    {link.is_primary ? " · Birincil" : ""}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </SectionPanel>
      ) : null}

      {/* Hesap şifresi */}
      <PasswordChangeCard
        allowEmptyCurrent={user.must_change_password}
        description={
          user.must_change_password
            ? "İlk girişte yönetici tarafından oluşturulan geçici şifren var. Aşağıdan yeni şifreni belirle."
            : "Mevcut şifreni doğrula, ardından yeni bir şifre belirle. Yeni şifre güvenli kabul edilmek için son sızıntı veritabanlarına karşı kontrol edilir."
        }
      />

      {/* İki faktörlü doğrulama (yalnız yönetici rolleri için görünür) */}
      <TwoFactorCard />

      {/* Aktif oturumlar (kendi cihazları) */}
      <SessionsCard />

      {/* KVKK durumu */}
      <SectionPanel
        title="Veri haklarınız (KVKK)"
        description={
          kvkk_status.has_pending_delete
            ? "Hesabınız için silme talebiniz var. 30 günlük süre içinde iptal edebilirsiniz."
            : "Verilerinizi indirebilir veya hesabınızı silebilirsiniz. Silme talebi 30 gün sonra uygulanır."
        }
        accent={kvkk_status.has_pending_delete ? "dikkat" : "yolunda"}
      >
        {kvkk_status.has_pending_delete ? (
          <div className="rounded-md border border-status-dikkat/40 bg-status-dikkat/10 px-4 py-3 text-sm">
            <p className="font-medium">Bekleyen silme talebi var</p>
            {kvkk_status.pending_delete_scheduled_at ? (
              <p className="text-muted-foreground mt-1">
                Uygulanma tarihi:{" "}
                <span className="font-medium text-foreground">
                  {formatDate(kvkk_status.pending_delete_scheduled_at)}
                </span>
              </p>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Aktif silme talebi yok.</p>
        )}
      </SectionPanel>

      {/* Son talepler */}
      {recent_requests.length > 0 ? (
        <SectionPanel
          title="Son talepleriniz"
          description="KVKK kapsamında açtığınız son 20 talep. İzleme amaçlıdır; iptal işlemi yukarıdaki paneldedir."
          accent="lacivert"
        >
          <ul className="divide-y divide-border">
            {recent_requests.map((req) => (
              <li key={req.id} className="py-3 flex items-start gap-3 text-sm">
                <FileText className="size-4 mt-0.5 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-medium">{req.kind_label_tr}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatDateShort(req.created_at)}
                    </span>
                  </div>
                  {req.reason ? (
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">
                      {req.reason}
                    </p>
                  ) : null}
                </div>
                <span className="text-xs text-muted-foreground shrink-0 self-center">
                  {req.status_label_tr}
                </span>
              </li>
            ))}
          </ul>
        </SectionPanel>
      ) : null}

      <Separator />
      <p className="text-xs text-muted-foreground text-center">
        Bu sayfa Next.js üzerinden FastAPI{" "}
        <code className="font-mono">/api/v2/me</code> endpoint&apos;ini gerçek
        zamanlı tüketir. Cache: <code className="font-mono">no-store</code>.
      </p>
    </main>
  );
}
