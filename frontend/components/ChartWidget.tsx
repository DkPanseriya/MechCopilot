"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api";
import type { ChartSpec } from "@/types/uiSpec";
import { LineChart as LineIcon, AlertCircle } from "lucide-react";

interface Point { x: number; y: number; }
interface SweepResult {
    x_label: string; x_unit: string;
    y_label: string; y_unit: string;
    points: Point[];
}

export default function ChartWidget({ spec }: { spec: ChartSpec }) {
    const [data, setData] = useState<SweepResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await fetch(`${API_BASE}/api/chart/sweep`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        relation: spec.relation,
                        solve_for: spec.solve_for,
                        sweep_var: spec.sweep_var,
                        sweep_min: spec.sweep_range.min,
                        sweep_max: spec.sweep_range.max,
                        steps: spec.sweep_range.steps ?? 30,
                        sweep_unit: spec.sweep_unit ?? null,
                        output_unit: spec.output_unit ?? null,
                        fixed_inputs: spec.fixed_inputs ?? {},
                    }),
                });
                const json = await res.json();
                if (!cancelled) {
                    if (json.detail) setError(String(json.detail));
                    else setData(json);
                }
            } catch {
                if (!cancelled) setError("Could not reach the compute server.");
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [spec]);

    const geom = useMemo(() => {
        if (!data || data.points.length < 2) return null;
        const W = 420, H = 240, padL = 52, padR = 16, padT = 16, padB = 40;
        const xs = data.points.map((p) => p.x);
        const ys = data.points.map((p) => p.y);
        const xMin = Math.min(...xs), xMax = Math.max(...xs);
        const yMin = Math.min(...ys), yMax = Math.max(...ys);
        const sx = (x: number) => padL + ((x - xMin) / (xMax - xMin || 1)) * (W - padL - padR);
        const sy = (y: number) => H - padB - ((y - yMin) / (yMax - yMin || 1)) * (H - padT - padB);
        const path = data.points.map((p, i) => `${i === 0 ? "M" : "L"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(" ");
        const ticks = (lo: number, hi: number, n = 4) =>
            Array.from({ length: n + 1 }, (_, i) => lo + (hi - lo) * i / n);
        return { W, H, padL, padB, padT, padR, sx, sy, path, xMin, xMax, yMin, yMax, xTicks: ticks(xMin, xMax), yTicks: ticks(yMin, yMax) };
    }, [data]);

    const fmt = (v: number) => Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0) ? v.toExponential(1) : v.toFixed(2);

    return (
        <div className="bg-card/95 border border-border rounded-2xl p-6 shadow-xl w-full max-w-lg my-4">
            <div className="flex items-center gap-2 mb-1 border-b border-border pb-3">
                <LineIcon className="text-cyan-500" size={18} />
                <h3 className="text-base font-bold text-foreground">{spec.title}</h3>
            </div>
            {spec.description && <p className="text-muted-foreground text-sm my-3">{spec.description}</p>}

            {loading && <div className="text-muted-foreground text-sm py-8 text-center">Computing sweep…</div>}
            {error && (
                <div className="text-red-500 text-sm flex items-center gap-1 py-6"><AlertCircle size={14} />{error}</div>
            )}

            {geom && data && (
                <svg viewBox={`0 0 ${geom.W} ${geom.H}`} className="w-full h-auto mt-2" role="img">
                    {/* axes */}
                    <line x1={geom.padL} y1={geom.padT} x2={geom.padL} y2={geom.H - geom.padB} stroke="currentColor" className="text-border" strokeWidth={1} />
                    <line x1={geom.padL} y1={geom.H - geom.padB} x2={geom.W - geom.padR} y2={geom.H - geom.padB} stroke="currentColor" className="text-border" strokeWidth={1} />
                    {/* gridlines + y ticks */}
                    {geom.yTicks.map((t, i) => (
                        <g key={`y${i}`}>
                            <line x1={geom.padL} y1={geom.sy(t)} x2={geom.W - geom.padR} y2={geom.sy(t)} stroke="currentColor" className="text-border/40" strokeWidth={0.5} />
                            <text x={geom.padL - 6} y={geom.sy(t) + 3} textAnchor="end" className="fill-muted-foreground" fontSize={9}>{fmt(t)}</text>
                        </g>
                    ))}
                    {/* x ticks */}
                    {geom.xTicks.map((t, i) => (
                        <text key={`x${i}`} x={geom.sx(t)} y={geom.H - geom.padB + 14} textAnchor="middle" className="fill-muted-foreground" fontSize={9}>{fmt(t)}</text>
                    ))}
                    {/* data */}
                    <path d={geom.path} fill="none" stroke="currentColor" className="text-cyan-500" strokeWidth={2} />
                    {/* labels */}
                    <text x={(geom.W) / 2} y={geom.H - 4} textAnchor="middle" className="fill-muted-foreground" fontSize={10}>{data.x_label}{data.x_unit ? ` (${data.x_unit})` : ""}</text>
                    <text x={12} y={geom.H / 2} textAnchor="middle" className="fill-muted-foreground" fontSize={10} transform={`rotate(-90 12 ${geom.H / 2})`}>{data.y_label}{data.y_unit ? ` (${data.y_unit})` : ""}</text>
                </svg>
            )}
        </div>
    );
}
