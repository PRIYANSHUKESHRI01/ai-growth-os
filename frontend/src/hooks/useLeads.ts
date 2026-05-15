"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "./useApiClient";

export function useLeads(page = 1, pageSize = 50) {
  const api = useApiClient();
  return useQuery({
    queryKey: ["leads", page, pageSize],
    queryFn: () => api.leads.list(page, pageSize),
    staleTime: 30_000,
  });
}

export function useTopLeads(limit = 10) {
  const api = useApiClient();
  return useQuery({
    queryKey: ["leads", "top", limit],
    queryFn: () => api.leads.top(limit),
    staleTime: 30_000,
    refetchInterval: 10_000, // refresh every 10s for dashboard feel
  });
}

export function useLead(id: string) {
  const api = useApiClient();
  return useQuery({
    queryKey: ["lead", id],
    queryFn: () => api.leads.getById(id),
    enabled: !!id,
  });
}

export function useLeadExplanation(id: string) {
  const api = useApiClient();
  return useQuery({
    queryKey: ["lead", id, "explanation"],
    queryFn: () => api.leads.explanation(id),
    enabled: !!id,
  });
}

export function useUploadLeads() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.leads.upload(file),
    onSuccess: () => {
      // Invalidate all lead queries so dashboard + leads page refresh
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

/** Score all leads for the current user (batch AI scoring) */
export function useScoreAllLeads() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.leads.scoreAll(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

/** Score a single lead by ID */
export function useScoreLead() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (leadId: string) => api.leads.scoreLead(leadId),
    onSuccess: (_data, leadId) => {
      // Refresh this specific lead and the full list
      queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

/** Hard-delete a lead (and its score) by ID */
export function useDeleteLead() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (leadId: string) => api.leads.deleteLead(leadId),
    // Optimistic update — remove the row immediately before server confirms
    onMutate: async (leadId) => {
      await queryClient.cancelQueries({ queryKey: ["leads"] });
      const previous = queryClient.getQueryData<any>(["leads", 1, 50]);
      queryClient.setQueriesData({ queryKey: ["leads"] }, (old: any) => {
        if (!old?.leads) return old;
        return { ...old, leads: old.leads.filter((l: any) => l.id !== leadId), total: old.total - 1 };
      });
      return { previous };
    },
    onError: (_err, _id, context) => {
      // Roll back on failure
      if (context?.previous) {
        queryClient.setQueryData(["leads", 1, 50], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}
