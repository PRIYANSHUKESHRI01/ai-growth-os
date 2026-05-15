"use client";

import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "./useApiClient";

export function useDashboardStats() {
  const api = useApiClient();
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => api.leads.stats(),
    staleTime: 30_000,
    refetchInterval: 10_000, // poll every 10s for real-time dashboard feel
  });
}
