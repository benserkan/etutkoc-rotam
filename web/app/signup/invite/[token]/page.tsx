import Link from "next/link";
import {
  BarChart3,
  CalendarCheck2,
  CalendarClock,
  CircleAlert,
  MessageSquareHeart,
  ShieldCheck,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { SignupInviteForm } from "./signup-invite-form";

/**
 * /signup/invite/[token] — davetiyeli kayıt.
 *
 * İlk izlenim sayfası: kurumun kendi markasıyla (logo, yoksa ad) karşılar;
 * kim davet etti, hangi rol, ne kadar süre geçerli — hepsi bir bakışta.
 * ETÜTKOÇ yalnız küçük "altyapı" notu. Tema her zaman açık (force-light).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Davetiyeli Kayıt" };

interface InvitationInfo {
  valid: boolean;
  status: string;
  email: string | null;
  full_name: string | null;
  role: string | null;
  institution_name: string | null;
  institution_logo_url?: string | null;
  inviter_name?: string | null;
  expires_at?: string | null;
  phone_verification_available?: boolean;
}

const STATUS_MESSAGE: Record<string, { title: string; text: string }> = {
  not_found: {
    title: "Davetiye bulunamadı",
    text: "Bağlantıyı e-postadan eksiksiz kopyaladığınızdan emin olun.",
  },
  expired: {
    title: "Davetiyenin süresi dolmuş",
    text: "Sizi davet eden kişiden yeni bir davet bağlantısı isteyin.",
  },
  consumed: {
    title: "Bu davetiye zaten kullanılmış",
    text: "Hesabınız açıldıysa e-posta ve şifrenizle giriş yapabilirsiniz.",
  },
  revoked: {
    title: "Davetiye iptal edilmiş",
    text: "Sizi davet eden kişiyle iletişime geçin.",
  },
};

const ROLE_LABEL: Record<string, string> = {
  teacher: "öğretmen",
  institution_admin: "kurum yöneticisi",
  student: "öğrenci",
  parent: "veli",
};

const BENEFITS = [
  {
    icon: CalendarCheck2,
    title: "Haftalık program",
    text: "Öğrencilerinize kitap ve konu bazlı program hazırlayın, kalan testleri anında görün.",
  },
  {
    icon: BarChart3,
    title: "Deneme ve ilerleme takibi",
    text: "Deneme sonuçları konu konu analiz edilir; kim nerede zorlanıyor tek ekranda.",
  },
  {
    icon: MessageSquareHeart,
    title: "Veli bilgilendirme",
    text: "Veliler programı ve gelişimi düzenli olarak kendiliğinden öğrenir.",
  },
];

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Istanbul",
  });
}

function InstitutionMark({ name, logoUrl }: { name: string; logoUrl: string | null }) {
  return (
    <div className="inline-flex min-h-16 max-w-full items-center rounded-2xl bg-white px-5 py-3 shadow-lg shadow-cyan-950/20 ring-1 ring-white/60">
      {logoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- kurum logosu (dinamik, herkese açık uç)
        <img src={logoUrl} alt={name} className="block h-12 w-auto max-w-[240px] object-contain" />
      ) : (
        <span className="font-display text-xl font-bold leading-tight text-slate-900 break-words">
          {name}
        </span>
      )}
    </div>
  );
}

export default async function SignupInvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  let info: InvitationInfo | null = null;
  try {
    info = await apiServer<InvitationInfo>(`/api/v2/auth/signup/invite/${token}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    info = { valid: false, status: "not_found", email: null, full_name: null, role: null, institution_name: null };
  }

  const valid = info?.valid === true;
  const instName = info?.institution_name ?? null;
  const logoUrl = info?.institution_logo_url ?? null;
  const roleLabel = ROLE_LABEL[info?.role ?? "teacher"] ?? "öğretmen";
  const expiresLabel = formatDate(info?.expires_at);
  const firstName = (info?.full_name ?? "").trim().split(/\s+/)[0] ?? "";

  // --- Geçersiz davet: sade, tek kart --------------------------------------
  if (!valid) {
    const msg = STATUS_MESSAGE[info?.status ?? "not_found"] ?? STATUS_MESSAGE.not_found;
    return (
      <main className="force-light flex min-h-screen items-center justify-center bg-slate-100 px-4 py-12 text-slate-900">
        <div className="w-full max-w-md space-y-6 text-center">
          {instName ? (
            <div className="flex justify-center">
              <InstitutionMark name={instName} logoUrl={logoUrl} />
            </div>
          ) : (
            <div className="flex justify-center">
              <BrandLogo href="/" size={34} />
            </div>
          )}
          <div className="rounded-2xl bg-white p-8 shadow-xl shadow-slate-900/5 ring-1 ring-slate-200">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-700">
              <CircleAlert className="h-6 w-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900">{msg.title}</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{msg.text}</p>
            <Link
              href="/login"
              className="mt-6 inline-flex w-full items-center justify-center rounded-lg bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-800"
            >
              Giriş sayfasına git
            </Link>
          </div>
          {instName ? (
            <p className="text-xs text-slate-500">Altyapı: ETÜTKOÇ Rotam</p>
          ) : null}
        </div>
      </main>
    );
  }

  // --- Geçerli davet: iki panelli karşılama --------------------------------
  return (
    <main
      className="force-light min-h-screen bg-slate-100 text-slate-900 lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]"
      data-testid="invite-page"
    >
      {/* Sol: kurum karşılaması */}
      <section className="relative overflow-hidden bg-gradient-to-br from-cyan-900 via-cyan-800 to-slate-900 px-6 py-10 text-white sm:px-10 lg:flex lg:min-h-screen lg:flex-col lg:justify-between lg:px-14 lg:py-14">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-cyan-400/20 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-amber-300/10 blur-3xl"
        />

        <div className="relative">
          {instName ? <InstitutionMark name={instName} logoUrl={logoUrl} /> : <BrandLogo href="/" size={34} wordmarkClassName="text-white" />}
        </div>

        <div className="relative mt-10 max-w-xl lg:mt-0">
          <p className="inline-flex items-center rounded-full bg-white/15 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-50 ring-1 ring-white/25">
            Davetiye · {roleLabel}
          </p>
          <h1 className="mt-4 font-display text-3xl font-bold leading-tight sm:text-4xl">
            {firstName ? `Hoş geldiniz, ${firstName}!` : "Hoş geldiniz!"}
          </h1>
          <p className="mt-4 text-base leading-relaxed text-cyan-50 sm:text-lg">
            {info?.inviter_name ? <b className="text-white">{info.inviter_name}</b> : "Kurum yöneticiniz"}
            {instName ? (
              <>
                {" "}sizi <b className="text-white">{instName}</b> ekibine{" "}
              </>
            ) : (
              " sizi ekibe "
            )}
            <b className="text-white">{roleLabel}</b> olarak davet etti.
          </p>

          <ul className="mt-8 space-y-4">
            {BENEFITS.map((b) => (
              <li key={b.title} className="flex gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 ring-1 ring-white/20">
                  <b.icon className="h-4.5 w-4.5 text-amber-200" />
                </span>
                <span>
                  <span className="block text-sm font-semibold text-white">{b.title}</span>
                  <span className="block text-sm leading-relaxed text-cyan-100/90">{b.text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative mt-10 text-xs text-cyan-100/70 lg:mt-0">Altyapı: ETÜTKOÇ Rotam</p>
      </section>

      {/* Sağ: form */}
      <section className="flex items-start justify-center px-4 py-10 sm:px-8 lg:items-center lg:py-14">
        <div className="w-full max-w-md">
          <div className="rounded-2xl bg-white p-6 shadow-xl shadow-slate-900/5 ring-1 ring-slate-200 sm:p-8">
            <h2 className="text-xl font-bold text-slate-900">Hesabınızı oluşturun</h2>
            <p className="mt-1 text-sm text-slate-600">
              Birkaç bilgiyle hesabınız hazır; ardından doğrudan panelinize geçersiniz.
            </p>
            {expiresLabel ? (
              <p className="mt-4 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900 ring-1 ring-amber-200">
                <CalendarClock className="h-4 w-4 shrink-0 text-amber-700" />
                Bu davet {expiresLabel} tarihine kadar geçerli ve tek kullanımlık.
              </p>
            ) : null}
            <div className="mt-6">
              <SignupInviteForm
                token={token}
                defaultEmail={info?.email ?? ""}
                defaultFullName={info?.full_name ?? ""}
                role={info?.role ?? "teacher"}
                phoneVerificationAvailable={info?.phone_verification_available === true}
              />
            </div>
          </div>
          <p className="mt-5 flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            Bilgileriniz şifreli bağlantıyla korunur.
          </p>
          <p className="mt-2 text-center text-xs text-slate-500">
            Zaten hesabınız var mı?{" "}
            <Link href="/login" className="font-semibold text-cyan-700 hover:underline">
              Giriş yapın
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
