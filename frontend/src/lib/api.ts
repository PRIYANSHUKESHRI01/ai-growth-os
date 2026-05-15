/**
 * lib/api.ts
 * ──────────────────────────────────────────────────────────────────────────────
 * Shared TypeScript interfaces for API data shapes.
 *
 * ⚠️  All API calls are made through useApiClient() hook (hooks/useApiClient.ts)
 *    which attaches the real Clerk JWT automatically.
 *    DO NOT add raw fetch calls here — this file is types-only.
 */

// --- Interfaces ---

export interface Lead {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  company: string;
  title?: string;
  score?: {
    final_score: number;
    tag: string;
  };
  created_at: string;
}

export interface LeadListResponse {
  leads: Lead[];
  total: number;
  page: number;
  page_size: number;
}

export interface LeadUploadResponse {
  message: string;
  created: number;
  skipped: number;
  lead_ids: string[];
}

export interface LeadExplanation {
  lead_id: string;
  score: number;
  tag: string;
  intent_label: string;
  top_reasons: string[];
  value_factors: string[];
  confidence_factors: string[];
  summary: string;
}

export interface DiscoveryJob {
  id: string;
  status: string;
  current_stage: string;
  total_items: number;
  processed_items: number;
  total_raw: number;
  total_enriched: number;
  success_count: number;
  enrichment_rate: number;
  input_filters: any;
}

export interface DiscoveryJobsResponse {
  jobs: DiscoveryJob[];
  total: number;
}

export interface CreditBalance {
  user_id: string;
  discovery_credits: number;
  enrichment_credits: number;
  total_jobs_run: number;
  total_leads_enriched: number;
}

export interface DashboardStats {
  total_leads: number;
  avg_score: number;
  hot_leads_count: number;
  campaigns_count: number;
}

export interface Campaign {
  id: string;
  name: string;
  target_persona: string;
  status: string;
  stats?: {
    delivered: number;
    opened: number;
  };
}

export interface CampaignRunRequest {
  campaign_id: string;
  lead_ids?: string[];
}

export interface CampaignAnalytics {
  campaign_id: string;
  campaign_name: string;
  delivered: number;
  opened: number;
  clicked: number;
  replied: number;
  unsubscribed: number;
  bounced: number;
}

// ── Automation 3: Outreach Engine ─────────────────────────────────────────

export interface OutreachCampaignCreateRequest {
  name: string;
  min_score_filter: number;
  lead_ids?: string[];
  date_filter?: string;
}

export interface OutreachCampaign {
  id: string;
  name: string;
  status: 'draft' | 'pending' | 'running' | 'paused' | 'completed' | 'failed';
  min_score_filter: number | null;
  total_leads: number;
  total_sent: number;
  total_replied: number;
  total_opened: number;
  reply_rate: number;
  open_rate: number;
  created_at: string;
}

export interface OutreachCampaignListResponse {
  total: number;
  page: number;
  page_size: number;
  campaigns: OutreachCampaign[];
}

export interface OutreachCampaignLead {
  campaign_lead_id: string;
  lead_id: string;
  first_name: string | null;
  last_name: string | null;
  email: string;
  company: string | null;
  title: string | null;
  status: 'pending' | 'sent' | 'replied' | 'failed' | 'unsubscribed' | 'skipped';
  current_step: number;
  last_contacted_at: string | null;
  reply_type: 'interested' | 'not_interested' | 'meeting_request' | 'objection' | 'unknown' | null;
  reply_summary: string | null;
}

export interface OutreachCampaignDetail extends OutreachCampaign {
  leads: OutreachCampaignLead[];
}

export interface CampaignStepStat {
  step_number: number;
  total_sent: number;
  total_replied: number;
  total_failed: number;
  total_opened: number;
  reply_rate: number;
  open_rate: number;
}

export interface OutreachCampaignStats {
  campaign_id: string;
  name: string;
  status: string;
  total_leads: number;
  total_sent: number;
  total_replied: number;
  total_opened: number;
  reply_rate: number;
  open_rate: number;
  step_stats: CampaignStepStat[];
}
