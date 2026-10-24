"use client";

import { useMemo, useRef, useState } from "react";
import type { RunSeries } from "@/types/calculator";

const COLORS = ["text-cyan-500", "text-amber-500", "text-violet-500", "text-emerald-500", "text-rose-500"];
const FILLS = ["fill-cyan-500/15", "fill-amber-500/15", "fill-violet-500/15", "fill-emerald-500/15", "fill-rose-500/15"];

function niceTicks(lo: number, hi: number, count = 5): number[] {
    if (!isFinite(lo) || !isFinite(hi)) return [];
    if (lo === hi) {
        const d = Math.abs(lo) || 1;
        lo -= d * 0.5;
        hi += d * 0.5;
    }
    const raw = (hi - lo) / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / mag;
    const stepSize = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
    const start = Math.ceil(lo / stepSize) * stepSize;
    const ticks: number[] = [];
    for (let v = start; v <= hi + stepSize * 1e-9; v += stepSize) ticks.push(Math.abs(v) < stepSize * 1e-9 ? 0 : v);
    return ticks;
}

/** Decade ticks for a log axis, given log10 bounds. Returns values in log space. */
function logTicks(lo: number, hi: number): number[] {
    const out: number[] = [];
    for (let k = Math.ceil(lo - 1e-9); k <= Math.floor(hi + 1e-9); k++) out.push(k);
    if (out.length < 2) return [lo, hi];
    return out;
}

export function fmtNum(v: number): string {
    if (!isFinite(v)) return "–";
    const a = Math.abs(v);
    if (a === 0) return "0";
    if (a >= 1e5 || a < 1e-3) return v.toExponential(2);
    if (a >= 100) return v.toFixed(0);
    if (a >= 10) return v.toFixed(1);
    if (a >= 1) return v.toFixed(2);
    return v.toPrecision(3);
}

function fmtDecade(k: number): string {
    const v = Math.pow(10, k);
    return Math.abs(k) >= 4 ? `1e${k}` : fmtNum(v);
}

export default function Plot({ series, height = 220 }: { series: RunSeries[]; height?: number }) {
    const [hover, setHover] = useState<number | null>(null);
    const svgRef = useRef<SVGSVGElement>(null);
    const first = series[0];
    const xLog = first?.x_scale === "log";
    const yLog = first?.y_scale === "log";

    const g = useMemo(() => {
        if (!first || first.x.length < 1) return null;
        const tx = (v: number) => (xLog ? Math.log10(v) : v);
        const ty = (v: number) => (yLog ? Math.log10(v) : v);
        const okX = (v: number) => isFinite(v) && (!xLog || v > 0);
        const okY = (v: number) => isFinite(v) && (!yLog || v > 0);

        const W = 560, H = height, padL = 58, padR = 18, padT = 14, padB = 40;
        const xs = series.flatMap((s) => s.x.filter(okX).map(tx));
        const ys = series.flatMap((s) => s.y.filter(okY).map(ty))
            .concat(series.flatMap((s) => s.ref_lines.map((r) => r.y).filter(okY).map(ty)));
        if (!xs.length || !ys.length) return null;
        let xMin = Math.min(...xs), xMax = Math.max(...xs);
        let yMin = Math.min(...ys), yMax = Math.max(...ys);
        if (!yLog && series.some((s) => s.kind === "area")) {
            yMin = Math.min(yMin, 0);
            yMax = Math.max(yMax, 0);
        }
        if (yMin === yMax) { yMin -= 1; yMax += 1; }
        if (xMin === xMax) { xMin -= 1; xMax += 1; }
        if (!yLog) {
            const yPad = (yMax - yMin) * 0.08;
            if (yMin < 0 || series.every((s) => s.kind !== "area")) yMin -= yPad;
            yMax += yPad;
        }
        const sx = (x: number) => padL + ((tx(x) - xMin) / (xMax - xMin)) * (W - padL - padR);
        const sy = (y: number) => H - padB - ((ty(y) - yMin) / (yMax - yMin)) * (H - padT - padB);
        // Ticks are always returned as raw (un-transformed) values with labels.
        const xTicks = xLog ? logTicks(xMin, xMax).map((k) => ({ v: Math.pow(10, k), l: fmtDecade(k) }))
                            : niceTicks(xMin, xMax).map((v) => ({ v, l: fmtNum(v) }));
        const yTicks = yLog ? logTicks(yMin, yMax).map((k) => ({ v: Math.pow(10, k), l: fmtDecade(k) }))
                            : niceTicks(yMin, yMax).map((v) => ({ v, l: fmtNum(v) }));
        return { W, H, padL, padR, padT, padB, sx, sy, okX, okY, xMin, xMax, yMin, yMax, xTicks, yTicks };
    }, [series, first, height, xLog, yLog]);

    if (!g || !first) return null;

    const pts = (s: RunSeries) => s.x.map((x, i) => [x, s.y[i]] as const).filter(([x, y]) => g.okX(x) && g.okY(y));

    const pathFor = (s: RunSeries) => {
        const p = pts(s);
        if (s.kind === "step") {
            return p.map(([x, y], i) => i === 0
                ? `M${g.sx(x)},${g.sy(y)}`
                : `L${g.sx(x)},${g.sy(p[i - 1][1])}L${g.sx(x)},${g.sy(y)}`).join("");
        }
        return p.map(([x, y], i) => `${i ? "L" : "M"}${g.sx(x).toFixed(1)},${g.sy(y).toFixed(1)}`).join("");
    };

    const areaFor = (s: RunSeries) => {
        const p = pts(s);
        if (!p.length) return "";
        const base = g.sy(Math.max(g.yMin, Math.min(0, g.yMax)));
        return `${pathFor(s)}L${g.sx(p[p.length - 1][0])},${base}L${g.sx(p[0][0])},${base}Z`;
    };

    const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
        const svg = svgRef.current;
        if (!svg) return;
        const rect = svg.getBoundingClientRect();
        const px = ((e.clientX - rect.left) / rect.width) * g.W;
        if (px < g.padL || px > g.W - g.padR) { setHover(null); return; }
        let best = -1, bestD = Infinity;
        first.x.forEach((x, i) => {
            if (!g.okX(x)) return;
            const d = Math.abs(g.sx(x) - px);
            if (d < bestD) { bestD = d; best = i; }
        });
        setHover(best >= 0 ? best : null);
    };

    const zeroInside = !yLog && g.yMin < 0 && g.yMax > 0;
    const legend = series.length > 1;

    return (
        <div className="w-full">
            <div className="flex items-baseline justify-between gap-3 mb-1 min-h-[18px]">
                <div className="text-xs text-muted-foreground">{legend && first.group ? first.group : first.title}</div>
                {hover !== null && (
                    <div className="text-xs text-muted-foreground tabular-nums text-right">
                        {first.x_label} = {fmtNum(first.x[hover])} {first.x_unit}
                        {series.map((s, i) => s.y[hover] !== undefined && s.x[hover] === first.x[hover] && (
                            <span key={s.id} className={`ml-3 ${COLORS[i % COLORS.length]}`}>
                                {s.y_label} = {fmtNum(s.y[hover])} {s.y_unit}
                            </span>
                        ))}
                    </div>
                )}
            </div>
            <svg ref={svgRef} viewBox={`0 0 ${g.W} ${g.H}`} className="w-full h-auto select-none touch-none"
                onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label={first.title}>
                {g.yTicks.map((t) => (
                    <g key={`y${t.v}`}>
                        <line x1={g.padL} x2={g.W - g.padR} y1={g.sy(t.v)} y2={g.sy(t.v)} stroke="currentColor" className="text-border" strokeWidth={0.6} />
                        <text x={g.padL - 6} y={g.sy(t.v) + 3} textAnchor="end" className="fill-muted-foreground" fontSize={10}>{t.l}</text>
                    </g>
                ))}
                {g.xTicks.map((t) => (
                    <g key={`x${t.v}`}>
                        {xLog && <line x1={g.sx(t.v)} x2={g.sx(t.v)} y1={g.padT} y2={g.H - g.padB} stroke="currentColor" className="text-border" strokeWidth={0.6} />}
                        <text x={g.sx(t.v)} y={g.H - g.padB + 15} textAnchor="middle" className="fill-muted-foreground" fontSize={10}>{t.l}</text>
                    </g>
                ))}
                <line x1={g.padL} x2={g.padL} y1={g.padT} y2={g.H - g.padB} stroke="currentColor" className="text-muted-foreground/60" strokeWidth={1} />
                <line x1={g.padL} x2={g.W - g.padR} y1={g.H - g.padB} y2={g.H - g.padB} stroke="currentColor" className="text-muted-foreground/60" strokeWidth={1} />
                {zeroInside && <line x1={g.padL} x2={g.W - g.padR} y1={g.sy(0)} y2={g.sy(0)} stroke="currentColor" className="text-muted-foreground" strokeWidth={1} />}

                {series.map((s, i) => (
                    <g key={s.id} className={COLORS[i % COLORS.length]}>
                        {s.kind === "area" && !yLog && <path d={areaFor(s)} className={FILLS[i % FILLS.length]} stroke="none" />}
                        {s.kind === "scatter"
                            ? pts(s).map(([x, y], j) => <circle key={j} cx={g.sx(x)} cy={g.sy(y)} r={4.5} className="fill-current" stroke="var(--background)" strokeWidth={1.5} />)
                            : <path d={pathFor(s)} fill="none" stroke="currentColor" strokeWidth={2} strokeLinejoin="round" />}
                    </g>
                ))}

                {series.flatMap((s) => s.ref_lines).filter((r) => g.okY(r.y)).map((r, i) => (
                    <g key={`r${i}`} className="text-rose-500">
                        <line x1={g.padL} x2={g.W - g.padR} y1={g.sy(r.y)} y2={g.sy(r.y)} stroke="currentColor" strokeWidth={1.2} strokeDasharray="5 4" />
                        <text x={g.W - g.padR - 4} y={g.sy(r.y) - 4} textAnchor="end" className="fill-rose-500" fontSize={10}>{r.label}</text>
                    </g>
                ))}
                {series.flatMap((s) => s.markers).filter((m) => g.okX(m.x)).map((m, i) => (
                    <g key={`m${i}`} className="text-foreground/70">
                        <line x1={g.sx(m.x)} x2={g.sx(m.x)} y1={g.padT} y2={g.H - g.padB} stroke="currentColor" strokeWidth={1} strokeDasharray="3 3" />
                        <text x={g.sx(m.x) + 4} y={g.padT + 10 + (i % 2) * 12} className="fill-foreground/80" fontSize={10}>{m.label}</text>
                    </g>
                ))}

                {hover !== null && (
                    <g>
                        <line x1={g.sx(first.x[hover])} x2={g.sx(first.x[hover])} y1={g.padT} y2={g.H - g.padB} stroke="currentColor" className="text-foreground/30" strokeWidth={1} />
                        {series.map((s, i) => s.y[hover] !== undefined && g.okY(s.y[hover]) && g.okX(s.x[hover]) && (
                            <circle key={s.id} cx={g.sx(s.x[hover])} cy={g.sy(s.y[hover])} r={3.5} className={`${COLORS[i % COLORS.length]} fill-current`} />
                        ))}
                    </g>
                )}

                <text x={(g.padL + g.W - g.padR) / 2} y={g.H - 6} textAnchor="middle" className="fill-muted-foreground" fontSize={11}>
                    {first.x_label}{first.x_unit ? ` (${first.x_unit})` : ""}{xLog ? " · log" : ""}
                </text>
                <text x={13} y={(g.padT + g.H - g.padB) / 2} textAnchor="middle" className="fill-muted-foreground" fontSize={11}
                    transform={`rotate(-90 13 ${(g.padT + g.H - g.padB) / 2})`}>
                    {legend ? first.y_unit : `${first.y_label}${first.y_unit ? ` (${first.y_unit})` : ""}`}{yLog ? " · log" : ""}
                </text>
            </svg>
            {legend && (
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
                    {series.map((s, i) => (
                        <span key={s.id} className={`text-[11px] flex items-center gap-1.5 ${COLORS[i % COLORS.length]}`}>
                            <span className={`inline-block ${s.kind === "scatter" ? "w-2 h-2 rounded-full" : "w-3 h-0.5 rounded"} bg-current`} />
                            <span className="text-muted-foreground">{s.title}</span>
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
