import { Activity, ArrowRight, Droplets, Moon, Pencil, Save, Sparkles, Utensils, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { HandoverEvidenceReview } from "./HandoverEvidenceReview";

export interface HandoverInsight {
  id: string;
  residentId: string;
  jobId: string;
  staffRevision: boolean;
  authoredBy: string | null;
  version: number;
  shiftStart: string;
  shiftEnd: string;
  updatedAt: string;
  text: string;
  originalText: string;
  warnings: string[];
  canEdit: boolean;
  overviewNotice?: string | null;
  originalSections?: { category: string; claims: { text: string; sources: { source_type: string; source_id: string; version: string }[] }[] }[];
}

interface Props {
  residentName: string;
  summary: HandoverInsight | null;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  generationControl?: ReactNode;
  onSave: (summary: HandoverInsight, text: string) => Promise<void>;
}

const topics = [
  { label: "Nutrition", icon: Utensils, color: "bg-cyan-50 text-cyan-600" },
  { label: "Hydration", icon: Droplets, color: "bg-blue-50 text-blue-600" },
  { label: "Activities", icon: Activity, color: "bg-emerald-50 text-emerald-600" },
  { label: "Sleep", icon: Moon, color: "bg-teal-50 text-teal-600" },
];

function dateTime(value: string) {
  return new Date(value).toLocaleString("en-GB", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London",
  });
}

export function ResidentAIInsights({ residentName, summary, loading, error, onRetry, onSave, generationControl }: Props) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const dirty = editing && text !== summary?.text;

  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);

  useEffect(() => {
    if (!dirty) return;
    const preventUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [dirty]);

  function close() {
    if (saving) return;
    if (dirty && !window.confirm("Discard your unsaved handover changes?")) return;
    setOpen(false);
    setEditing(false);
    setSaveError("");
    trigger.current?.focus();
  }

  async function save() {
    if (!summary || !text.trim() || saving) return;
    setSaving(true);
    setSaveError("");
    try {
      await onSave(summary, text.trim());
      setEditing(false);
      setSaved(true);
    } catch {
      setSaveError("Your changes could not be saved. Keep this window open and try again. If someone else updated the draft, reload it before editing.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="flex h-full flex-col border-sky-100 bg-gradient-to-br from-white to-sky-50/40">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <Sparkles className="h-4 w-4 text-sky-600" /> AI insights
        </h3>
        <Pill tone={summary ? "amber" : "slate"}>{summary ? "Needs review" : "Handover"}</Pill>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Handover draft</p>
        {generationControl}
      </div>
      <div className="mt-2 min-h-20" aria-live="polite">
        {loading ? <p className="text-sm text-slate-500">Loading handover summary…</p> : error ? (
          <div role="alert">
            <p className="text-sm text-slate-600">{error}</p>
            {onRetry && <button type="button" onClick={onRetry} className="mt-2 text-sm font-medium text-brand-600">Try again</button>}
          </div>
        ) : summary ? (
          <>
            <p className="line-clamp-3 whitespace-pre-line text-sm leading-6 text-slate-700">{summary.text}</p>
            <p className="mt-2 text-xs text-slate-400">{dateTime(summary.shiftStart)} – {dateTime(summary.shiftEnd)} · UK time</p>
          </>
        ) : <p className="text-sm leading-6 text-slate-500">No AI handover is available yet. Generated summaries will appear here for review.</p>}
      </div>
      <div className="my-4 grid grid-cols-4 gap-2">
        {topics.map(({ label, icon: Icon, color }) => (
          <div key={label} className="flex flex-col items-center gap-2 rounded-xl border border-slate-100 bg-white/80 px-1 py-3 text-center">
            <span className={`rounded-lg p-2 ${color}`}><Icon className="h-4 w-4" /></span>
            <span className="text-[11px] text-slate-500">{label}</span>
            <span className="text-xs text-slate-400" aria-label={`${label} metric not available`}>—</span>
          </div>
        ))}
      </div>
      <p className="mb-3 text-[11px] text-slate-400">Category metrics are not available yet.</p>
      <button
        ref={trigger} type="button" disabled={!summary || loading || !!error}
        onClick={() => { setText(summary?.text ?? ""); setSaved(false); setSaveError(""); setOpen(true); }}
        className="mt-auto flex w-full items-center justify-center gap-2 rounded-lg py-2 text-sm font-semibold text-brand-600 transition-colors hover:bg-sky-50 disabled:cursor-not-allowed disabled:text-slate-400"
      >View AI summary <ArrowRight className="h-4 w-4" /></button>

      <dialog ref={dialog} aria-labelledby="ai-handover-title"
        onCancel={(event) => { event.preventDefault(); close(); }}
        className="fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto rounded-2xl border-0 bg-white p-0 shadow-2xl backdrop:bg-slate-900/40"
      >
        {summary && <>
          <div className="flex items-start justify-between gap-4 border-b border-slate-100 p-6">
            <div>
              <p className="mb-1 flex items-center gap-2 text-xs font-medium text-sky-600"><Sparkles className="h-4 w-4" /> AI insights · Handover</p>
              <h2 id="ai-handover-title" className="text-xl font-semibold text-slate-900">{residentName}</h2>
              <p className="mt-1 text-xs text-slate-500">{dateTime(summary.shiftStart)} – {dateTime(summary.shiftEnd)} · UK time</p>
            </div>
            <button type="button" onClick={close} disabled={saving} aria-label="Close handover summary" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X className="h-5 w-5" /></button>
          </div>
          <div className="space-y-5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Pill tone="amber">Draft · Nurse-in-charge review required</Pill>
              <span className="text-xs text-slate-400">{summary.staffRevision ? "Staff revision" : "AI original"} · Version {summary.version}</span>
            </div>
            {editing ? <div>
              <label htmlFor="handover-edit" className="mb-2 block text-sm font-medium text-slate-700">Edit handover draft</label>
              <textarea id="handover-edit" value={text} onChange={(event) => setText(event.target.value)} disabled={saving} maxLength={20000}
                className="min-h-72 w-full rounded-xl border border-slate-300 p-4 text-sm leading-7 text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100" />
              <p className="mt-1 text-xs text-slate-500">The original AI summary is preserved. Saving creates a staff revision and does not finalise the handover.</p>
            </div> : <div className="whitespace-pre-wrap text-sm leading-7 text-slate-700">{summary.text}</div>}
            {summary.overviewNotice && <p className="text-xs text-slate-500">{summary.overviewNotice}</p>}
            {summary.warnings.length > 0 && <details className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
              <summary className="cursor-pointer font-medium">Coverage notes · {summary.warnings.length} limitations to review</summary>
              <ul className="mt-2 list-disc space-y-1 pl-4">{summary.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
            </details>}
            {summary.staffRevision && <details className="rounded-xl border border-slate-200 p-4">
              <summary className="cursor-pointer text-sm font-medium text-slate-600">View original AI summary</summary>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">{summary.originalText}</p>
            </details>}
            <HandoverEvidenceReview key={`${summary.jobId}:${summary.version}`} summary={summary} />
            {saveError && <p role="alert" className="text-sm text-rose-700">{saveError}</p>}
            {saved && <p role="status" className="text-sm text-emerald-700">Handover draft saved. It still requires review.</p>}
            {summary.staffRevision && <p className="text-xs text-slate-500">Staff-authored handover statement. Author ID: {summary.authoredBy}. Changes have not been verified against source records.</p>}
            <p className="text-xs text-slate-400">Updated {dateTime(summary.updatedAt)} · UK time</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 bg-slate-50 px-6 py-4">
            {editing ? <>
              <Button variant="secondary" disabled={saving} onClick={() => { if (!dirty || window.confirm("Discard your unsaved changes?")) { setEditing(false); setSaveError(""); } }}>Cancel</Button>
              <Button disabled={saving || !text.trim() || !dirty} onClick={() => void save()}><Save className="h-4 w-4" />{saving ? "Saving…" : "Save handover"}</Button>
            </> : <>
              <Button variant="secondary" onClick={close}>Close</Button>
              {summary.canEdit && <Button onClick={() => { setText(summary.text); setEditing(true); setSaved(false); }}><Pencil className="h-4 w-4" />Edit draft</Button>}
            </>}
          </div>
        </>}
      </dialog>
    </Card>
  );
}
