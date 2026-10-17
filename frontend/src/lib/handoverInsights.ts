import api from "@/lib/api";
import type { HandoverInsight } from "@/components/residents/ResidentAIInsights";

// A same-origin reverse proxy keeps staff authentication on the application origin.
const base = "/intelligence/v1/handovers";
interface DraftResponse {
  id: string;
  job_id: string;
  resident_id: string;
  version: number;
  version_kind: "ai_original" | "staff_revision";
  authored_by: string | null;
  shift_start: string;
  shift_end: string;
  updated_at: string;
  text: string;
  original_text: string;
  warnings: string[];
  can_edit: boolean;
  overview_notice?: string | null;
  original_sections: { category: string; claims: { text: string; sources: { source_type: string; source_id: string; version: string }[] }[] }[];
}
function toInsight(data: DraftResponse): HandoverInsight {
  return {
    id: data.id, jobId: data.job_id, residentId: data.resident_id, version: data.version,
    staffRevision: data.version_kind === "staff_revision", authoredBy: data.authored_by,
    shiftStart: data.shift_start, shiftEnd: data.shift_end, updatedAt: data.updated_at,
    text: data.text, originalText: data.original_text, warnings: data.warnings, canEdit: data.can_edit,
    originalSections: data.original_sections,
    overviewNotice: data.overview_notice,
  };
}
export async function fetchHandoverInsight(residentId: string, signal: AbortSignal) {
  const { data } = await api.get<DraftResponse | null>(`${base}/residents/${encodeURIComponent(residentId)}/latest`, {
    baseURL: window.location.origin, signal, headers: { "Cache-Control": "no-cache" },
  });
  if (data && data.resident_id !== residentId) throw new Error("Resident scope mismatch");
  return data ? toInsight(data) : null;
}
export async function fetchHandoverDraft(jobId: string, residentId: string, signal: AbortSignal) {
  const { data } = await api.get<DraftResponse>(`${base}/${encodeURIComponent(jobId)}/draft`, {
    baseURL: window.location.origin, signal,
  });
  if (data.resident_id !== residentId) throw new Error("Resident scope mismatch");
  return toInsight(data);
}
export interface HandoverEvidence {
  resident_id: string;
  retrieved_at: string;
  evidence_cutoff: string | null;
  coverage_complete: boolean;
  versions: { id: string; version: number; kind: string; author: string | null; created_at: string; text: string }[];
}
export async function fetchHandoverEvidence(jobId: string, residentId: string, signal: AbortSignal) {
  const { data } = await api.get<HandoverEvidence>(`${base}/${encodeURIComponent(jobId)}/evidence`, {
    baseURL: window.location.origin, signal,
  });
  if (data.resident_id !== residentId) throw new Error("Resident scope mismatch");
  return data;
}
export async function saveHandoverInsight(summary: HandoverInsight, text: string) {
  const { data } = await api.post<DraftResponse>(`${base}/${encodeURIComponent(summary.jobId)}/revisions`, {
    expected_version_id: summary.id, text,
  }, { baseURL: window.location.origin });
  if (data.resident_id !== summary.residentId) throw new Error("Resident scope mismatch");
  return toInsight(data);
}

export interface HandoverShift { start: string; end: string }
export interface HandoverJob { job_id: string; resident_id?: string; state: "queued" | "running" | "draft_ready" | "failed" | "cancelled" }
export async function fetchHandoverShifts(residentId: string, signal: AbortSignal) {
  const { data } = await api.get<HandoverShift[]>(`${base}/residents/${encodeURIComponent(residentId)}/shifts`, {
    baseURL: window.location.origin, signal,
  });
  return data;
}
export async function generateHandover(residentId: string, shift: HandoverShift, key: string, signal: AbortSignal) {
  const { data } = await api.post<HandoverJob>(base, {
    resident_id: residentId, shift_start: shift.start, shift_end: shift.end,
  }, { baseURL: window.location.origin, signal, headers: { "Idempotency-Key": key } });
  return data;
}
export async function fetchHandoverJob(jobId: string, residentId: string, signal: AbortSignal) {
  const { data } = await api.get<HandoverJob>(`${base}/${encodeURIComponent(jobId)}`, {
    baseURL: window.location.origin, signal,
  });
  if (data.resident_id !== residentId) throw new Error("Resident scope mismatch");
  return data;
}
