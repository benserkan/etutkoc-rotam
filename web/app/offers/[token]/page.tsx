import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import { BrandLogo } from "@/components/brand-logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { OfferActions } from "./offer-actions";

/**
 * /offers/[token] — public teklif sayfası (Dalga 7 P5).
 *
 * Login gerektirmez; kurum/öğretmen e-postadaki link ile gelir.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Size Özel Teklif" };

interface OfferView {
  valid: boolean;
  status: string;
  kind: string | null;
  kind_label: string | null;
  title: string | null;
  summary: string | null;
  public_message: string | null;
  owner_name: string | null;
  expires_at: string | null;
}

const STATUS_MESSAGE: Record<string, string> = {
  not_found: "Teklif bulunamadı. Bağlantıyı doğru kopyaladığınızdan emin olun.",
  accepted: "Bu teklifi zaten kabul ettiniz.",
  declined: "Bu teklifi daha önce reddettiniz.",
  expired: "Bu teklifin süresi dolmuş.",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
  } catch {
    return iso.slice(0, 10);
  }
}

export default async function OfferPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  let offer: OfferView | null = null;
  try {
    offer = await apiServer<OfferView>(`/api/v2/offers/${token}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    offer = null;
  }

  const valid = offer?.valid === true;

  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-1.5">
          <BrandLogo href="/" />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{valid ? (offer?.kind_label ?? "Size özel teklif") : "Teklif"}</CardTitle>
            {offer?.owner_name ? (
              <CardDescription>{offer.owner_name} için hazırlandı</CardDescription>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-4">
            {valid && offer ? (
              <>
                <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-4 dark:bg-indigo-500/10 dark:border-indigo-500/30">
                  <p className="text-lg font-semibold text-indigo-900">{offer.summary ?? offer.title}</p>
                  {offer.public_message ? (
                    <p className="mt-2 text-sm text-indigo-800">{offer.public_message}</p>
                  ) : null}
                </div>
                {offer.expires_at ? (
                  <p className="text-xs text-muted-foreground">
                    Son geçerlilik: {fmtDate(offer.expires_at)}
                  </p>
                ) : null}
                <OfferActions token={token} />
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                {STATUS_MESSAGE[offer?.status ?? "not_found"] ?? STATUS_MESSAGE.not_found}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
