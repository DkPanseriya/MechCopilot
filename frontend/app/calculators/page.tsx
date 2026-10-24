"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, ArrowRight, Loader2 } from "lucide-react";
import { getCatalog } from "@/lib/calcApi";
import type { CatalogResponse } from "@/types/calculator";

export default function CalculatorLibrary() {
    const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [q, setQ] = useState("");

    useEffect(() => {
        getCatalog().then(setCatalog).catch(() => setError("Could not reach the calculation server. Start the backend on port 8001."));
    }, []);

    const filtered = useMemo(() => {
        if (!catalog) return [];
        const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
        return catalog.calculators.filter((c) => {
            const hay = `${c.title} ${c.summary} ${c.category} ${c.keywords.join(" ")}`.toLowerCase();
            return terms.every((t) => hay.includes(t));
        });
    }, [catalog, q]);

    const byCategory = useMemo(() => {
        const m = new Map<string, typeof filtered>();
        for (const c of filtered) {
            if (!m.has(c.category)) m.set(c.category, []);
            m.get(c.category)!.push(c);
        }
        return [...m.entries()];
    }, [filtered]);

    return (
        <div className="max-w-6xl mx-auto px-6 py-10">
            <div className="mb-8">
                <h1 className="text-3xl font-semibold text-foreground">Calculator library</h1>
                <p className="text-muted-foreground mt-2 max-w-2xl">
                    Every calculator shows its diagram, worked solution and the standard it follows.
                    Open one directly, or describe your problem in a design session and the copilot will pick and fill them for you.
                </p>
            </div>

            <div className="relative mb-8 max-w-xl">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search: bolt preload, bearing life, beam deflection, fit…"
                    className="w-full rounded-xl border border-border bg-background pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                    autoFocus
                />
            </div>

            {error && <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-500">{error}</div>}
            {!catalog && !error && <div className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Loading…</div>}
            {catalog && filtered.length === 0 && <p className="text-sm text-muted-foreground">No calculator matches “{q}”.</p>}

            <div className="space-y-10">
                {byCategory.map(([cat, calcs]) => (
                    <section key={cat}>
                        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                            {cat} <span className="opacity-60">· {calcs.length}</span>
                        </h2>
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {calcs.map((c) => (
                                <Link key={c.id} href={`/calculators/view?id=${c.id}`}
                                    className="group rounded-xl border border-border bg-card p-4 hover:border-blue-500/50 transition-colors">
                                    <div className="flex items-start justify-between gap-2">
                                        <h3 className="font-medium text-foreground leading-snug">{c.title}</h3>
                                        <ArrowRight size={15} className="text-muted-foreground group-hover:text-blue-500 shrink-0 mt-0.5 transition-colors" />
                                    </div>
                                    <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">{c.summary}</p>
                                </Link>
                            ))}
                        </div>
                    </section>
                ))}
            </div>
        </div>
    );
}
