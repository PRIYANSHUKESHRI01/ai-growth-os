"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";
import { toast } from "sonner";
import type {
  Lead,
  LeadListResponse,
  LeadUploadResponse,
  LeadExplanation,
  DiscoveryJob,
  DiscoveryJobsResponse,
  CreditBalance,
  DashboardStats,
  Campaign,
  CampaignRunRequest,
  CampaignAnalytics,
  OutreachCampaignCreateRequest,
  OutreachCampaignListResponse,
  OutreachCampaignDetail,
  OutreachCampaignStats,
} from "@/lib/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ── Core request helper ──────────────────────────────────────────────────────

async function authenticatedRequest<T>(
  token: string,
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...(options.headers as Record<string, string>),
  };

  // Don't manually set Content-Type for FormData — browser sets it with boundary
  const isFormData = options.body instanceof FormData;
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ message: "An unknown error occurred" }));

      // Structured error from backend
      let message = response.statusText;
      if (errorData.message) {
        message = errorData.message;
      } else if (errorData.detail) {
        if (Array.isArray(errorData.detail)) {
          message = errorData.detail.map((e: any) => e.msg || JSON.stringify(e)).join(", ");
        } else if (typeof errorData.detail === "string") {
          message = errorData.detail;
        } else {
          message = JSON.stringify(errorData.detail);
        }
      }
      
      const code = errorData.error || `HTTP_${response.status}`;

      // Map known error codes to user-friendly messages
      const friendlyMessages: Record<string, string> = {
        LOW_CREDITS: "Not enough credits to run this operation.",
        INVALID_TOKEN: "Your session has expired. Please sign in again.",
        INTERNAL_SERVER_ERROR: "Server error. Please try again.",
      };

      const friendlyMessage = friendlyMessages[code] || message;
      // Safety check to ensure friendlyMessage is a string and not an object
      const safeMessage = typeof friendlyMessage === 'string' ? friendlyMessage : JSON.stringify(friendlyMessage);
      toast.error(safeMessage);
      throw new Error(safeMessage);
    }

    return response.json();
  } catch (error: any) {
    if (error.name === "AbortError") throw error;
    // Only show "network error" if the request never reached the server
    // (TypeError means fetch itself failed — no DNS, no connection, etc.)
    // If we already threw from response.ok === false above, that error already
    // had a toast shown and its message won't be a TypeError.
    if (error instanceof TypeError) {
      toast.error("Network error: Please check your connection and try again.");
    }
    throw error;
  }
}

// ── Hook — returns token-aware API client ─────────────────────────────────────

export function useApiClient() {
  const { getToken } = useAuth();

  const request = useCallback(
    async <T>(endpoint: string, options: RequestInit = {}): Promise<T> => {
      const token = await getToken();
      if (!token) {
        toast.error("You must be signed in to perform this action.");
        throw new Error("Not authenticated");
      }
      return authenticatedRequest<T>(token, endpoint, options);
    },
    [getToken]
  );

  // ── Leads ─────────────────────────────────────────────────────────────────

  const leads = {
    list: (page = 1, pageSize = 50) =>
      request<LeadListResponse>(`/leads?page=${page}&page_size=${pageSize}`),

    getById: (id: string) => request<Lead>(`/leads/${id}`),

    top: (limit = 10) =>
      request<LeadListResponse>(`/leads/top?limit=${limit}`),

    explanation: (id: string) =>
      request<LeadExplanation>(`/leads/${id}/explanation`),

    stats: () => request<DashboardStats>(`/dashboard/stats`),

    // Score every unscored lead for the current user
    scoreAll: () =>
      request<{ status: string; scored: number; message: string }>(`/leads/score-all`, {
        method: "POST",
      }),

    // Score a single lead by ID
    scoreLead: (id: string) =>
      request<{ status: string; lead_id: string; final_score: number; tag: string; message: string }>(
        `/leads/${id}/score`,
        { method: "POST" }
      ),

    // Delete a lead (and its score)
    deleteLead: (id: string) =>
      request<{ status: string; lead_id: string }>(`/leads/${id}`, { method: "DELETE" }),

    upload: async (file: File) => {
      if (file.size > 10 * 1024 * 1024) {
        toast.error("File too large. Maximum upload size is 10MB.");
        throw new Error("File too large");
      }
      const formData = new FormData();
      formData.append("file", file);
      return request<LeadUploadResponse>(`/leads/upload`, {
        method: "POST",
        body: formData,
        // No Content-Type — browser sets multipart/form-data with boundary
      });
    },
  };

  // ── Discovery ─────────────────────────────────────────────────────────────

  const discovery = {
    listJobs: (page = 1, pageSize = 20) =>
      request<DiscoveryJobsResponse>(
        `/discovery/jobs?page=${page}&page_size=${pageSize}`
      ),

    getJob: (id: string) => request<DiscoveryJob>(`/discovery/jobs/${id}`),

    createJob: (filters: any) =>
      request<DiscoveryJob>(`/discovery/jobs`, {
        method: "POST",
        body: JSON.stringify(filters),
      }),

    // Async Celery-based run (requires Celery worker)
    runJob: (id: string) =>
      request<DiscoveryJob>(`/discovery/run/${id}`, { method: "POST" }),

    // Synchronous in-process run — no Celery required
    runJobSync: (id: string) =>
      request<any>(`/discovery/run-sync/${id}`, { method: "POST" }),

    // Download leads CSV for a job
    downloadJobCsv: async (id: string, filename?: string) => {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const res = await fetch(`${API_BASE_URL}/discovery/jobs/${id}/csv`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to download CSV");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename ?? `leads_job_${id.slice(0, 8)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },

    // Send job leads to AI scoring engine
    sendToScoring: (id: string) =>
      request<any>(`/discovery/jobs/${id}/send-to-scoring`, { method: "POST" }),

    // List all enriched leads from the discovery pipeline (paginated)
    listEnrichedLeads: (page = 1, pageSize = 50) =>
      request<any>(`/discovery/leads?page=${page}&page_size=${pageSize}`),

    getCredits: () => request<CreditBalance>(`/discovery/credits`),
  };

  // ── Campaigns ─────────────────────────────────────────────────────────────

  const campaigns = {
    list: () => request<Campaign[]>(`/campaigns`),

    run: (data: CampaignRunRequest) =>
      request<any>(`/campaign/run`, {
        method: "POST",
        body: JSON.stringify(data),
      }),

    analytics: (id: string) =>
      request<CampaignAnalytics>(`/campaign/analytics?campaign_id=${id}`),
  };

  // ── Outreach (Automation 3) ─────────────────────────────────────────

  const outreach = {
    create: (data: OutreachCampaignCreateRequest) =>
      request<any>(`/outreach/campaigns`, {
        method: "POST",
        body: JSON.stringify(data),
      }),

    list: (page = 1, pageSize = 20) =>
      request<OutreachCampaignListResponse>(
        `/outreach/campaigns?page=${page}&page_size=${pageSize}`
      ),

    detail: (id: string) =>
      request<OutreachCampaignDetail>(`/outreach/campaigns/${id}`),

    run: (id: string) =>
      request<any>(`/outreach/campaigns/${id}/run`, { method: "POST" }),

    pause: (id: string) =>
      request<any>(`/outreach/campaigns/${id}/pause`, { method: "POST" }),

    delete: (id: string) =>
      request<any>(`/outreach/campaigns/${id}`, { method: "DELETE" }),

    stats: (id: string) =>
      request<OutreachCampaignStats>(`/outreach/campaigns/${id}/stats`),

    markReply: (campaignId: string, leadId: string, replyText?: string) =>
      request<any>(`/outreach/reply`, {
        method: "POST",
        body: JSON.stringify({
          campaign_id: campaignId,
          lead_id: leadId,
          reply_text: replyText ?? null,
        }),
      }),
  };

  return { leads, discovery, campaigns, outreach };
}
