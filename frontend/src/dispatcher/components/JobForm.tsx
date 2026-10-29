import { useEffect, useState, type FormEvent } from "react";
import {
  createJob,
  fetchOrganization,
  fetchSkills,
  updateJob,
  type Skill,
} from "../../shared/api/client";
import { ApiError } from "../../shared/api/http";
import {
  CATEGORY_DEFAULT_MINUTES,
  CATEGORY_DEFAULT_SKILL,
  CATEGORY_LABEL,
  type JobCategory,
  type JobCreateInput,
  type JobDetail,
} from "../../shared/api/models";
import { splitLocal, toIso } from "../../shared/jobTime";
import { ui } from "../../shared/ui";

const ZIP = /^\d{5}(-\d{4})?$/;
// A ZIP typed at the end of the address ("... Austin, TX 78701") is picked up automatically.
const TRAILING_ZIP = /\b(\d{5}(?:-\d{4})?)\s*$/;

/** The job's title is the first line of the problem, so the dispatcher types it once. */
function deriveTitle(description: string, category: JobCategory): string {
  const first = description.trim().split(/\n|(?<=[.!?])\s/)[0] ?? "";
  if (first === "") return `${CATEGORY_LABEL[category]} job`;
  if (first.length <= 70) return first;
  return first.slice(0, 70).replace(/\s+\S*$/, "") + "…";
}

const hhmm = (t: string | null | undefined, fallback: string) =>
  t ? t.slice(0, 5) : fallback;
const CATEGORIES = Object.keys(CATEGORY_LABEL) as JobCategory[];

interface Props {
  /** Present = edit this job; absent = create a new one. */
  job?: JobDetail;
  onSaved: (job: JobDetail) => void;
  onCancel: () => void;
  /** Called when the server says the job changed under us (409): reload it. */
  onReload?: () => void;
}

export default function JobForm({ job, onSaved, onCancel, onReload }: Props) {
  const editing = job !== undefined;
  // Once a job is planned, the address, time and skills are frozen (the API enforces it too).
  const locked = editing && job.status !== "unassigned";

  const start = job?.slot_start ? splitLocal(job.slot_start) : null;
  const end = job?.slot_end ? splitLocal(job.slot_end) : null;

  const [skills, setSkills] = useState<Skill[]>([]);
  const [titleText, setTitleText] = useState(job?.title ?? "");
  const [customerName, setCustomerName] = useState(job?.customer_name ?? "");
  const [customerPhone, setCustomerPhone] = useState(job?.customer_phone ?? "");
  const [category, setCategory] = useState<JobCategory>(
    job?.category ?? "hvac",
  );
  const [description, setDescription] = useState(job?.description ?? "");
  const [address, setAddress] = useState(job?.address ?? "");
  const [postalCode, setPostalCode] = useState(job?.postal_code ?? "");
  const [duration, setDuration] = useState(
    String(job?.estimated_duration_minutes ?? ""),
  );
  const [urgent, setUrgent] = useState(job?.is_urgent ?? false);
  const [slotDate, setSlotDate] = useState(start?.date ?? "");
  // The window defaults to the organization's working day, so most jobs need no typing here.
  const [slotStart, setSlotStart] = useState(start?.time ?? "08:00");
  const [slotEnd, setSlotEnd] = useState(end?.time ?? "17:00");
  // Until the dispatcher touches the chips, the skills follow the category.
  const [skillsTouched, setSkillsTouched] = useState(editing);
  const [pickedSkills, setPickedSkills] = useState<number[]>(
    job?.acceptable_skills.map((s) => s.id) ?? [],
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchSkills()
      .then(setSkills)
      .catch(() => setSkills([]));
    if (!editing) {
      fetchOrganization()
        .then((o) => {
          setSlotStart(hhmm(o.work_start, "08:00"));
          setSlotEnd(hhmm(o.work_end, "17:00"));
        })
        .catch(() => undefined);
    }
  }, [editing]);

  const zipInAddress = TRAILING_ZIP.exec(address.trim())?.[1] ?? null;
  const zip = zipInAddress ?? postalCode;
  const showZipField =
    zipInAddress === null && (editing || address.trim() !== "");
  // Until the dispatcher sets it, the duration follows the category.
  const minutes =
    duration !== "" ? duration : String(CATEGORY_DEFAULT_MINUTES[category]);

  const categoryDefaults = skills
    .filter((s) => s.name === CATEGORY_DEFAULT_SKILL[category])
    .map((s) => s.id);
  const skillIds = skillsTouched ? pickedSkills : categoryDefaults;

  function toggleSkill(id: number, on: boolean) {
    setSkillsTouched(true);
    setPickedSkills(on ? [...skillIds, id] : skillIds.filter((x) => x !== id));
  }

  function validate(): Record<string, string> {
    const found: Record<string, string> = {};
    if (!locked) {
      if (!ZIP.test(zip)) found.postal_code = "Add the ZIP code, like 12345.";
      if (!urgent) {
        if (!slotDate) found.slot_start = "Pick the day.";
        else if (slotEnd <= slotStart)
          found.slot_end = "Must be later than the start.";
      }
      if (skillIds.length === 0) found.skill_ids = "Select at least one skill.";
    }
    return found;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const problems = validate();
    setErrors(problems);
    setConflict(false);
    if (Object.keys(problems).length > 0) return;

    const title = editing ? titleText : deriveTitle(description, category);
    const phone = customerPhone.trim() === "" ? null : customerPhone.trim();
    const slot = urgent
      ? { slot_start: null, slot_end: null }
      : {
          slot_start: toIso(slotDate, slotStart),
          slot_end: toIso(slotDate, slotEnd),
        };

    setBusy(true);
    try {
      let saved: JobDetail;
      if (job) {
        saved = await updateJob(job.id, {
          version: job.version,
          title,
          description,
          customer_name: customerName,
          customer_phone: phone,
          category,
          ...(locked
            ? {}
            : {
                is_urgent: urgent,
                address,
                postal_code: zip,
                estimated_duration_minutes: Number(minutes),
                skill_ids: skillIds,
                ...slot,
              }),
        });
      } else {
        const input: JobCreateInput = {
          title,
          description,
          customer_name: customerName,
          customer_phone: phone,
          category,
          is_urgent: urgent,
          address,
          postal_code: zip,
          estimated_duration_minutes: Number(minutes),
          ...(urgent ? {} : slot),
          // Omitted unless the dispatcher chose: the server then applies the category rule.
          ...(skillsTouched ? { skill_ids: skillIds } : {}),
        };
        saved = await createJob(input);
      }
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setConflict(true);
      setErrors(
        err instanceof ApiError
          ? { ...err.fieldErrors, _: err.message }
          : { _: "Could not reach the server." },
      );
    } finally {
      setBusy(false);
    }
  }

  const fieldError = (k: string) =>
    errors[k] && <span className={ui.error}>{errors[k]}</span>;
  const showSummary = errors._ && !Object.keys(errors).some((k) => k !== "_");

  return (
    <form onSubmit={onSubmit} className={ui.form} noValidate>
      {locked && (
        <p className={ui.notice}>
          This job is already planned, so its address, time and skills are
          locked. Unassign it first to change them.
        </p>
      )}

      <Section title="Customer">
        <div className={ui.row}>
          <label className={ui.label}>
            Name
            <input
              className={ui.input}
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              maxLength={50}
              required
            />
            {fieldError("customer_name")}
          </label>
          <label className={ui.label}>
            <span className="whitespace-nowrap">
              Phone <span className="font-normal">(optional)</span>
            </span>
            <input
              className={ui.input}
              type="tel"
              inputMode="tel"
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              maxLength={20}
              title="Digits, spaces, + ( ) - . only, e.g. +1 (555) 123-4567"
            />
            {fieldError("customer_phone")}
          </label>
        </div>
      </Section>

      <Section title="The problem">
        <div
          className="flex flex-wrap gap-2"
          role="radiogroup"
          aria-label="Type of work"
        >
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={category === c}
              onClick={() => setCategory(c)}
              className={`min-h-11 rounded-full border-[1.5px] px-4 text-sm font-semibold ${
                category === c
                  ? "border-brand bg-brand-soft text-brand-ink"
                  : "border-line-strong bg-surface hover:bg-canvas"
              }`}
            >
              {CATEGORY_LABEL[c]}
            </button>
          ))}
        </div>
        {fieldError("category")}
        <label className={ui.label}>
          Problem, as the customer describes it
          <textarea
            className={ui.input}
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. The AC is blowing warm air since last night"
            required
          />
          {fieldError("description")}
        </label>
        {editing && (
          <label className={ui.label}>
            Title
            <input
              className={ui.input}
              value={titleText}
              onChange={(e) => setTitleText(e.target.value)}
              maxLength={100}
              required
            />
            {fieldError("title")}
          </label>
        )}
      </Section>

      <Section title="Where">
        <label className={ui.label}>
          Address
          <input
            className={ui.input}
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            maxLength={255}
            required
            disabled={locked}
            autoComplete="street-address"
            placeholder="Full address, e.g. 1204 Congress Ave, Austin, TX 78701"
          />
          {fieldError("address")}
        </label>
        {showZipField && (
          <label className={`${ui.label} max-w-48`}>
            ZIP code
            <input
              className={ui.input}
              value={postalCode}
              onChange={(e) => setPostalCode(e.target.value)}
              maxLength={10}
              inputMode="numeric"
              disabled={locked}
            />
            {fieldError("postal_code")}
          </label>
        )}
        <p className={ui.muted}>
          The map location is found automatically when you save.
        </p>
      </Section>

      <Section title="When can we visit?">
        <div
          className="flex flex-wrap gap-2"
          role="radiogroup"
          aria-label="Timing"
        >
          {[
            { value: false, label: "Pick a day" },
            { value: true, label: "Urgent: as soon as possible" },
          ].map((o) => (
            <button
              key={o.label}
              type="button"
              role="radio"
              aria-checked={urgent === o.value}
              disabled={locked}
              onClick={() => setUrgent(o.value)}
              className={`min-h-11 rounded-full border-[1.5px] px-4 text-sm font-semibold disabled:opacity-60 ${
                urgent === o.value
                  ? "border-brand bg-brand-soft text-brand-ink"
                  : "border-line-strong bg-surface hover:bg-canvas"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
        {urgent ? (
          <p className={ui.muted}>
            Urgent jobs have no time window. They are planned first.
          </p>
        ) : (
          <>
            <div className={ui.row}>
              <label className={ui.label}>
                Day
                <input
                  className={ui.input}
                  type="date"
                  value={slotDate}
                  onChange={(e) => setSlotDate(e.target.value)}
                  disabled={locked}
                />
                {fieldError("slot_start")}
              </label>
              <label className={ui.label}>
                Available from
                <input
                  className={ui.input}
                  type="time"
                  value={slotStart}
                  onChange={(e) => setSlotStart(e.target.value)}
                  disabled={locked}
                />
              </label>
              <label className={ui.label}>
                Available until
                <input
                  className={ui.input}
                  type="time"
                  value={slotEnd}
                  onChange={(e) => setSlotEnd(e.target.value)}
                  disabled={locked}
                />
                {fieldError("slot_end")}
              </label>
            </div>
            <p className={ui.muted}>
              When someone can be at the address. The system picks the exact
              visit time inside this window.
            </p>
          </>
        )}
      </Section>

      <details className="rounded-xl border border-line bg-canvas px-4 py-3">
        <summary className="cursor-pointer text-sm font-semibold">
          Set automatically: about{" "}
          {Number(minutes) >= 60
            ? `${+(Number(minutes) / 60).toFixed(1)} h`
            : `${minutes} min`}
          ,{" "}
          {skillIds.length === 0
            ? "no skill chosen"
            : skills
                .filter((s) => skillIds.includes(s.id))
                .map((s) => s.name)
                .join(", ")}
          . Change
        </summary>
        <div className="mt-3 grid gap-4">
          <label className={`${ui.label} max-w-60`}>
            Expected duration (minutes)
            <input
              className={ui.input}
              type="number"
              min={1}
              max={1440}
              step={5}
              value={minutes}
              onChange={(e) => setDuration(e.target.value)}
              disabled={locked}
            />
            {fieldError("estimated_duration_minutes")}
          </label>
          <fieldset className="grid gap-2" disabled={locked}>
            <legend className="mb-1 text-sm font-medium text-ink-muted">
              Technicians with these skills can be given the job
            </legend>
            <div className="flex flex-wrap gap-2">
              {skills.map((s) => (
                <label
                  key={s.id}
                  className="flex min-h-9 items-center gap-2 rounded-full bg-brand-soft px-3 py-1 text-sm font-medium text-brand-ink"
                >
                  <input
                    type="checkbox"
                    className="size-4 accent-brand"
                    checked={skillIds.includes(s.id)}
                    onChange={(e) => toggleSkill(s.id, e.target.checked)}
                  />
                  {s.name}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      </details>
      {fieldError("skill_ids")}

      {showSummary && !conflict && (
        <p role="alert" className={ui.error}>
          {errors._}
        </p>
      )}
      {errors.non_field_errors && (
        <p role="alert" className={ui.error}>
          {errors.non_field_errors}
        </p>
      )}
      {conflict && onReload && (
        <div className="flex flex-wrap items-center gap-3">
          <p role="alert" className={ui.error}>
            {errors._}
          </p>
          <button type="button" className={ui.btnSmall} onClick={onReload}>
            Reload the latest version
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button className={ui.btn} disabled={busy}>
          {busy ? "Saving…" : editing ? "Save changes" : "Create job"}
        </button>
        <button type="button" className={ui.btnSmall} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="grid gap-3">
      <h2 className="text-sm font-bold uppercase tracking-wide text-ink-muted">
        {title}
      </h2>
      {children}
    </section>
  );
}
