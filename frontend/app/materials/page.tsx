"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Loader2, Search } from "lucide-react";
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

const COLUMNS: { key: SortKey; label: string; unit?: string; format: (m: Material) => string }[] = [
    { key: "yield_strength", label: "Yield", unit: "MPa", format: (m) => (m.yield_strength / 1e6).toFixed(0) },
    { key: "ultimate_strength", label: "Tensile", unit: "MPa", format: (m) => (m.ultimate_strength / 1e6).toFixed(0) },
    { key: "elastic_modulus", label: "E", unit: "GPa", format: (m) => (m.elastic_modulus / 1e9).toFixed(0) },
    { key: "density", label: "Density", unit: "kg/m³", format: (m) => new Intl.NumberFormat().format(m.density) },
];

function SortIcon({ sort, k }: { sort: { key: SortKey; asc: boolean }; k: SortKey }) {
    if (sort.key !== k) return null;
    return sort.asc ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
}

export default function MaterialsPage() {
    const [materials, setMaterials] = useState<Material[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [q, setQ] = useState("");
    const [category, setCategory] = useState("All");
    const [sort, setSort] = useState<{ key: SortKey; asc: boolean }>({ key: "name", asc: true });

    useEffect(() => {
        fetch(`${API_BASE}/api/materials/`)
            .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
            .then(setMaterials)
            .catch(() => setError(true))
            .finally(() => setLoading(false));
    }, []);

    const categories = useMemo(() => ["All", ...new Set(materials.map((m) => m.category))], [materials]);

    const rows = useMemo(() => {
        const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
        const list = materials.filter((m) => {
            const hay = `${m.name} ${m.sub_category} ${m.description}`.toLowerCase();
            return (category === "All" || m.category === category) && terms.every((t) => hay.includes(t));
        });
        const dir = sort.asc ? 1 : -1;
        return list.sort((a, b) => (sort.key === "name"
            ? a.name.localeCompare(b.name) : (a[sort.key] - b[sort.key])) * dir);
    }, [materials, q, category, sort]);

    const sortBy = (key: SortKey) =>
        setSort((s) => (s.key === key ? { key, asc: !s.asc } : { key, asc: key === "name" }));

    return (
        <div className="max-w-4xl mx-auto px-6 py-10">
            <h1 className="text-2xl font-semibold text-foreground tracking-tight">Materials</h1>
            <p className="text-sm text-muted-foreground mt-1.5">
                Typical properties of common engineering materials. Click a column to sort.
            </p>

            <div className="flex flex-wrap items-center gap-3 mt-6 mb-6">
                <div className="relative flex-1 min-w-[14rem]">
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
            </div>

            {loading && <div className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Loading…</div>}
            {error && <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-500">Could not load the materials. Is the backend running?</div>}

            {!loading && !error && (
                rows.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No material matches these filters.</p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm tabular-nums">
                            <thead className="text-xs text-muted-foreground">
                                <tr>
                                    <th className="text-left font-normal py-2 pr-4">
                                        <button type="button" onClick={() => sortBy("name")} className="inline-flex items-center gap-1 hover:text-foreground">
                                            Material <SortIcon sort={sort} k="name" />
                                        </button>
                                    </th>
                                    {COLUMNS.map((c) => (
                                        <th key={c.key} className="text-right font-normal py-2 pl-4 whitespace-nowrap">
                                            <button type="button" onClick={() => sortBy(c.key)} className="inline-flex items-center gap-1 hover:text-foreground">
                                                <SortIcon sort={sort} k={c.key} />{c.label} <span className="text-muted-foreground/70">{c.unit}</span>
                                            </button>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((m) => (
                                    <tr key={m.id} className="border-t border-border/60" title={m.description}>
                                        <td className="py-2 pr-4">
                                            <div className="text-foreground">{m.name}</div>
                                            <div className="text-xs text-muted-foreground">{m.sub_category}</div>
                                        </td>
                                        {COLUMNS.map((c) => (
                                            <td key={c.key} className="py-2 pl-4 text-right text-foreground">{c.format(m)}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )
            )}
        </div>
    );
}
