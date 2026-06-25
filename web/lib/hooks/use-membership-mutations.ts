"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { membershipKeys } from "@/lib/api/membership";
import type {
  BulkMembershipOfferBody,
  BulkMembershipOfferResult,
  CreateMembershipOfferBody,
  MembershipOfferCreated,
} from "@/lib/types/membership";

function errMsg(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.detail?.message ?? fallback : fallback;
}

export function useCreateMembershipOffer() {
  const qc = useQueryClient();
  return useMutation<MembershipOfferCreated, ApiError, { body: CreateMembershipOfferBody }>({
    mutationFn: ({ body }) =>
      api<MembershipOfferCreated>("/api/v2/admin/membership-offers", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => toast.error(errMsg(e, "Teklif oluşturulamadı")),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: membershipKeys.offers() });
      toast.success("Teklif oluşturuldu — linki kopyalayıp WhatsApp'tan gönderebilirsin");
    },
  });
}

export function useCreateMembershipOffersBulk() {
  const qc = useQueryClient();
  return useMutation<BulkMembershipOfferResult, ApiError, { body: BulkMembershipOfferBody }>({
    mutationFn: ({ body }) =>
      api<BulkMembershipOfferResult>("/api/v2/admin/membership-offers/bulk", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => toast.error(errMsg(e, "Toplu teklif oluşturulamadı")),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: membershipKeys.offers() });
      toast.success(`${res.created} teklif oluşturuldu`);
    },
  });
}

export function useSendMembershipOfferWhatsApp() {
  const qc = useQueryClient();
  return useMutation<{ ok: boolean; wa_sent_at: string | null; message: string }, ApiError, { id: number }>({
    mutationFn: ({ id }) =>
      api(`/api/v2/admin/membership-offers/${id}/send-whatsapp`, { method: "POST" }),
    onError: (e) => toast.error(errMsg(e, "WhatsApp gönderilemedi")),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: membershipKeys.offers() });
      toast.success("Branded teklif WhatsApp'tan gönderildi");
    },
  });
}

