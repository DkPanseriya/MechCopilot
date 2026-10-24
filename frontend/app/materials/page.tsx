"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { API_BASE } from "@/lib/api";

interface Material {
    id: string;
    name: string;
    category: string;
    sub_category: string;
    density: number;
    yield_strength: number;
    ultimate_strength: number;
    elastic_modulus: number;
    description: string;
}

type SortKey = "name" | "yield_strength" | "ultimate_strength" | "elastic_modulus" | "density";

const SORTS: { key: SortKey; label: string }[] = [
    { key: "name", label: "Name" },
    { key: "yield_strength", label: "Yield" },
    { key: "ultimate_strength", label: "Tensile" },
    { key: "elastic_modulus", label: "Stiffness" },
    { key: "density", label: "Density" },
];

// One colour per material family, so a family reads at a glance (the swatch and its bars).
const FAMILY: Record<string, string> = {
    "Structural Steel": "oklch(0.62 0.05 250)",
    "Carbon Steel": "oklch(0.6 0.045 245)",
    "Alloy Steel": "oklch(0.58 0.08 265)",
    "Stainless Steel": "oklch(0.8 0.02 250)",
    "Aluminium Alloy": "oklch(0.76 0.08 225)",
    "Titanium Alloy": "oklch(0.7 0.09 300)",
    "Cast Iron": "oklch(0.55 0.02 60)",
    "Copper Alloy": "oklch(0.72 0.12 65)",
};
const familyColour = (m: Material) => FAMILY[m.sub_category] ?? "oklch(0.72 0.12 160)"; // plastics

const BARS: { key: "ultimate_strength" | "elastic_modulus" | "density"; label: string; format: (m: Material) => string }[] = [
    { key: "ultimate_strength", label: "Tensile", format: (m) => `${(m.ultimate_strength / 1e6).toFixed(0)} MPa` },
    { key: "elastic_modulus", label: "Stiffness", format: (m) => `${(m.elastic_modulus / 1e9).toFixed(0)} GPa` },
    { key: "density", label: "Density", format: (m) => `${(m.density / 1000).toFixed(2)} g/cm³` },
];

export default function MaterialsPage() {
    const [materials, setMaterials] = useState<Material[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [q, setQ] = useState("");
    const [category, setCategory] = useState("All");
    const [sort, setSort] = useState<SortKey>("name");

    useEffect(() => {
        fetch(`${API_BASE}/api/materials/`)
            .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
            .then(setMaterials)
            .catch(() => setError(true))
            .finally(() => setLoading(false));
    }, []);

    const categories = useMemo(() => ["All", ...new Set(materials.map((m) => m.category))], [materials]);
    // Bars compare each material with the strongest / stiffest / densest in the library.
    const max = useMemo(() => Object.fromEntries(
        BARS.map((b) => [b.key, Math.max(1, ...materials.map((m) => m[b.key]))])) as Record<string, number>, [materials]);

    const tiles = useMemo(() => {
        const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
        const list = materials.filter((m) => {
            const hay = `${m.name} ${m.sub_category} ${m.description}`.toLowerCase();
            return (category === "All" || m.category === category) && terms.every((t) => hay.includes(t));
        });
        return list.sort((a, b) => (sort === "name" ? a.name.localeCompare(b.name) : b[sort] - a[sort]));
    }, [materials, q, category, sort]);

    return (
        <div className="max-w-5xl mx-auto px-6 py-10">
            <h1 className="text-2xl font-semibold text-foreground tracking-tight">Materials</h1>
            <p className="text-sm text-muted-foreground mt-1.5">Typical properties of common engineering materials.</p>

            <div className="flex flex-wrap items-center gap-3 mt-6 mb-6">
                <div className="relative flex-1 min-w-[14rem] max-w-md">
                    <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search: S355, aluminium, PEEK…"
                        aria-label="Search materials"
                        className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/40" />
                </div>
                <div className="flex rounded-lg border border-border p-0.5" role="radiogroup" aria-label="Category">
                    {categories.map((c) => (
                        <button key={c} type="button" role="radio" aria-checked={category === c} onClick={() => setCategory(c)}
                            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${category === c ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                            {c}
                        </button>
                    ))}
                </div>
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    Sort
                    <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}
                        className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/40">
                        {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                    </select>
                </label>
            </div>

            {loading && <div className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Loading…</div>}
            {error && <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-500">Could not load the materials. Is the backend running?</div>}
            {!loading && !error && tiles.length === 0 && <p className="text-sm text-muted-foreground">No material matches these filters.</p>}

            <ul className="grid gap-3 grid-cols-[repeat(auto-fill,minmax(13rem,1fr))]">
                {tiles.map((m) => {
                    const colour = familyColour(m);
                    return (
                        <li key={m.id} title={m.description}
                            className="rounded-xl border border-border/70 p-4 transition-colors duration-150 hover:border-border hover:bg-muted/30">
                            <div className="flex items-start gap-3">
                                {/* swatch with a soft sheen, like a polished sample */}
                                <span className="h-9 w-9 shrink-0 rounded-lg ring-1 ring-inset ring-white/10"
                                    style={{ background: `linear-gradient(135deg, color-mix(in oklch, ${colour} 70%, white) 0%, ${colour} 55%, color-mix(in oklch, ${colour} 80%, black) 100%)` }} />
                                <div className="min-w-0">
                                    <div className="text-sm text-foreground leading-snug">{m.name}</div>
                                    <div className="text-xs text-muted-foreground">{m.sub_category}</div>
                                </div>
                            </div>
                            <div className="mt-4 flex items-baseline gap-1.5">
                                <span className="text-2xl font-semibold tracking-tight tabular-nums text-foreground">{(m.yield_strength / 1e6).toFixed(0)}</span>
                                <span className="text-xs text-muted-foreground">MPa yield</span>
                            </div>
                            <dl className="mt-3 space-y-1.5">
                                {BARS.map((b) => (
                                    <div key={b.key} className="grid grid-cols-[3.75rem_1fr_4.5rem] items-center gap-2 text-xs">
                                        <dt className="text-muted-foreground">{b.label}</dt>
                                        <dd className="h-1.5 rounded-full bg-muted overflow-hidden">
                                            <span className="block h-full rounded-full"
                                                style={{ width: `${Math.max(3, (100 * m[b.key]) / max[b.key])}%`, background: colour }} />
                                        </dd>
                                        <dd className="text-right tabular-nums text-muted-foreground">{b.format(m)}</dd>
                                    </div>
                                ))}
                            </dl>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}
