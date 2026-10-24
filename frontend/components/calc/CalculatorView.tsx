"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BlockMath, InlineMath } from "react-katex";
import "katex/dist/katex.min.css";
import {
    AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, ExternalLink,
    Info, Loader2, Maximize2, RotateCcw, XCircle,
} from "lucide-react";
import { CalcRunError, convertValue, getCatalog, initialValues, isVisible, runCalculator, tidy } from "@/lib/calcApi";
import type { CalcParam, CalculatorDef, InputSource, ParamValue, Provenance, RunResult, UnitChoices } from "@/types/calculator";
import Plot from "@/components/calc/Plot";
import DataTable from "@/components/calc/DataTable";
import { Diagram } from "@/components/diagrams";

const CHECK_ICON: Record<string, { Icon: any; cls: string }> = {
    ok: { Icon: CheckCircle2, cls: "text-emerald-500" },
    warn: { Icon: AlertTriangle, cls: "text-amber-500" },
    fail: { Icon: XCircle, cls: "text-rose-500" },
};

type Values = Record<string, ParamValue>;

// Chips on copilot-filled inputs. Values nobody gave are highlighted: they are the ones to check.
const SOURCE_CHIP: Record<InputSource["source"], { label: string; cls: string; tip: string }> = {
    user: { label: "given", cls: "border-border text-muted-foreground", tip: "Given by you" },
    assumed: { label: "assumed", cls: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300", tip: "Chosen by the copilot" },
    derived: { label: "derived", cls: "border-border text-muted-foreground", tip: "Follows from other inputs" },
    default: { label: "default", cls: "border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-400", tip: "Calculator default: nobody set this" },
};

function SourceChip({ s }: { s: InputSource }) {
    const chip = SOURCE_CHIP[s.source];
    if (!chip) return null;
    return (
        <span title={s.why ? `${chip.tip}: ${s.why}` : chip.tip}
            className={`ml-auto text-[10px] font-medium px-1.5 rounded border ${chip.cls}`}>
            {chip.label}
        </span>
    );
}

function toPayload(params: CalcParam[], values: Values): { payload: Record<string, any>; invalid: string[] } {
    const payload: Record<string, any> = {};
    const invalid: string[] = [];
    for (const p of params) {
        const v = values[p.name];
        if (p.kind === "number") {
            const o = v as { value: number | string; unit: string };
            const n = typeof o?.value === "number" ? o.value : parseFloat(String(o?.value ?? ""));
            if (!isFinite(n)) { if (isVisible(p, values)) invalid.push(p.name); continue; }
            payload[p.name] = { value: n, unit: o.unit };
        } else {
            payload[p.name] = v;
        }
    }
    return { payload, invalid };
}

function NumberField({ p, value, units, onChange, invalid }: {
    p: CalcParam; value: { value: number | string; unit: string }; units: UnitChoices;
    onChange: (v: ParamValue) => void; invalid: boolean;
}) {
    const choices = units[p.dim] || [];
    const changeUnit = (u: string) => {
        const n = typeof value.value === "number" ? value.value : parseFloat(String(value.value));
        onChange({ value: isFinite(n) ? tidy(convertValue(n, value.unit, u, p.dim, units)) : value.value, unit: u });
    };
    return (
        <div className={`flex items-stretch rounded-lg border bg-background overflow-hidden focus-within:ring-2 focus-within:ring-blue-500/40 ${invalid ? "border-rose-500" : "border-border"}`}>
            <input
                inputMode="decimal"
                className="flex-1 min-w-0 bg-transparent px-3 py-1.5 text-sm tabular-nums focus:outline-none"
                value={String(value.value)}
                onChange={(e) => onChange({ value: e.target.value, unit: value.unit })}
                aria-label={p.label}
            />
            {choices.length > 1 ? (
                <select
                    value={value.unit}
                    onChange={(e) => changeUnit(e.target.value)}
                    className="bg-transparent text-muted-foreground text-xs pl-1 pr-2 focus:outline-none cursor-pointer"
                    aria-label={`${p.label} unit`}
                >
                    {choices.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
            ) : choices[0]?.label && choices[0].label !== "–" ? (
                <span className="text-muted-foreground text-xs pr-3 flex items-center">{choices[0].label}</span>
            ) : null}
        </div>
    );
}

function ParamRow({ p, values, units, setValue, invalid, source }: {
    p: CalcParam; values: Values; units: UnitChoices; setValue: (n: string, v: ParamValue) => void; invalid: boolean;
    source?: InputSource;
}) {
    const v = values[p.name];
    return (
        <label className="block">
            <span className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                {p.label}
                {p.help && <span title={p.help} className="cursor-help"><Info size={11} className="opacity-70" /></span>}
                {source && <SourceChip s={source} />}
            </span>
            {p.kind === "number" && (
                <NumberField p={p} value={v as any} units={units} invalid={invalid} onChange={(nv) => setValue(p.name, nv)} />
            )}
            {p.kind === "select" && (
                <select
                    value={String(v)}
                    onChange={(e) => {
                        const opt = p.options?.find((o) => String(o.value) === e.target.value);
                        setValue(p.name, (opt?.value ?? e.target.value) as any);
                    }}
                    className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                >
                    {p.options?.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.label}</option>)}
                </select>
            )}
            {p.kind === "bool" && (
                <button
                    type="button"
                    onClick={() => setValue(p.name, !v)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${v ? "bg-blue-600" : "bg-muted"}`}
                    aria-pressed={Boolean(v)}
                >
                    <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${v ? "translate-x-6" : "translate-x-1"}`} />
                </button>
            )}
            {p.kind === "text" && (
                <input value={String(v ?? "")} onChange={(e) => setValue(p.name, e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40" />
            )}
        </label>
    );
}

/** A quiet, closed-by-default row: label, optional count, chevron. */
function Disclosure({ title, count, defaultOpen = false, children }: {
    title: string; count?: number | string; defaultOpen?: boolean; children: React.ReactNode;
}) {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div className="border-t border-border/70">
            <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
                className="w-full flex items-center gap-2 py-2.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <span className={open ? "text-foreground" : ""}>{title}</span>
                {count !== undefined && <span className="text-xs text-muted-foreground/70 tabular-nums">{count}</span>}
            </button>
            {open && <div className="pb-4 pl-[22px]">{children}</div>}
        </div>
    );
}

/** "Passes all 4 checks", "Fails 1 of 4 checks": the answer in words. */
function verdictText(checks: RunResult["checks"]): string | null {
    if (!checks.length) return null;
    const n = checks.length;
    const fail = checks.filter((c) => c.status === "fail").length;
    const warn = checks.filter((c) => c.status === "warn").length;
    if (fail) return `Fails ${fail} of ${n} check${n > 1 ? "s" : ""}`;
    if (warn) return `Passes, with ${warn} warning${warn > 1 ? "s" : ""}`;
    return n === 1 ? "Passes the check" : `Passes all ${n} checks`;
}

export default function CalculatorView({
    calculatorId, initial, compact = false, provenance, example, provisional, editedNames, onEdit,
}: {
    calculatorId: string; initial?: Record<string, any>; compact?: boolean;
    provenance?: Provenance; example?: boolean; provisional?: string[];
    /** Inputs the user already changed in this card (restored from the session). */
    editedNames?: string[];
    /** Called with the full input payload after each successful run the user caused. */
    onEdit?: (inputs: Record<string, any>) => void;
}) {
    const [def, setDef] = useState<CalculatorDef | null>(null);
    // Inputs changed in the card are the user's own; a preset or reset replaces every input.
    const [edited, setEdited] = useState<Set<string>>(() => new Set(editedNames ?? []));
    const userChanged = useRef(false);   // the initial run is the copilot's, not an edit
    const onEditRef = useRef(onEdit);
    onEditRef.current = onEdit;
    const [detached, setDetached] = useState(false);
    const [units, setUnits] = useState<UnitChoices>({});
    const [values, setValues] = useState<Values>({});
    const [result, setResult] = useState<RunResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [running, setRunning] = useState(false);
    const [showAll, setShowAll] = useState(false);
    const abortRef = useRef<AbortController | null>(null);

    useEffect(() => {
        let alive = true;
        getCatalog()
            .then((cat) => {
                if (!alive) return;
                const d = cat.calculators.find((c) => c.id === calculatorId);
                if (!d) { setLoadError(`Calculator "${calculatorId}" not found.`); return; }
                setDef(d);
                setUnits(cat.unit_choices);
                setValues(initialValues(d.params, initial || {}));
            })
            .catch(() => alive && setLoadError("Could not reach the calculation server. Is the backend running?"));
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [calculatorId]);

    const { payload, invalid } = useMemo(
        () => (def ? toPayload(def.params, values) : { payload: {}, invalid: [] as string[] }),
        [def, values],
    );

    useEffect(() => {
        if (!def || invalid.length) return;
        const t = setTimeout(async () => {
            abortRef.current?.abort();
            const ctrl = new AbortController();
            abortRef.current = ctrl;
            setRunning(true);
            try {
                const r = await runCalculator(def.id, payload, ctrl.signal);
                setResult(r);
                if (userChanged.current) onEditRef.current?.(payload);
                setError(null);
            } catch (e: any) {
                if (e?.name === "AbortError") return;
                setError(e instanceof CalcRunError ? e.message : "Calculation server unavailable.");
            } finally {
                if (abortRef.current === ctrl) setRunning(false);
            }
        }, 300);
        return () => clearTimeout(t);
    }, [def, payload, invalid.length]);

    const setValue = useCallback((name: string, v: ParamValue) => {
        setValues((prev) => ({ ...prev, [name]: v }));
        setEdited((prev) => (prev.has(name) ? prev : new Set(prev).add(name)));
        userChanged.current = true;
    }, []);
    const replaceAll = (next: Values) => { setValues(next); setDetached(true); userChanged.current = true; };
    const sourceOf = (name: string): InputSource | undefined => {
        if (!provenance || detached) return undefined;
        return edited.has(name) ? { source: "user", why: "changed in the card" } : provenance[name];
    };

    if (loadError) {
        return <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-500">{loadError}</div>;
    }
    if (!def) {
        return <div className="py-6 text-sm text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Loading calculator…</div>;
    }

    // Key inputs are the ones that decide the result (the calculator's governing inputs and the
    // size being checked); everything else sits under "All inputs". An invalid field is never hidden.
    const visible = def.params.filter((p) => isVisible(p, values));
    const governing = new Set([...(def.governing ?? []), ...(def.trial ?? [])]);
    let key = visible.filter((p) => governing.has(p.name));
    if (!key.length) key = visible.filter((p) => !p.advanced).slice(0, 4);
    const keyNames = new Set(key.map((p) => p.name));
    const rest = visible.filter((p) => !keyNames.has(p.name));
    const groups: { name: string; params: CalcParam[] }[] = [];
    for (const p of rest.filter((q) => !q.advanced)) {
        const g = p.group || "Inputs";
        let grp = groups.find((x) => x.name === g);
        if (!grp) { grp = { name: g, params: [] }; groups.push(grp); }
        grp.params.push(p);
    }
    const restAdvanced = rest.filter((p) => p.advanced);
    if (restAdvanced.length) groups.push({ name: "Advanced", params: restAdvanced });
    const allOpen = showAll || rest.some((p) => invalid.includes(p.name));

    const primary = result?.outputs.filter((o) => o.primary) ?? [];
    const secondary = result?.outputs.filter((o) => !o.primary) ?? [];
    const verdict = result ? verdictText(result.checks) : null;
    const status = result?.verdict ?? "none";
    // Selection tables (rows with a pass/fail status) are part of the answer; the rest are detail.
    const answerTables = result?.tables.filter((t) => t.rows.some((r) => r._status)) ?? [];
    const detailTables = result?.tables.filter((t) => !answerTables.includes(t)) ?? [];

    const plotGroups: { key: string; series: RunResult["series"] }[] = [];
    for (const s of result?.series ?? []) {
        const k = s.group || s.id;
        const g = plotGroups.find((x) => x.key === k);
        if (g) g.series.push(s); else plotGroups.push({ key: k, series: [s] });
    }

    const field = (p: CalcParam) => (
        <ParamRow key={p.name} p={p} values={values} units={units} setValue={setValue}
            invalid={invalid.includes(p.name)} source={sourceOf(p.name)} />
    );

    const inputs = (
        <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">{key.map(field)}</div>
            {def.presets.length > 0 && (
                <p className="text-xs text-muted-foreground leading-relaxed">
                    Try{" "}
                    {def.presets.map((pr, i) => (
                        <span key={pr.label}>
                            {i > 0 && <span className="mx-1 text-muted-foreground/50">·</span>}
                            <button type="button" onClick={() => replaceAll(initialValues(def.params, pr.values))}
                                className="text-foreground/80 underline decoration-border underline-offset-2 hover:text-blue-500 hover:decoration-blue-500/50">
                                {pr.label}
                            </button>
                        </span>
                    ))}
                </p>
            )}
            {rest.length > 0 && (
                <div>
                    <button type="button" onClick={() => setShowAll(!allOpen)} aria-expanded={allOpen}
                        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
                        {allOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        All inputs <span className="text-xs text-muted-foreground/70 tabular-nums">{rest.length}</span>
                    </button>
                    {allOpen && (
                        <div className="mt-3 space-y-5">
                            {groups.map((g) => (
                                <div key={g.name}>
                                    <div className="text-xs font-medium text-foreground/80 mb-2">{g.name}</div>
                                    <div className="grid gap-3 sm:grid-cols-2">{g.params.map(field)}</div>
                                </div>
                            ))}
                            <button type="button" onClick={() => replaceAll(initialValues(def.params))}
                                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                                <RotateCcw size={11} />Reset to defaults
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );

    // Example and provisional runs say so before any number is read; editing the card clears it.
    const labelOf = (n: string) => def.params.find((p) => p.name === n)?.label ?? n;
    const stillDefault = (provisional ?? []).filter((n) => !edited.has(n));
    const basis = detached ? null
        : example && edited.size === 0 ? "Example values, not your design. Enter your own to check it."
        : stillDefault.length ? `Provisional: defaults used for ${stillDefault.map(labelOf).join(", ")}.`
        : null;

    const tone = status === "fail" ? "text-rose-600 dark:text-rose-400"
        : status === "warn" ? "text-amber-600 dark:text-amber-400"
        : "text-emerald-600 dark:text-emerald-400";
    const VerdictIcon = status === "fail" ? XCircle : status === "warn" ? AlertTriangle : CheckCircle2;

    const answer = (
        <div className={`space-y-4 transition-opacity duration-200 ${running ? "opacity-60" : ""}`}>
            {error && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-sm text-rose-500 flex items-start gap-2">
                    <XCircle size={15} className="mt-0.5 shrink-0" />{error}
                </div>
            )}
            {verdict && (
                <div className={`flex items-center gap-2 text-base font-semibold ${tone}`}>
                    <VerdictIcon size={18} className="shrink-0" />{verdict}
                </div>
            )}
            {basis && (
                <p className="text-xs text-amber-700 dark:text-amber-300 flex items-start gap-1.5">
                    <Info size={13} className="mt-px shrink-0" />{basis}
                </p>
            )}
            {primary.length > 0 && (
                <dl className="grid gap-x-8 gap-y-3 grid-cols-[repeat(auto-fit,minmax(9rem,1fr))]">
                    {primary.map((o) => {
                        // Text results (designations, fit types) read better smaller.
                        const isText = o.value === null && !/^[-+]?[\d.∞–]/.test(o.display);
                        return (
                            <div key={o.name} className="min-w-0">
                                <dt className="text-xs text-muted-foreground truncate" title={o.label}>{o.label}</dt>
                                <dd className="mt-0.5 flex items-baseline gap-1">
                                    <span className={`font-semibold text-foreground tabular-nums ${isText ? "text-base" : "text-2xl tracking-tight"}`}>{o.display}</span>
                                    {o.value !== null && <span className="text-sm text-muted-foreground">{o.unit_label}</span>}
                                </dd>
                            </div>
                        );
                    })}
                </dl>
            )}
            {result && result.checks.length > 0 && (
                <ul className="space-y-1">
                    {result.checks.map((c, i) => {
                        const { Icon, cls } = CHECK_ICON[c.status];
                        return (
                            <li key={i} className="flex items-start gap-2 text-sm">
                                <Icon size={14} className={`${cls} mt-[3px] shrink-0`} />
                                <span><span className="text-foreground">{c.label}</span> <span className="text-muted-foreground">{c.message}</span></span>
                            </li>
                        );
                    })}
                </ul>
            )}
            {answerTables.map((t, i) => <DataTable key={i} table={t} maxRows={compact ? 5 : 8} />)}
            {result && result.links.length > 0 && (
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {result.links.map((l) => (
                        <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline">
                            {l.label}<ExternalLink size={12} />
                        </a>
                    ))}
                </div>
            )}
        </div>
    );

    const diagram = def.diagram && result?.diagram ? (
        <div className="mx-auto max-w-2xl">
            <Diagram id={def.diagram} params={result.diagram.params} inputs={values} />
        </div>
    ) : null;

    const details = result && (
        <div>
            {secondary.length > 0 && (
                <Disclosure title="All results" count={secondary.length}>
                    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
                        {secondary.map((o) => (
                            <div key={o.name} className="flex justify-between gap-3 text-sm py-1">
                                <dt className="text-muted-foreground truncate" title={o.help || o.label}>{o.label}</dt>
                                <dd className="tabular-nums text-foreground whitespace-nowrap">{o.display} <span className="text-muted-foreground text-xs">{o.value !== null ? o.unit_label : ""}</span></dd>
                            </div>
                        ))}
                    </dl>
                </Disclosure>
            )}
            {plotGroups.length > 0 && (
                <Disclosure title="Charts" count={plotGroups.length}>
                    <div className="space-y-6">{plotGroups.map((g) => <Plot key={g.key} series={g.series} />)}</div>
                </Disclosure>
            )}
            {detailTables.length > 0 && (
                <Disclosure title="Tables" count={detailTables.length}>
                    <div className="space-y-4">{detailTables.map((t, i) => <DataTable key={i} table={t} maxRows={12} />)}</div>
                </Disclosure>
            )}
            {result.notes.length > 0 && (
                <Disclosure title="Notes" count={result.notes.length}>
                    <ul className="space-y-1.5 max-w-prose">
                        {result.notes.map((n, i) => <li key={i} className="text-sm text-muted-foreground">{n}</li>)}
                    </ul>
                </Disclosure>
            )}
            {result.steps.length > 0 && (
                <Disclosure title="Worked solution" count={`${result.steps.length} steps`}>
                    <ol className="space-y-1.5">
                        {result.steps.map((s, i) => (
                            <li key={i} className="grid grid-cols-[1fr_auto] gap-3 items-baseline text-sm">
                                <div className="min-w-0">
                                    <span className="text-muted-foreground text-xs mr-2">{s.label}</span>
                                    <span className="overflow-x-auto"><InlineMath math={s.latex} /></span>
                                </div>
                                {s.display !== undefined && (
                                    <span className="tabular-nums text-foreground whitespace-nowrap">= {s.display} <span className="text-muted-foreground text-xs">{s.unit_label}</span></span>
                                )}
                            </li>
                        ))}
                    </ol>
                </Disclosure>
            )}
            {(def.formulas.length > 0 || def.references.length > 0) && (
                <Disclosure title="Theory and references">
                    {def.description && <p className="text-sm text-muted-foreground mb-3 leading-relaxed max-w-prose">{def.description}</p>}
                    <div className="space-y-1">
                        {def.formulas.map((f, i) => <div key={i} className="overflow-x-auto"><BlockMath math={f} /></div>)}
                    </div>
                    {def.references.length > 0 && (
                        <ul className="mt-3 space-y-0.5">
                            {def.references.map((r) => <li key={r} className="text-xs text-muted-foreground">{r}</li>)}
                        </ul>
                    )}
                </Disclosure>
            )}
        </div>
    );

    if (compact) {
        // In a chat reply: the answer first; inputs, drawing and details one click away.
        return (
            <div className="rounded-xl border border-border bg-card px-4 pt-3 w-full">
                <div className="flex items-center justify-between gap-3 mb-3">
                    <h3 className="text-sm font-medium text-foreground truncate">{def.title}</h3>
                    <div className="flex items-center gap-1 shrink-0">
                        {running && <Loader2 size={13} className="animate-spin text-muted-foreground" />}
                        <Link href={`/calculators/view?id=${def.id}`} title="Open full calculator"
                            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted">
                            <Maximize2 size={13} />
                        </Link>
                    </div>
                </div>
                <div className="pb-4">{answer}</div>
                <Disclosure title="Inputs" count={key.length + rest.length} defaultOpen={Boolean(basis)}>{inputs}</Disclosure>
                {diagram && <Disclosure title="Diagram">{diagram}</Disclosure>}
                {details}
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <header className="max-w-3xl">
                <h1 className="text-2xl font-semibold text-foreground tracking-tight text-balance">{def.title}</h1>
                <p className="text-sm text-muted-foreground mt-1.5 max-w-prose">{def.summary}</p>
            </header>
            <div className="grid gap-10 xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
                <section aria-label="Inputs" className="xl:sticky xl:top-8 self-start max-w-2xl">{inputs}</section>
                <div className="min-w-0 space-y-8">
                    <section aria-label="Result">{answer}</section>
                    {diagram && <section aria-label="Diagram">{diagram}</section>}
                    {details}
                </div>
            </div>
        </div>
    );
}
