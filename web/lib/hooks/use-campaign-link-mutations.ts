"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { campaignLinkKeys } from "@/lib/api/campaign-links";
import type {
  CampaignLinkItem,
  CreateCampaignLinkBody,
} from "@/lib/types/campaign-link";

function errMsg(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.detail?.message ?? fallback : fallback;
}

export function useCreateCampaignLink() {
  const qc = useQueryClient();
  return useMutation<CampaignLinkItem, ApiError, { body: CreateCampaignLinkBody }>({
    mutationFn: ({ body }) =>
      api<CampaignLinkItem>("/api/v2/admin/campaign-links", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onError: (e) => toast.error(errMsg(e, "Kampanya linki oluşturulamadı")),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: campaignLinkKeys.list() });
      toast.success("Kampanya linki oluşturuldu — kopyalayıp gruba paylaşabilirsin");
    },
  });
}

export function useSetCampaignLinkStatus() {
  const qc = useQueryClient();
  return useMutation<CampaignLinkItem, ApiError, { id: number; status: string }>({
    mutationFn: ({ id, status }) =>
      api<CampaignLinkItem>(`/api/v2/admin/campaign-links/${id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      }),
    onError: (e) => toast.error(errMsg(e, "Durum değiştirilemedi")),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: campaignLinkKeys.list() });
    },
  });
}
