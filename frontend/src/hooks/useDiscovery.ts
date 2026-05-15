"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "./useApiClient";
import { toast } from "sonner";

export function useDiscoveryJobs(page = 1, pageSize = 20) {
  const api = useApiClient();
  return useQuery({
    queryKey: ["discovery", "jobs", page, pageSize],
    queryFn: () => api.discovery.listJobs(page, pageSize),
    refetchInterval: 2000, // Poll every 2s for real-time job progress
    staleTime: 0,
  });
}

/** All enriched leads discovered via the pipeline (paginated) */
export function useEnrichedLeads(page = 1, pageSize = 50) {
  const api = useApiClient();
  return useQuery({
    queryKey: ["discovery", "enriched-leads", page, pageSize],
    queryFn: () => api.discovery.listEnrichedLeads(page, pageSize),
    staleTime: 30_000,
  });
}

export function useDiscoveryJob(id: string | null) {
  const api = useApiClient();
  return useQuery({
    queryKey: ["discovery", "job", id],
    queryFn: () => (id ? api.discovery.getJob(id) : Promise.reject("No ID")),
    enabled: !!id,
    // Smart polling: only poll running/pending jobs
    refetchInterval: (query) => {
      const jobStatus = query.state.data?.status;
      return jobStatus === "running" || jobStatus === "pending" ? 2000 : false;
    },
  });
}

export function useDiscoveryCredits() {
  const api = useApiClient();
  return useQuery({
    queryKey: ["discovery", "credits"],
    queryFn: () => api.discovery.getCredits(),
    staleTime: 30_000,
  });
}

export function useCreateDiscoveryJob() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filters: any) => api.discovery.createJob(filters),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["discovery", "jobs"] });
      queryClient.invalidateQueries({ queryKey: ["discovery", "credits"] });
    },
  });
}

export function useRunDiscoveryJob() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.discovery.runJob(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ["discovery", "jobs"] });
      const previousJobs = queryClient.getQueryData<any>(["discovery", "jobs"]);

      queryClient.setQueryData(["discovery", "jobs"], (old: any) => {
        if (!old) return old;
        return {
          ...old,
          jobs: old.jobs.map((j: any) =>
            j.id === id ? { ...j, status: "running" } : j
          ),
        };
      });

      return { previousJobs };
    },
    onError: (_err, _id, context) => {
      queryClient.setQueryData(["discovery", "jobs"], context?.previousJobs);
    },
    onSuccess: (_, id) => {
      toast.success("Discovery pipeline actively harvesting...");
      queryClient.invalidateQueries({ queryKey: ["discovery", "job", id] });
      queryClient.invalidateQueries({ queryKey: ["discovery", "jobs"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

/** Synchronous in-process discovery — no Celery required */
export function useRunDiscoveryJobSync() {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.discovery.runJobSync(id),
    onSuccess: (data, id) => {
      toast.success(
        `Discovery complete! Found ${data.discovered} leads, enriched ${data.enriched}.`
      );
      queryClient.invalidateQueries({ queryKey: ["discovery", "jobs"] });
      queryClient.invalidateQueries({ queryKey: ["discovery", "job", id] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: () => {
      toast.error("Discovery pipeline failed. Check the logs.");
    },
  });
}

/** Download leads from a job as CSV */
export function useDownloadJobCsv() {
  const api = useApiClient();
  return useMutation({
    mutationFn: (id: string) => api.discovery.downloadJobCsv(id),
    onSuccess: () => {
      toast.success("CSV downloaded successfully!");
    },
    onError: () => {
      toast.error("Failed to download CSV.");
    },
  });
}

/** Send discovered leads to the AI scoring engine */
export function useSendJobToScoring(onNavigate?: () => void) {
  const api = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.discovery.sendToScoring(id),
    onSuccess: (data) => {
      if (data.status === "scoring_complete") {
        toast.success(
          data.message || `Scored ${data.scored} leads! Redirecting to Leads dashboard...`
        );
      } else {
        toast.info(data.message || "Leads sent to scoring.");
      }
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      // Navigate to leads page after short delay so toast is visible
      if (onNavigate) {
        setTimeout(onNavigate, 800);
      }
    },
    onError: (err: any) => {
      toast.error(err?.message || "Failed to send leads to scoring engine.");
    },
  });
}
