import { clsx } from "clsx";
import { ChevronDown, ChevronLeft, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Pill } from "@/components/ui/Pill";
import { Tile, TileGrid } from "@/components/ui/Tile";
import { PageHeader } from "@/components/layout/PageHeader";
import { careIconFor } from "@/lib/careIcons";
import type { CareCategory, CareEventCreate, CareEventStatus, CareTemplate, Resident } from "@/types";
import { createCareEvent, fetchCareCategories, fetchCareTemplateDetail, fetchCareTemplatesByCategory, fetchResidents } from "@/utils/helper";

type Stage = "select" | "review";

const STATUS_OPTIONS: { value: CareEventStatus; label: string }[] = [
  { value: "completed", label: "Completed" },
  { value: "declined", label: "Declined" },
  { value: "refused", label: "Refused" },
  { value: "not_applicable", label: "Not Applicable" },
];

interface OptionState {
  selected: boolean;
  note: string;
}

interface TemplateFormState {
  status: CareEventStatus;
  optionState: Record<string, OptionState>;
  measurementValues: Record<string, string | boolean>;
  generalNote: string;
}

function defaultFormState(): TemplateFormState {
  return { status: "completed", optionState: {}, measurementValues: {}, generalNote: "" };
}

function buildPayload(residentId: string, template: CareTemplate, form: TemplateFormState, durationMinutes: number): CareEventCreate {
  const selectedOptionIds = Object.entries(form.optionState)
    .filter(([, s]) => s.selected)
    .map(([optId]) => optId);

  return {
    resident_id: residentId,
    template_id: template.id,
    status: form.status,
    note: form.generalNote.trim() || null,
    duration_minutes: durationMinutes,
    options: selectedOptionIds.map((optId) => ({
      care_template_option_id: optId,
      note: form.optionState[optId]?.note?.trim() || null,
    })),
    measurements: template.measurements
      .filter((m) => form.measurementValues[m.id] !== undefined && form.measurementValues[m.id] !== "")
      .map((m) => {
        const raw = form.measurementValues[m.id];
        if (m.data_type === "numeric") return { care_template_measurement_id: m.id, value_numeric: Number(raw) };
        if (m.data_type === "boolean") return { care_template_measurement_id: m.id, value_boolean: Boolean(raw) };
        return { care_template_measurement_id: m.id, value_text: String(raw) };
      }),
  };
}

export function CareRecordEntryPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [resident, setResident] = useState<Resident | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadingResident, setLoadingResident] = useState(true);

  const [categories, setCategories] = useState<CareCategory[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);

  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [templatesByCategory, setTemplatesByCategory] = useState<Record<string, CareTemplate[]>>({});
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  const [selection, setSelection] = useState<CareTemplate[]>([]);
  const [stage, setStage] = useState<Stage>("select");
  const [templateDetailCache, setTemplateDetailCache] = useState<Record<string, CareTemplate>>({});
  const [formStates, setFormStates] = useState<Record<string, TemplateFormState>>({});
  const [durationMinutes, setDurationMinutes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    fetchResidents()
      .then((residents) => {
        if (cancelled) return;
        const match = residents.find((r) => r.id === id);
        if (!match) {
          setNotFound(true);
          return;
        }
        setResident(match);
      })
      .catch(() => !cancelled && setNotFound(true))
      .finally(() => !cancelled && setLoadingResident(false));
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    fetchCareCategories()
      .then((data) => !cancelled && setCategories([...data].sort((a, b) => a.sort_order - b.sort_order)))
      .catch((err) => {
        if (cancelled) return;
        setCategoriesError(
          err?.response?.status === 403
            ? "Your role doesn't have permission to record care events."
            : "Couldn't load care categories. Please try again.",
        );
      })
      .finally(() => !cancelled && setLoadingCategories(false));
    return () => {
      cancelled = true;
    };
  }, []);

  // All categories load expanded, with every template prefetched up front -- there's
  // no per-category lazy-fetch anymore, so expanding/collapsing is just a display
  // toggle over data that's already in hand.
  useEffect(() => {
    if (categories.length === 0) return;
    let cancelled = false;
    setExpandedCategories(new Set(categories.map((c) => c.id)));
    setLoadingTemplates(true);
    Promise.all(
      categories.map((c) =>
        fetchCareTemplatesByCategory(c.id).then(
          (data) => [c.id, [...data].sort((a, b) => a.sort_order - b.sort_order)] as const,
        ),
      ),
    )
      .then((pairs) => {
        if (cancelled) return;
        const map: Record<string, CareTemplate[]> = {};
        pairs.forEach(([categoryId, list]) => {
          map[categoryId] = list;
        });
        setTemplatesByCategory(map);
      })
      .finally(() => !cancelled && setLoadingTemplates(false));
    return () => {
      cancelled = true;
    };
  }, [categories]);

  useEffect(() => {
    if (!successMessage) return;
    const t = setTimeout(() => setSuccessMessage(null), 3000);
    return () => clearTimeout(t);
  }, [successMessage]);

  function toggleCategory(categoryId: string) {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(categoryId)) next.delete(categoryId);
      else next.add(categoryId);
      return next;
    });
  }

  function toggleTemplateSelection(template: CareTemplate) {
    setSelection((prev) => {
      const exists = prev.some((t) => t.id === template.id);
      if (exists) return prev.filter((t) => t.id !== template.id);
      return [...prev, template];
    });
  }

  function removeFromSelection(templateId: string) {
    setSelection((prev) => prev.filter((t) => t.id !== templateId));
  }

  function startReview() {
    if (selection.length === 0) return;
    setSubmitError(null);
    setStage("review");
    const missing = selection.filter((t) => !templateDetailCache[t.id]);
    if (missing.length === 0) return;
    Promise.all(missing.map((t) => fetchCareTemplateDetail(t.id))).then((details) => {
      setTemplateDetailCache((prev) => {
        const next = { ...prev };
        details.forEach((d) => {
          next[d.id] = d;
        });
        return next;
      });
    });
  }

  function updateForm(templateId: string, patch: Partial<TemplateFormState> | ((prev: TemplateFormState) => TemplateFormState)) {
    setFormStates((prev) => {
      const current = prev[templateId] ?? defaultFormState();
      const next = typeof patch === "function" ? patch(current) : { ...current, ...patch };
      return { ...prev, [templateId]: next };
    });
  }

  function toggleOption(templateId: string, optionId: string) {
    updateForm(templateId, (prev) => ({
      ...prev,
      optionState: {
        ...prev.optionState,
        [optionId]: { selected: !prev.optionState[optionId]?.selected, note: prev.optionState[optionId]?.note ?? "" },
      },
    }));
  }

  function setOptionNote(templateId: string, optionId: string, note: string) {
    updateForm(templateId, (prev) => ({
      ...prev,
      optionState: { ...prev.optionState, [optionId]: { selected: prev.optionState[optionId]?.selected ?? false, note } },
    }));
  }

  function setMeasurement(templateId: string, measurementId: string, value: string | boolean) {
    updateForm(templateId, (prev) => ({ ...prev, measurementValues: { ...prev.measurementValues, [measurementId]: value } }));
  }

  function isEntryValid(template: CareTemplate): boolean {
    const detail = templateDetailCache[template.id];
    if (!detail) return false;
    const form = formStates[template.id] ?? defaultFormState();
    if (detail.requires_note && !form.generalNote.trim()) return false;
    if (form.status !== "completed") return true;

    const missingRequiredMeasurement = detail.measurements.some((m) => {
      if (!m.is_required) return false;
      const v = form.measurementValues[m.id];
      return v === undefined || v === "";
    });
    if (missingRequiredMeasurement) return false;

    const hasSelectedOption = Object.values(form.optionState).some((s) => s.selected);
    return hasSelectedOption || Object.values(form.measurementValues).some((v) => v !== "" && v !== undefined) || form.generalNote.trim().length > 0;
  }

  const durationValue = Number(durationMinutes);
  const durationValid = durationMinutes.trim() !== "" && Number.isFinite(durationValue) && durationValue > 0;
  const canSaveAll = selection.length > 0 && selection.every((t) => isEntryValid(t)) && durationValid;

  async function handleSaveAll() {
    if (!id || !canSaveAll) return;
    setSubmitting(true);
    setSubmitError(null);
    const results = await Promise.allSettled(
      selection.map((t) => {
        const form = formStates[t.id] ?? defaultFormState();
        const detail = templateDetailCache[t.id] ?? t;
        return createCareEvent(buildPayload(id, detail, form, durationValue)).then(() => t.id);
      }),
    );
    setSubmitting(false);

    const failed = selection.filter((_, i) => results[i].status === "rejected");
    if (failed.length === 0) {
      setSuccessMessage(`${selection.length} ${selection.length === 1 ? "entry" : "entries"} logged`);
      setSelection([]);
      setFormStates({});
      setDurationMinutes("");
      setStage("select");
    } else {
      const succeeded = selection.length - failed.length;
      setSubmitError(`${succeeded} of ${selection.length} saved. ${failed.length} failed — please retry.`);
      setSelection(failed);
    }
  }

  const filteredCategories = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return categories.map((category) => {
      const all = templatesByCategory[category.id] ?? [];
      const templates = query ? all.filter((t) => t.name.toLowerCase().includes(query)) : all;
      return { category, templates, matched: !query || templates.length > 0 };
    });
  }, [categories, templatesByCategory, searchQuery]);

  if (notFound) {
    return <Navigate to="/residents" replace />;
  }

  if (loadingResident || !resident) {
    return <div className="py-12 text-center text-sm text-slate-400">Loading resident…</div>;
  }

  const displayName = `${resident.preferred_name || resident.first_name} ${resident.last_name}`;
  const isSearching = searchQuery.trim().length > 0;

  return (
    <div className="pb-20">
      <button
        onClick={() => (stage === "review" ? setStage("select") : navigate(`/residents/${id}`))}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        <ChevronLeft className="h-4 w-4" />
        {stage === "review" ? "Back to selection" : `Back to ${displayName}`}
      </button>

      <PageHeader
        title={`Record Care · ${displayName}`}
        subtitle={
          stage === "select"
            ? "Select one or more care entries, then continue"
            : `Add detail for ${selection.length} selected ${selection.length === 1 ? "entry" : "entries"}`
        }
      />

      {successMessage && (
        <div className="mb-4 rounded-lg bg-emerald-50 px-4 py-2.5 text-sm font-medium text-emerald-700">✓ {successMessage}</div>
      )}
      {submitError && stage === "select" && (
        <div className="mb-4 rounded-lg bg-rose-50 px-4 py-2.5 text-sm text-rose-700">{submitError}</div>
      )}

      {stage === "select" && categoriesError && (
        <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{categoriesError}</div>
      )}

      {stage === "select" && !categoriesError && (
        <>
          <div className="relative mb-4 max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search all care entries…"
              className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 shadow-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
          </div>

          <div className="space-y-3">
            {filteredCategories.map(({ category, templates, matched }) => {
              if (!matched) return null;
              const expanded = isSearching || expandedCategories.has(category.id);
              const selectedCount = selection.filter((t) => t.category_id === category.id).length;
              const Icon = careIconFor(category.icon);

              return (
                <div key={category.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                  <button
                    type="button"
                    onClick={() => toggleCategory(category.id)}
                    className="flex w-full items-center gap-3 px-4 py-3.5 text-left hover:bg-slate-50"
                  >
                    <Icon className="h-5 w-5 shrink-0 text-slate-500" />
                    <span className="flex-1 font-medium text-slate-900">{category.name}</span>
                    {isSearching && <span className="text-xs text-slate-400">{templates.length} match{templates.length === 1 ? "" : "es"}</span>}
                    {selectedCount > 0 && <Pill tone="emerald">{selectedCount} selected</Pill>}
                    <ChevronDown className={clsx("h-4 w-4 shrink-0 text-slate-400 transition-transform", expanded && "rotate-180")} />
                  </button>

                  {expanded && (
                    <div className="border-t border-slate-100 p-4">
                      {loadingTemplates && <p className="py-4 text-center text-sm text-slate-400">Loading…</p>}
                      {!loadingTemplates && templates.length === 0 && (
                        <p className="py-4 text-center text-sm text-slate-400">
                          {isSearching ? `No matches for "${searchQuery}".` : "No templates configured for this category yet."}
                        </p>
                      )}
                      {!loadingTemplates && templates.length > 0 && (
                        <TileGrid>
                          {templates.map((template) => (
                            <Tile
                              key={template.id}
                              label={template.name}
                              selected={selection.some((t) => t.id === template.id)}
                              onClick={() => toggleTemplateSelection(template)}
                            />
                          ))}
                        </TileGrid>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            {loadingCategories && <p className="py-6 text-center text-sm text-slate-400">Loading categories…</p>}
          </div>
        </>
      )}

      {stage === "select" && selection.length > 0 && (
        <div className="fixed bottom-6 right-6 z-40 flex items-center gap-3 rounded-full border border-slate-200 bg-white px-4 py-2.5 shadow-lg">
          <span className="text-sm font-medium text-slate-700">{selection.length} selected</span>
          <button type="button" onClick={() => setSelection([])} className="text-sm text-slate-400 hover:text-slate-600">
            Clear
          </button>
          <Button onClick={startReview}>Continue</Button>
        </div>
      )}

      {stage === "review" && (
        <div className="mx-auto max-w-2xl space-y-5">
          {selection.map((template) => {
            const detail = templateDetailCache[template.id];
            const form = formStates[template.id] ?? defaultFormState();

            return (
              <div key={template.id} className="rounded-2xl border border-slate-200 bg-white p-6">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <h2 className="text-lg font-semibold text-slate-900">{template.name}</h2>
                  <button
                    type="button"
                    onClick={() => removeFromSelection(template.id)}
                    className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                  >
                    <X className="h-3.5 w-3.5" />
                    Remove
                  </button>
                </div>

                {!detail ? (
                  <p className="py-4 text-center text-sm text-slate-400">Loading…</p>
                ) : (
                  <div className="space-y-4">
                    {detail.description && <p className="text-sm text-slate-500">{detail.description}</p>}

                    <div>
                      <p className="mb-1.5 text-sm font-medium text-slate-700">Status</p>
                      <div className="flex flex-wrap gap-2">
                        {STATUS_OPTIONS.map((opt) => (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => updateForm(template.id, { status: opt.value })}
                            className={clsx(
                              "rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                              form.status === opt.value ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200",
                            )}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {[...detail.sections]
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map((section) => (
                        <div key={section.id}>
                          <p className="mb-1.5 text-sm font-medium text-slate-700">{section.name}</p>
                          <div className="flex flex-wrap gap-2">
                            {[...section.options]
                              .sort((a, b) => a.sort_order - b.sort_order)
                              .map((option) => {
                                const state = form.optionState[option.id];
                                return (
                                  <div key={option.id} className="space-y-1.5">
                                    <Tile
                                      size="sm"
                                      label={option.label}
                                      selected={state?.selected}
                                      alert={option.triggers_alert}
                                      onClick={() => toggleOption(template.id, option.id)}
                                      className="w-20"
                                    />
                                    {option.requires_note && state?.selected && (
                                      <textarea
                                        value={state.note}
                                        onChange={(e) => setOptionNote(template.id, option.id, e.target.value)}
                                        placeholder="Note required…"
                                        rows={2}
                                        className="w-20 rounded-lg border border-slate-300 p-1.5 text-xs outline-none focus:border-brand-500"
                                      />
                                    )}
                                  </div>
                                );
                              })}
                          </div>
                        </div>
                      ))}

                    {detail.measurements.map((measurement) => (
                      <div key={measurement.id}>
                        <label className="mb-1.5 block text-sm font-medium text-slate-700">
                          {measurement.name}
                          {measurement.is_required && <span className="text-rose-500"> *</span>}
                        </label>
                        {measurement.data_type === "boolean" ? (
                          <label className="flex items-center gap-2 text-sm text-slate-700">
                            <input
                              type="checkbox"
                              checked={Boolean(form.measurementValues[measurement.id])}
                              onChange={(e) => setMeasurement(template.id, measurement.id, e.target.checked)}
                              className="h-4 w-4 rounded border-slate-300"
                            />
                            Yes
                          </label>
                        ) : measurement.data_type === "numeric" ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              min={measurement.min_value ?? undefined}
                              max={measurement.max_value ?? undefined}
                              value={(form.measurementValues[measurement.id] as string) ?? ""}
                              onChange={(e) => setMeasurement(template.id, measurement.id, e.target.value)}
                              className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                            />
                            {measurement.unit && <span className="text-sm text-slate-500">{measurement.unit}</span>}
                          </div>
                        ) : (
                          <input
                            type="text"
                            value={(form.measurementValues[measurement.id] as string) ?? ""}
                            onChange={(e) => setMeasurement(template.id, measurement.id, e.target.value)}
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                          />
                        )}
                      </div>
                    ))}

                    <div>
                      <label className="mb-1.5 block text-sm font-medium text-slate-700">
                        Note
                        {detail.requires_note && <span className="text-rose-500"> *</span>}
                      </label>
                      <textarea
                        rows={3}
                        value={form.generalNote}
                        onChange={(e) => updateForm(template.id, { generalNote: e.target.value })}
                        placeholder="Add any additional detail…"
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Time spent this round (minutes)
              <span className="text-rose-500"> *</span>
            </label>
            <input
              type="number"
              min={1}
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(e.target.value)}
              placeholder="e.g. 15"
              className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
            <p className="mt-1.5 text-xs text-slate-500">Tracks staff time spent on {displayName} for this round of care.</p>
          </div>

          {submitError && <p className="text-sm text-rose-600">{submitError}</p>}

          <div className="flex justify-end gap-3 pb-6">
            <Button type="button" variant="secondary" onClick={() => setStage("select")}>
              Back
            </Button>
            <Button type="button" onClick={handleSaveAll} disabled={!canSaveAll || submitting}>
              {submitting ? "Saving…" : `Save (${selection.length})`}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
