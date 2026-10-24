"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, ChevronRight, Loader2 } from "lucide-react";
import { getCatalog } from "@/lib/calcApi";
import type { CatalogResponse } from "@/types/calculator";

export default function CalculatorLibrary() {
    const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [q, setQ] = useState("");

    useEffect(() => {
        getCatalog().then(setCatalog).catch(() => setError("Could not reach the calculation server. Is the backend running?"));
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
        <div className="max-w-3xl mx-auto px-6 py-10">
            <h1 className="text-2xl font-semibold text-foreground tracking-tight">Calculators</h1>
            <p className="text-sm text-muted-foreground mt-1.5">
                Open one directly, or describe your problem in a design session and the copilot fills them in.
            </p>

            <div className="relative mt-6 mb-8">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search: bolt preload, bearing life, beam deflection…"
                    aria-label="Search calculators"
                    className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                    autoFocus
                />
            </div>

            {error && <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-500">{error}</div>}
            {!catalog && !error && <div className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Loading…</div>}
            {catalog && filtered.length === 0 && <p className="text-sm text-muted-foreground">No calculator matches “{q}”.</p>}

            <div className="space-y-8">
                {byCategory.map(([cat, calcs]) => (
                    <section key={cat}>
                        <h2 className="text-sm font-medium text-foreground mb-1">{cat}</h2>
                        <ul className="divide-y divide-border/60">
                            {calcs.map((c) => (
                                <li key={c.id}>
                                    <Link href={`/calculators/view?id=${c.id}`}
                                        className="group flex items-center gap-3 -mx-3 px-3 py-2.5 rounded-lg hover:bg-muted/50 transition-colors">
                                        <div className="min-w-0 flex-1">
                                            <div className="text-sm text-foreground">{c.title}</div>
                                            <div className="text-xs text-muted-foreground truncate mt-0.5">{c.summary}</div>
                                        </div>
                                        <ChevronRight size={15} className="text-muted-foreground/50 group-hover:text-foreground shrink-0 transition-colors" />
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </section>
                ))}
            </div>
        </div>
    );
}
