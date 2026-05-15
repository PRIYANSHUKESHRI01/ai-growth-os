"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "./useApiClient";
import type { CampaignRunRequest } from "@/lib/api";
import { toast } from "sonner";

export function useCampaigns() {
  const api = useApiClient();
  return useQuery({
    queryKey: ["campaigns", "list"],
    queryFn: () => api.campaigns.list(),
    staleTime: 30_000,
  });
}

export function useCampaignAnalytics(campaignId: string | null) {
  const api = useApiClient();
  return useQuery({
    queryKey: ["campaigns", "analytics", campaignId],
    queryFn: () =>
      campaignId
        ? api.campaigns.analytics(campaignId)
        : Promise.reject("No ID"),
    enabled: !!campaignId,
  });
}

export function useRunCampaign() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: CampaignRunRequest) => api.campaigns.run(request),
    onMutate: async (request) => {
      await queryClient.cancelQueries({ queryKey: ["campaigns", "list"] });
      const previousCampaigns = queryClient.getQueryData<any[]>([
        "campaigns",
        "list",
      ]);

      queryClient.setQueryData(
        ["campaigns", "list"],
        (old: any[] | undefined) => {
          return old?.map((c) =>
            c.id === request.campaign_id ? { ...c, status: "running" } : c
          );
        }
      );

      return { previousCampaigns };
    },
    onError: (_err, _request, context) => {
      queryClient.setQueryData(
        ["campaigns", "list"],
        context?.previousCampaigns
      );
    },
    onSuccess: () => {
      toast.success("Campaign sequence initiated!");
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}
