import { ChevronLeft } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Tile, TileGrid } from "@/components/ui/Tile";
import { PageHeader } from "@/components/layout/PageHeader";
import { careIconFor } from "@/lib/careIcons";
import type { CareCategory, CareEventCreate, CareEventStatus, CareTemplate, Resident } from "@/types";
import { createCareEvent, fetchCareCategories, fetchCareTemplateDetail, fetchCareTemplatesByCategory, fetchResidents } from "@/utils/helper";

type View = "categories" | "templates";

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

export function CareRecordEntryPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [resident, setResident] = useState<Resident | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadingResident, setLoadingResident] = useState(true);

  const [view, setView] = useState<View>("categories");
  const [categories, setCategories] = useState<CareCategory[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);

  const [selectedCategory, setSelectedCategory] = useState<CareCategory | null>(null);
  const [templates, setTemplates] = useState<CareTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  const [activeTemplate, setActiveTemplate] = useState<CareTemplate | null>(null);
  const [loadingTemplateDetail, setLoadingTemplateDetail] = useState(false);

  const [status, setStatus] = useState<CareEventStatus>("completed");
  const [optionState, setOptionState] = useState<Record<string, OptionState>>({});
  const [measurementValues, setMeasurementValues] = useState<Record<string, string | boolean>>({});
  const [generalNote, setGeneralNote] = useState("");
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

  useEffect(() => {
    if (!successMessage) return;
    const t = setTimeout(() => setSuccessMessage(null), 3000);
    return () => clearTimeout(t);
  }, [successMessage]);

  function openCategory(category: CareCategory) {
    setSelectedCategory(category);
    setView("templates");
    setLoadingTemplates(true);
    fetchCareTemplatesByCategory(category.id)
      .then((data) => setTemplates([...data].sort((a, b) => a.sort_order - b.sort_order)))
      .finally(() => setLoadingTemplates(false));
  }

  function backToCategories() {
    setView("categories");
    setSelectedCategory(null);
    setTemplates([]);
  }

  function openTemplate(template: CareTemplate) {
    setSubmitError(null);
    setStatus("completed");
    setOptionState({});
    setMeasurementValues({});
    setGeneralNote("");
    setActiveTemplate(template);
    setLoadingTemplateDetail(true);
    fetchCareTemplateDetail(template.id)
      .then((detail) => setActiveTemplate(detail))
      .finally(() => setLoadingTemplateDetail(false));
  }

  function closeTemplate() {
    setActiveTemplate(null);
    setSubmitError(null);
  }

  function toggleOption(optionId: string) {
    setOptionState((prev) => ({
      ...prev,
      [optionId]: { selected: !prev[optionId]?.selected, note: prev[optionId]?.note ?? "" },
    }));
  }

  function setOptionNote(optionId: string, note: string) {
    setOptionState((prev) => ({
      ...prev,
      [optionId]: { selected: prev[optionId]?.selected ?? false, note },
    }));
  }

  function setMeasurementValue(measurementId: string, value: string | boolean) {
    setMeasurementValues((prev) => ({ ...prev, [measurementId]: value }));
  }

  const selectedOptionIds = useMemo(
    () => Object.entries(optionState).filter(([, s]) => s.selected).map(([optId]) => optId),
    [optionState],
  );

  const canSubmit = useMemo(() => {
    if (!activeTemplate) return false;
    if (activeTemplate.requires_note && !generalNote.trim()) return false;
    if (status !== "completed") return true;

    const missingRequiredMeasurement = activeTemplate.measurements.some((m) => {
      if (!m.is_required) return false;
      const v = measurementValues[m.id];
      return v === undefined || v === "";
    });
    if (missingRequiredMeasurement) return false;

    return selectedOptionIds.length > 0 || Object.values(measurementValues).some((v) => v !== "" && v !== undefined) || generalNote.trim().length > 0;
  }, [activeTemplate, status, selectedOptionIds, measurementValues, generalNote]);

  async function handleSubmit() {
    if (!activeTemplate || !id || !canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload: CareEventCreate = {
        resident_id: id,
        template_id: activeTemplate.id,
        status,
        note: generalNote.trim() || null,
        options: selectedOptionIds.map((optId) => ({
          care_template_option_id: optId,
          note: optionState[optId]?.note?.trim() || null,
        })),
        measurements: activeTemplate.measurements
          .filter((m) => measurementValues[m.id] !== undefined && measurementValues[m.id] !== "")
          .map((m) => {
            const raw = measurementValues[m.id];
            if (m.data_type === "numeric") return { care_template_measurement_id: m.id, value_numeric: Number(raw) };
            if (m.data_type === "boolean") return { care_template_measurement_id: m.id, value_boolean: Boolean(raw) };
            return { care_template_measurement_id: m.id, value_text: String(raw) };
          }),
      };
      await createCareEvent(payload);
      setSuccessMessage(`${activeTemplate.name} logged`);
      closeTemplate();
    } catch (err) {
      console.error(err);
      setSubmitError("Couldn't save this entry. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (notFound) {
    return <Navigate to="/residents" replace />;
  }

  if (loadingResident || !resident) {
    return <div className="py-12 text-center text-sm text-slate-400">Loading resident…</div>;
  }

  const displayName = `${resident.preferred_name || resident.first_name} ${resident.last_name}`;

  return (
    <div>
      <button
        onClick={() => (view === "templates" ? backToCategories() : navigate(`/residents/${id}`))}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        <ChevronLeft className="h-4 w-4" />
        {view === "templates" ? "Back to categories" : `Back to ${displayName}`}
      </button>

      <PageHeader
        title={`Record Care · ${displayName}`}
        subtitle={
          view === "categories"
            ? "Choose a care category"
            : `${selectedCategory?.name} · choose what you're recording`
        }
      />

      {successMessage && (
        <div className="mb-4 rounded-lg bg-emerald-50 px-4 py-2.5 text-sm font-medium text-emerald-700">
          ✓ {successMessage}
        </div>
      )}

      {view === "categories" && categoriesError && (
        <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{categoriesError}</div>
      )}
      {view === "categories" && !categoriesError && (
        <TileGrid>
          {categories.map((category) => (
            <Tile key={category.id} label={category.name} icon={careIconFor(category.icon)} onClick={() => openCategory(category)} />
          ))}
        </TileGrid>
      )}
      {view === "categories" && loadingCategories && <p className="py-6 text-center text-sm text-slate-400">Loading categories…</p>}

      {view === "templates" && (
        <TileGrid>
          {templates.map((template) => (
            <Tile
              key={template.id}
              label={template.name}
              icon={careIconFor(selectedCategory?.icon)}
              onClick={() => openTemplate(template)}
            />
          ))}
        </TileGrid>
      )}
      {view === "templates" && loadingTemplates && <p className="py-6 text-center text-sm text-slate-400">Loading…</p>}
      {view === "templates" && !loadingTemplates && templates.length === 0 && (
        <p className="py-6 text-center text-sm text-slate-400">No templates configured for this category yet.</p>
      )}

      {activeTemplate && (
        <Modal title={activeTemplate.name} onClose={closeTemplate}>
          {loadingTemplateDetail ? (
            <p className="py-6 text-center text-sm text-slate-400">Loading…</p>
          ) : (
            <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
              {activeTemplate.description && <p className="text-sm text-slate-500">{activeTemplate.description}</p>}

              <div>
                <p className="mb-1.5 text-sm font-medium text-slate-700">Status</p>
                <div className="flex flex-wrap gap-2">
                  {STATUS_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setStatus(opt.value)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                        status === opt.value ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {[...activeTemplate.sections]
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((section) => (
                  <div key={section.id}>
                    <p className="mb-1.5 text-sm font-medium text-slate-700">{section.name}</p>
                    <div className="flex flex-wrap gap-2">
                      {[...section.options]
                        .sort((a, b) => a.sort_order - b.sort_order)
                        .map((option) => {
                          const state = optionState[option.id];
                          return (
                            <div key={option.id} className="space-y-1.5">
                              <Tile
                                size="sm"
                                label={option.label}
                                selected={state?.selected}
                                alert={option.triggers_alert}
                                onClick={() => toggleOption(option.id)}
                                className="w-20"
                              />
                              {option.requires_note && state?.selected && (
                                <textarea
                                  value={state.note}
                                  onChange={(e) => setOptionNote(option.id, e.target.value)}
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

              {activeTemplate.measurements.map((measurement) => (
                  <div key={measurement.id}>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">
                      {measurement.name}
                      {measurement.is_required && <span className="text-rose-500"> *</span>}
                    </label>
                    {measurement.data_type === "boolean" ? (
                      <label className="flex items-center gap-2 text-sm text-slate-700">
                        <input
                          type="checkbox"
                          checked={Boolean(measurementValues[measurement.id])}
                          onChange={(e) => setMeasurementValue(measurement.id, e.target.checked)}
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
                          value={(measurementValues[measurement.id] as string) ?? ""}
                          onChange={(e) => setMeasurementValue(measurement.id, e.target.value)}
                          className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                        />
                        {measurement.unit && <span className="text-sm text-slate-500">{measurement.unit}</span>}
                      </div>
                    ) : (
                      <input
                        type="text"
                        value={(measurementValues[measurement.id] as string) ?? ""}
                        onChange={(e) => setMeasurementValue(measurement.id, e.target.value)}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                      />
                    )}
                  </div>
                ))}

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Note
                  {activeTemplate.requires_note && <span className="text-rose-500"> *</span>}
                </label>
                <textarea
                  rows={3}
                  value={generalNote}
                  onChange={(e) => setGeneralNote(e.target.value)}
                  placeholder="Add any additional detail…"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                />
              </div>

              {submitError && <p className="text-sm text-rose-600">{submitError}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <Button type="button" variant="secondary" onClick={closeTemplate}>
                  Cancel
                </Button>
                <Button type="button" onClick={handleSubmit} disabled={!canSubmit || submitting}>
                  {submitting ? "Saving…" : "Save Entry"}
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
