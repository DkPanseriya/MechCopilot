"use client";

import { useEffect, useState, useCallback } from "react";
import { API_BASE } from "@/lib/api";
import type { SelectorSpec } from "@/types/uiSpec";
import { Table2, AlertCircle } from "lucide-react";

interface SelectorResult {
    service: string;
    basis: string;
    recommended?: string | null;
    columns: string[];
    rows: Record<string, any>[];
}

const LABELS: Record<string, string> = {
    designation: "Desig.", bore_mm: "Bore (mm)", od_mm: "OD (mm)",
    C: "C (N)", C0: "C₀ (N)", L10_Mrev: "L10 (Mrev)", L10h_hours: "L10h (h)",
    static_safety: "s₀", size: "Size", stress_area_mm2: "Aₜ (mm²)",
    proof_load_kN: "Proof (kN)", preload_kN: "Preload (kN)",
    tightening_torque_Nm: "Torque (Nm)", safety_vs_proof: "SF", adequate: "OK",
};

export default function SelectorWidget({ spec }: { spec: SelectorSpec }) {
    const [constraints, setConstraints] = useState<Record<string, any>>(spec.constraints || {});
    const [data, setData] = useState<SelectorResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const run = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/selector/${spec.service}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(constraints),
            });
            const json = await res.json();
            if (json.detail) setError(String(json.detail));
            else setData(json);
        } catch {
            setError("Could not reach the selector service.");
        } finally {
            setLoading(false);
        }
    }, [spec.service, constraints]);

    useEffect(() => { run(); /* initial */ }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const setC = (k: string, v: string) => {
        const num = Number(v);
        setConstraints((p) => ({ ...p, [k]: isNaN(num) || v === "" ? v : num }));
    };

    return (
        <div className="bg-card/95 border border-border rounded-2xl p-6 shadow-xl w-full max-w-2xl my-4">
            <div className="flex items-center gap-2 mb-1 border-b border-border pb-3">
                <Table2 className="text-cyan-500" size={18} />
                <h3 className="text-base font-bold text-foreground">{spec.title}</h3>
            </div>
            {spec.description && <p className="text-muted-foreground text-sm my-3">{spec.description}</p>}

            {/* constraint inputs */}
            <div className="flex flex-wrap gap-3 my-4">
                {Object.entries(constraints).map(([k, v]) => (
                    <div key={k} className="flex flex-col">
                        <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1">{k}</label>
                        <input
                            value={v ?? ""}
                            onChange={(e) => setC(k, e.target.value)}
                            className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm font-mono w-32 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        />
                    </div>
                ))}
                <button onClick={run} disabled={loading}
                    className="self-end bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded-lg text-sm font-semibold disabled:opacity-50">
                    {loading ? "…" : "Update"}
                </button>
            </div>

            {data?.recommended && (
                <div className="mb-3 text-sm bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-300 rounded-lg px-3 py-2">
                    Recommended: <span className="font-bold">{data.recommended}</span>
                </div>
            )}
            {error && <div className="text-red-500 text-sm flex items-center gap-1 py-2"><AlertCircle size={14} />{error}</div>}

            {data && (
                <div className="overflow-x-auto rounded-lg border border-border">
                    <table className="w-full text-xs">
                        <thead className="bg-muted/50 text-muted-foreground">
                            <tr>{data.columns.map((c) => <th key={c} className="px-3 py-2 text-left font-semibold whitespace-nowrap">{LABELS[c] ?? c}</th>)}</tr>
                        </thead>
                        <tbody className="font-mono">
                            {data.rows.map((row, i) => (
                                <tr key={i} className={`border-t border-border ${row.adequate === false ? "opacity-40" : ""} ${(row.designation === data.recommended || row.size === data.recommended) ? "bg-blue-50 dark:bg-blue-900/20" : ""}`}>
                                    {data.columns.map((c) => (
                                        <td key={c} className="px-3 py-1.5 whitespace-nowrap">
                                            {typeof row[c] === "boolean" ? (row[c] ? "✓" : "—") : (row[c] ?? "—")}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
            <p className="text-[10px] text-muted-foreground mt-3 italic">{data?.basis}</p>
        </div>
    );
}
