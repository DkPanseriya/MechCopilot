"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BlockMath, InlineMath } from "react-katex";
import "katex/dist/katex.min.css";
import {
    AlertTriangle, BookOpen, CheckCircle2, ChevronDown, ChevronRight, ExternalLink,
    Info, Loader2, Maximize2, RotateCcw, XCircle,
} from "lucide-react";
import { CalcRunError, convertValue, getCatalog, initialValues, isVisible, runCalculator, tidy } from "@/lib/calcApi";
import type { CalcParam, CalculatorDef, InputSource, ParamValue, Provenance, RunResult, UnitChoices } from "@/types/calculator";
import Plot from "@/components/calc/Plot";
import DataTable from "@/components/calc/DataTable";
import { Diagram } from "@/components/diagrams";

const VERDICT: Record<string, { label: string; cls: string; Icon: any }> = {
    ok: { label: "Passes", cls: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30", Icon: CheckCircle2 },
    warn: { label: "Check warnings", cls: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30", Icon: AlertTriangle },
    fail: { label: "Fails", cls: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30", Icon: XCircle },
};

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
            className={`ml-auto text-[9px] font-medium uppercase tracking-wide px-1.5 py-px rounded border ${chip.cls}`}>
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
                className="flex-1 min-w-0 bg-transparent px-3 py-2 text-sm font-mono tabular-nums focus:outline-none"
                value={String(value.value)}
                onChange={(e) => onChange({ value: e.target.value, unit: value.unit })}
                aria-label={p.label}
            />
            {choices.length > 1 ? (
                <select
                    value={value.unit}
                    onChange={(e) => changeUnit(e.target.value)}
                    className="bg-muted/60 text-muted-foreground text-xs px-2 border-l border-border focus:outline-none cursor-pointer"
                    aria-label={`${p.label} unit`}
                >
                    {choices.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
            ) : choices[0]?.label && choices[0].label !== "–" ? (
                <span className="bg-muted/60 text-muted-foreground text-xs px-2 flex items-center border-l border-border">{choices[0].label}</span>
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
            <span className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground mb-1">
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
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40"
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

function Section({ title, children, defaultOpen = true, icon }: { title: string; children: React.ReactNode; defaultOpen?: boolean; icon?: React.ReactNode }) {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div className="border-t border-border pt-3">
            <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 text-xs font-semibold text-foreground mb-2 hover:text-blue-500">
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                {icon}{title}
            </button>
            {open && children}
        </div>
    );
}

export default function CalculatorView({ calculatorId, initial, compact = false, provenance, example, provisional }: {
    calculatorId: string; initial?: Record<string, any>; compact?: boolean;
    provenance?: Provenance; example?: boolean; provisional?: string[];
}) {
    const [def, setDef] = useState<CalculatorDef | null>(null);
    // Inputs changed in the card are the user's own; a preset or reset replaces every input.
    const [edited, setEdited] = useState<Set<string>>(new Set());
    const [detached, setDetached] = useState(false);
    const [units, setUnits] = useState<UnitChoices>({});
    const [values, setValues] = useState<Values>({});
    const [result, setResult] = useState<RunResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [running, setRunning] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
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
            .catch(() => alive && setLoadError("Could not reach the calculation server. Is the backend running on port 8001?"));
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
    }, []);
    const replaceAll = (next: Values) => { setValues(next); setDetached(true); };
    const sourceOf = (name: string): InputSource | undefined => {
        if (!provenance || detached) return undefined;
        return edited.has(name) ? { source: "user", why: "changed in the card" } : provenance[name];
    };

    if (loadError) {
        return <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-500">{loadError}</div>;
    }
    if (!def) {
        return <div className="rounded-xl border border-border p-6 text-sm text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Loading calculator…</div>;
    }

    // Group visible params, preserving definition order.
    const visible = def.params.filter((p) => isVisible(p, values));
    const basic = visible.filter((p) => !p.advanced);
    const advanced = visible.filter((p) => p.advanced);
    const groups: { name: string; params: CalcParam[] }[] = [];
    for (const p of basic) {
        const g = p.group || "Inputs";
        let grp = groups.find((x) => x.name === g);
        if (!grp) { grp = { name: g, params: [] }; groups.push(grp); }
        grp.params.push(p);
    }

    const primary = result?.outputs.filter((o) => o.primary) ?? [];
    const secondary = result?.outputs.filter((o) => !o.primary) ?? [];
    const verdict = result && VERDICT[result.verdict];

    const plotGroups: { key: string; series: RunResult["series"] }[] = [];
    for (const s of result?.series ?? []) {
        const key = s.group || s.id;
        const g = plotGroups.find((x) => x.key === key);
        if (g) g.series.push(s); else plotGroups.push({ key, series: [s] });
    }

    const inputs = (
        <div className="space-y-4">
            {def.presets.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {def.presets.map((pr) => (
                        <button key={pr.label} onClick={() => replaceAll(initialValues(def.params, pr.values))}
                            className="text-[11px] px-2.5 py-1 rounded-full border border-border hover:border-blue-500/50 hover:text-blue-500 text-muted-foreground">
                            {pr.label}
                        </button>
                    ))}
                </div>
            )}
            {groups.map((g) => (
                <div key={g.name}>
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80 mb-2">{g.name}</div>
                    <div className={`grid gap-3 sm:grid-cols-2 ${compact ? "" : "xl:grid-cols-1"}`}>
                        {g.params.map((p) => (
                            <ParamRow key={p.name} p={p} values={values} units={units} setValue={setValue} invalid={invalid.includes(p.name)} source={sourceOf(p.name)} />
                        ))}
                    </div>
                </div>
            ))}
            {advanced.length > 0 && (
                <div>
                    <button onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground">
                        {showAdvanced ? <ChevronDown size={13} /> : <ChevronRight size={13} />}Advanced ({advanced.length})
                    </button>
                    {showAdvanced && (
                        <div className={`grid gap-3 mt-2 sm:grid-cols-2 ${compact ? "" : "xl:grid-cols-1"}`}>
                            {advanced.map((p) => (
                                <ParamRow key={p.name} p={p} values={values} units={units} setValue={setValue} invalid={invalid.includes(p.name)} source={sourceOf(p.name)} />
                            ))}
                        </div>
                    )}
                </div>
            )}
            <button onClick={() => replaceAll(initialValues(def.params))} className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground">
                <RotateCcw size={11} />Reset to defaults
            </button>
        </div>
    );

    const resultsBlock = (
        <div className="space-y-4">
            {error && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-sm text-rose-500 flex items-start gap-2">
                    <XCircle size={15} className="mt-0.5 shrink-0" />{error}
                </div>
            )}
            {primary.length > 0 && (
                <div className={`grid gap-2 ${primary.length >= 3 ? "grid-cols-2 xl:grid-cols-3" : "grid-cols-2"} ${running ? "opacity-70" : ""} transition-opacity`}>
                    {primary.map((o) => {
                        // Text results (designations, fit types) read better in the UI font.
                        const isText = o.value === null && !/^[-+]?[\d.∞–]/.test(o.display);
                        return (
                            <div key={o.name} className={`rounded-xl border border-border bg-muted/30 px-3 py-2.5 ${isText && o.display.length > 18 ? "col-span-2" : ""}`}>
                                <div className="text-[11px] text-muted-foreground truncate" title={o.label}>{o.label}</div>
                                <div className="flex items-baseline gap-1.5 mt-0.5">
                                    <span className={isText
                                        ? "text-sm font-semibold text-foreground leading-snug"
                                        : "text-xl font-semibold font-mono tabular-nums text-foreground"}>{o.display}</span>
                                    <span className="text-xs text-muted-foreground">{o.value !== null ? o.unit_label : ""}</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
            {result && result.checks.length > 0 && (
                <ul className="space-y-1.5">
                    {result.checks.map((c, i) => {
                        const { Icon, cls } = CHECK_ICON[c.status];
                        return (
                            <li key={i} className="flex items-start gap-2 text-sm">
                                <Icon size={15} className={`${cls} mt-0.5 shrink-0`} />
                                <span><span className="font-medium text-foreground">{c.label}.</span> <span className="text-muted-foreground">{c.message}</span></span>
                            </li>
                        );
                    })}
                </ul>
            )}
            {secondary.length > 0 && (
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1">
                    {secondary.map((o) => (
                        <div key={o.name} className="flex justify-between gap-3 text-sm border-b border-border/60 py-1">
                            <dt className="text-muted-foreground truncate" title={o.help || o.label}>{o.label}</dt>
                            <dd className="font-mono tabular-nums text-foreground whitespace-nowrap">{o.display} <span className="text-muted-foreground text-xs">{o.value !== null ? o.unit_label : ""}</span></dd>
                        </div>
                    ))}
                </dl>
            )}
            {result && result.links.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {result.links.map((l) => (
                        <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white">
                            {l.label}<ExternalLink size={12} />
                        </a>
                    ))}
                </div>
            )}
        </div>
    );

    const diagram = def.diagram && result?.diagram ? (
        <div className="rounded-2xl border border-border bg-muted/20 p-3 sm:p-4">
            <div className={`mx-auto ${compact ? "max-w-2xl" : "max-w-3xl"}`}>
                <Diagram id={def.diagram} params={result.diagram.params} inputs={values} />
            </div>
        </div>
    ) : null;

    const extras = result && (
        <div className="space-y-4">
            {plotGroups.map((g) => (
                <div key={g.key} className="rounded-xl border border-border p-3"><Plot series={g.series} /></div>
            ))}
            {result.tables.map((t, i) => <DataTable key={i} table={t} maxRows={compact ? 6 : 12} />)}
            {result.notes.length > 0 && (
                <ul className="space-y-1">
                    {result.notes.map((n, i) => (
                        <li key={i} className="text-xs text-muted-foreground flex gap-2"><Info size={12} className="mt-0.5 shrink-0" />{n}</li>
                    ))}
                </ul>
            )}
            {result.steps.length > 0 && (
                <Section title="Worked solution" defaultOpen={!compact} icon={<BookOpen size={13} className="mr-0.5" />}>
                    <ol className="space-y-1.5">
                        {result.steps.map((s, i) => (
                            <li key={i} className="grid grid-cols-[1fr_auto] gap-3 items-baseline text-sm">
                                <div className="min-w-0">
                                    <span className="text-muted-foreground text-xs mr-2">{s.label}</span>
                                    <span className="overflow-x-auto"><InlineMath math={s.latex} /></span>
                                </div>
                                {s.display !== undefined && (
                                    <span className="font-mono tabular-nums text-foreground whitespace-nowrap">= {s.display} <span className="text-muted-foreground text-xs">{s.unit_label}</span></span>
                                )}
                            </li>
                        ))}
                    </ol>
                </Section>
            )}
            {(def.formulas.length > 0 || def.references.length > 0) && (
                <Section title="Theory & references" defaultOpen={false}>
                    {def.description && <p className="text-sm text-muted-foreground mb-3 leading-relaxed">{def.description}</p>}
                    <div className="space-y-1">
                        {def.formulas.map((f, i) => <div key={i} className="overflow-x-auto"><BlockMath math={f} /></div>)}
                    </div>
                    {def.references.length > 0 && (
                        <ul className="mt-3 space-y-0.5">
                            {def.references.map((r) => <li key={r} className="text-xs text-muted-foreground">· {r}</li>)}
                        </ul>
                    )}
                </Section>
            )}
        </div>
    );

    const header = (
        <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-blue-500 mb-1">{def.category}</div>
                <h2 className={`${compact ? "text-base" : "text-2xl"} font-semibold text-foreground leading-tight`}>{def.title}</h2>
                <p className="text-sm text-muted-foreground mt-1">{def.summary}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                {running && <Loader2 size={14} className="animate-spin text-muted-foreground" />}
                {verdict && (
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${verdict.cls}`}>
                        <verdict.Icon size={13} />{verdict.label}
                    </span>
                )}
                {compact && (
                    <Link href={`/calculators/view?id=${def.id}`} title="Open full calculator"
                        className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted">
                        <Maximize2 size={14} />
                    </Link>
                )}
            </div>
        </div>
    );

    // Example and provisional runs say so before any number is read; editing the card clears it.
    const labelOf = (n: string) => def.params.find((p) => p.name === n)?.label ?? n;
    const stillDefault = (provisional ?? []).filter((n) => !edited.has(n));
    const basis = detached ? null
        : example && edited.size === 0 ? "Example: these are the calculator's default values, not your design. Enter your own to check it."
        : stillDefault.length ? `Provisional: calculator defaults used for ${stillDefault.map(labelOf).join(", ")}. Enter your values to confirm the result.`
        : null;

    if (compact) {
        return (
            <div className="rounded-2xl border border-border bg-card p-4 space-y-4 w-full">
                {header}
                {basis && (
                    <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                        <Info size={13} className="mt-px shrink-0" />{basis}
                    </div>
                )}
                {diagram}
                {inputs}
                {resultsBlock}
                {extras}
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {header}
            {diagram}
            <div className="grid gap-6 xl:grid-cols-[minmax(300px,340px)_1fr]">
                <aside className="xl:sticky xl:top-6 self-start rounded-2xl border border-border bg-card p-4">{inputs}</aside>
                <div className="space-y-5 min-w-0">
                    <div className="rounded-2xl border border-border bg-card p-4">{resultsBlock}</div>
                    {extras}
                </div>
            </div>
        </div>
    );
}
