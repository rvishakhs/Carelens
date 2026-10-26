import api from "@/lib/api";

export type EvidenceSourceType = "fall" | "appointment";
export interface EvidenceCitation { evidence_id: string; source_type: EvidenceSourceType; source_id: string; source_version: string | null; occurred_at: string; title: string; excerpt: string | null; }
export interface ResidentHistoryResult { search_id: string; resident_id: string; answer: string; answer_status: "supported" | "no_evidence" | "partial"; coverage_limitations: string[]; citations: EvidenceCitation[]; }
export interface EvidenceSource { source_type: EvidenceSourceType; source_id: string; occurred_at: string; source_version: string | null; title: string; details: Record<string, unknown>; changed_since_search: boolean; }

export async function searchResidentHistory(residentId: string, payload: { question: string; from: string | null; to: string | null; source_types: EvidenceSourceType[] }, signal: AbortSignal) {
  const { data } = await api.post<ResidentHistoryResult>(`/residents/${encodeURIComponent(residentId)}/history-search`, { ...payload, mode: "evidence" }, { signal, timeout: 20000 });
  if (data.resident_id !== residentId) throw new Error("Resident search scope mismatch");
  return data;
}

export async function fetchResidentHistorySource(residentId: string, searchId: string, sourceType: EvidenceSourceType, sourceId: string, signal: AbortSignal) {
  const { data } = await api.get<EvidenceSource>(`/residents/${encodeURIComponent(residentId)}/history-search/${encodeURIComponent(searchId)}/sources/${sourceType}/${encodeURIComponent(sourceId)}`, { signal, timeout: 20000 });
  if (data.source_id !== sourceId || data.source_type !== sourceType) throw new Error("Resident search scope mismatch");
  return data;
}
