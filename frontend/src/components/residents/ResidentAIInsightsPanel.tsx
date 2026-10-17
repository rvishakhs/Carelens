import { useEffect, useState } from "react";
import { isAxiosError } from "axios";

import { ResidentAIInsights, type HandoverInsight } from "./ResidentAIInsights";
import { fetchHandoverDraft, fetchHandoverInsight, saveHandoverInsight } from "@/lib/handoverInsights";
import { GenerateHandover } from "./GenerateHandover";

export function ResidentAIInsightsPanel({ residentId, residentName }: { residentId: string; residentName: string }) {
  const [summary, setSummary] = useState<HandoverInsight | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setSummary(null);
    (selectedJob ? fetchHandoverDraft(selectedJob, residentId, controller.signal) : fetchHandoverInsight(residentId, controller.signal))
      .then((value) => { if (!controller.signal.aborted) setSummary(value); })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const status = isAxiosError(err) ? err.response?.status : undefined;
        setError(status === 401 || status === 403 || status === 404
          ? "AI handover is not available for your current access."
          : "We couldn’t load the AI handover. Please try again.");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [residentId, reload, selectedJob]);

  return <ResidentAIInsights key={summary?.jobId ?? "no-draft"}
    residentName={residentName} summary={summary} loading={loading} error={error}
    generationControl={<GenerateHandover residentId={residentId} onReady={(jobId) => { setSelectedJob(jobId); setReload((value) => value + 1); }} />}
    onRetry={() => setReload((value) => value + 1)}
    onSave={async (current, text) => { setSummary(await saveHandoverInsight(current, text)); }}
  />;
}
