import { useEffect, useState } from "react";
import { fetchHandoverEvidence, type HandoverEvidence } from "@/lib/handoverInsights";
import type { HandoverInsight } from "./ResidentAIInsights";

export function HandoverEvidenceReview({ summary }: { summary: HandoverInsight }) {
  const [expanded, setExpanded] = useState(false);
  const [evidence, setEvidence] = useState<HandoverEvidence | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!expanded) return;
    const controller = new AbortController();
    setError("");
    fetchHandoverEvidence(summary.jobId, summary.residentId, controller.signal)
      .then((value) => { if (!controller.signal.aborted) setEvidence(value); })
      .catch(() => { if (!controller.signal.aborted) setError("Evidence history could not be loaded. Close and reopen to retry."); });
    return () => controller.abort();
  }, [expanded, summary.jobId, summary.residentId]);
  return <details className="rounded-xl border border-slate-200 p-4" onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm font-medium">Evidence references and version history</summary>
    <p className="my-2 text-xs text-slate-500">References below support the AI original. Staff edits are not automatically verified against these records.</p>
    {summary.originalSections?.map((section, index) => <div key={index} className="my-3 text-sm">
      <h4 className="font-medium">{section.category.replaceAll("_", " ")}</h4>
      {section.claims.map((claim, claimIndex) => <div key={claimIndex} className="my-2">
        <p>{claim.text}</p>
        <ul className="break-all text-xs text-slate-500">{claim.sources.map((source, sourceIndex) =>
          <li key={sourceIndex}>{source.source_type}: {source.source_id} · Version {source.version}</li>)}</ul>
      </div>)}
    </div>)}
    {error ? <p role="alert">{error}</p> : evidence ? <>
      <p className="text-xs">Retrieved: {evidence.retrieved_at}. Coverage: {evidence.coverage_complete ? "complete" : "incomplete"}.
        {evidence.evidence_cutoff ? ` Snapshot cutoff: ${evidence.evidence_cutoff}` : " No consistent source snapshot established."}</p>
      {evidence.versions.map((version) => <details key={version.id} className="mt-3 border-t pt-2">
        <summary className="text-sm">Version {version.version} · {version.kind.replaceAll("_", " ")} · {version.created_at}</summary>
        <p className="text-xs text-slate-500">{version.author ? `Author: ${version.author}` : "AI generated"}</p>
        <p className="whitespace-pre-wrap text-sm">{version.text}</p>
      </details>)}
    </> : expanded && <p role="status">Loading history…</p>}
  </details>;
}
