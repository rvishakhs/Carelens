import { useEffect, useRef, useState } from "react";
import { Loader2, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { fetchHandoverJob, fetchHandoverShifts, generateHandover, type HandoverShift } from "@/lib/handoverInsights";

function label(shift: HandoverShift) {
  const format = (value: string) => new Date(value).toLocaleString("en-GB", {
    timeZone: "Europe/London", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
  return `${format(shift.start)} – ${format(shift.end)} (UK)`;
}

export function GenerateHandover({ residentId, onReady }: { residentId: string; onReady: (jobId: string) => void }) {
  const [shifts, setShifts] = useState<HandoverShift[]>([]);
  const [selected, setSelected] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [check, setCheck] = useState(0);
  const [reload, setReload] = useState(0);
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const keys = useRef(new Map<string, string>());
  const request = useRef<AbortController | null>(null);
  const ready = useRef(onReady);
  ready.current = onReady;

  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);

  function close() {
    setOpen(false);
    dialog.current?.close();
    trigger.current?.focus();
  }

  useEffect(() => {
    const controller = new AbortController();
    fetchHandoverShifts(residentId, controller.signal).then((values) => {
      if (controller.signal.aborted) return;
      setShifts(values); setSelected(values[0]?.end ?? ""); setStatus("");
    }).catch(() => { if (!controller.signal.aborted) setStatus("Could not load authorised shifts. Try again."); });
    return () => { controller.abort(); request.current?.abort(); };
  }, [residentId, reload]);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    const poll = async () => {
      try {
        const job = await fetchHandoverJob(jobId, residentId, controller.signal);
        if (controller.signal.aborted) return;
        if (job.state === "draft_ready") {
          setStatus("Draft ready for review."); setBusy(false); setJobId(null); ready.current(jobId); return;
        }
        if (job.state === "failed" || job.state === "cancelled") {
          setStatus(`Generation ${job.state}. Ask your administrator to review the job before trying again.`);
          setBusy(false); setJobId(null); return;
        }
        setStatus(job.state === "queued" ? "Handover queued…" : "Generating handover…");
        if (++attempts >= 100) {
          setStatus("The job is still processing. Check its status again shortly."); setBusy(false); return;
        }
        timer = setTimeout(() => void poll(), 3000);
      } catch {
        if (!controller.signal.aborted) {
          setStatus("Status unavailable. The job may still be running; check again."); setBusy(false);
        }
      }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobId, residentId, check]);

  async function generate() {
    const shift = shifts.find((value) => value.end === selected);
    if (!shift || busy) return;
    const controller = new AbortController();
    request.current = controller;
    const key = keys.current.get(selected) ?? crypto.randomUUID();
    keys.current.set(selected, key);
    setBusy(true); setStatus("Submitting handover…");
    try {
      const job = await generateHandover(residentId, shift, key, controller.signal);
      if (!controller.signal.aborted) {
        setJobId(job.job_id); setCheck((value) => value + 1); close();
      }
    } catch {
      if (!controller.signal.aborted) {
        setBusy(false); setStatus("Submission could not be confirmed. Retry to check or reuse the same request.");
      }
    }
  }

  return <>
    <button ref={trigger} type="button" onClick={() => setOpen(true)} aria-haspopup="dialog"
      title={status || "Generate a handover summary"}
      className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-sky-700 transition-colors hover:bg-sky-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500">
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
      {busy ? "Generating…" : jobId ? "Check handover" : "Generate handover"}
    </button>
    <span role="status" className="sr-only">{status}</span>
    <dialog ref={dialog} aria-labelledby={`generate-handover-title-${residentId}`}
      onCancel={(event) => { event.preventDefault(); close(); }}
      onClose={() => setOpen(false)}
      className="fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-md overflow-y-auto rounded-2xl border-0 bg-white p-0 text-slate-900 shadow-2xl backdrop:bg-slate-900/40">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <h2 id={`generate-handover-title-${residentId}`} className="text-base font-semibold">Generate handover</h2>
        <button type="button" onClick={close} aria-label="Close handover generation"
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"><X className="h-4 w-4" /></button>
      </div>
      <div className="space-y-3 p-5">
        <label className="block text-sm font-medium" htmlFor={`handover-shift-${residentId}`}>Select shift</label>
        <select id={`handover-shift-${residentId}`} className="w-full min-w-0 rounded-lg border border-slate-300 bg-white p-2.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100" value={selected}
          disabled={busy || !!jobId} onChange={(event) => setSelected(event.target.value)}>
          {!shifts.length && <option value="">No shifts available</option>}
          {shifts.map((shift) => <option key={shift.end} value={shift.end}>{label(shift)}</option>)}
        </select>
        <p className="text-xs text-slate-500">Choose a completed shift. Times are shown in UK time.</p>
        {status && <p className="text-sm text-slate-600">{status}</p>}
        {!shifts.length && <button type="button" className="text-sm font-medium text-sky-700" onClick={() => setReload((value) => value + 1)}>Reload shifts</button>}
      </div>
      <div className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50 px-5 py-4">
        <Button variant="secondary" onClick={close}>Close</Button>
        {jobId ? <Button disabled={busy} onClick={() => { setBusy(true); setCheck((value) => value + 1); close(); }}>Check status</Button>
          : <Button disabled={busy || !selected} onClick={() => void generate()}>{busy ? "Submitting…" : "Generate now"}</Button>}
      </div>
    </dialog>
  </>;
}
