import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { ParentInvitationInfo } from "@/lib/types/parent";
import { ParentInvitationClient } from "@/components/parent/parent-invitation-client";
import { ParentInvitationInvalid } from "@/components/parent/parent-invitation-invalid";

/**
 * /parent/invitation/{token} — Public davet kabul sayfası.
 *
 * Jinja kaynağı: parent.py:95-113 (invitation_form) + invitation_accept.html
 * Hatalı token → invitation_invalid.html (4 durum)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Veli Daveti — ETÜTKOÇ Rotam" };

interface PageProps {
  params: Promise<{ token: string }>;
}

export default async function ParentInvitationPage({ params }: PageProps) {
  const { token } = await params;
  let info: ParentInvitationInfo | null = null;
  let errorCode: string | null = null;

  try {
    info = await apiServer<ParentInvitationInfo>(
      `/api/v2/parent/invitation/${encodeURIComponent(token)}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 400) {
      errorCode = e.detail?.code ?? "unknown";
    } else {
      throw e;
    }
  }

  if (!info) {
    return <ParentInvitationInvalid reason={errorCode ?? "unknown"} />;
  }
  return <ParentInvitationClient invitation={info} />;
}
