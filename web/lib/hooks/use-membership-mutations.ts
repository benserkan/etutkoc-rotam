"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { membershipKeys } from "@/lib/api/membership";
import type {
  BulkMembershipOfferBody,
  BulkMembershipOfferResult,
  CreateMembershipOfferBody,
  MembershipHavaleBody,
  MembershipHavaleInfo,
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

export function useSetMembershipHavale() {
  const qc = useQueryClient();
  return useMutation<MembershipHavaleInfo, ApiError, { body: MembershipHavaleBody }>({
    mutationFn: ({ body }) =>
      api<MembershipHavaleInfo>("/api/v2/admin/membership-offers/havale", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => toast.error(errMsg(e, "Havale bilgisi kaydedilemedi")),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: membershipKeys.havale() });
      qc.invalidateQueries({ queryKey: membershipKeys.offers() });
      toast.success("Havale/EFT bilgisi kaydedildi");
    },
  });
}
