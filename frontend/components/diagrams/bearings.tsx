"use client";

// Bearing diagrams: an axial section through the bearing drawn to its real
// d / D / B proportions, with the rolling-element shape of the chosen type.
// params come from backend/engineering/bearings/calcs.py (result.diagram.params).

import { useId } from "react";
import { Arrow, BODY, BODY_DARK, DiagramComponent, DiagramSvg, Dim, Tag } from "./primitives";

type Kind = "ball" | "angular" | "roller" | "barrel" | "taper" | "thrust";

const num = (v: any): number | null => (typeof v === "number" && isFinite(v) ? v : null);
const g = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/0+$/, "").replace(/\.$/, ""));

function Section({ id, kind, d, D, B, xc, y0 }: { id: string; kind: Kind; d: number; D: number; B: number; xc: number; y0: number }) {
    const s = 170 / D;                        // px per mm (fit outer diameter)
    const Ro = (D / 2) * s, Ri = (d / 2) * s;
    const w = Math.max(B * s, 34);
    const x0 = xc - w / 2;
    const ring = (Ro - Ri) * 0.28;
    const rm = (Ro + Ri) / 2;
    const el = (Ro - Ri) * 0.42;

    const half = (sign: 1 | -1) => {
        const y = (r: number) => y0 - sign * r;
        const top = (a: number, b: number) => Math.min(y(a), y(b));
        const h = (a: number, b: number) => Math.abs(y(a) - y(b));
        if (kind === "thrust") {
            const tw = w * 0.3;
            return (
                <g key={sign}>
                    {/* shaft washer (left, bore = d) and housing washer (right, OD = D) */}
                    <rect x={x0} y={top(Ri, Ro - el * 0.2)} width={tw} height={h(Ri, Ro - el * 0.2)} className={BODY} strokeWidth={1.3} />
                    <rect x={x0 + w - tw} y={top(Ri + el * 0.2, Ro)} width={tw} height={h(Ri + el * 0.2, Ro)} className={BODY} strokeWidth={1.3} />
                    <circle cx={xc} cy={y(rm)} r={Math.min((w - 2 * tw) / 2 - 1, el / 2)} className={BODY_DARK} strokeWidth={1.3} />
                </g>
            );
        }
        let element: React.ReactNode;
        const cy = y(rm);
        if (kind === "ball" || kind === "angular") {
            element = (
                <>
                    <circle cx={xc} cy={cy} r={el / 2} className={BODY_DARK} strokeWidth={1.3} />
                    {kind === "angular" && (
                        <line x1={xc - (el * 0.9) * Math.sin(0.70) * sign} y1={cy - el * 0.9 * Math.cos(0.70)}
                            x2={xc + (el * 0.9) * Math.sin(0.70) * sign} y2={cy + el * 0.9 * Math.cos(0.70)}
                            stroke="currentColor" strokeDasharray="3 2" strokeWidth={1} className="text-muted-foreground" />
                    )}
                </>
            );
        } else if (kind === "roller") {
            element = <rect x={xc - w * 0.32} y={cy - el / 2} width={w * 0.64} height={el} rx={1.5} className={BODY_DARK} strokeWidth={1.3} />;
        } else if (kind === "barrel") {
            element = <rect x={xc - w * 0.3} y={cy - el / 2} width={w * 0.6} height={el} rx={el / 2.4} className={BODY_DARK} strokeWidth={1.3} />;
        } else {
            // tapered: trapezoid, larger end towards the back face
            const a = el * 0.62, b = el * 0.95, hw = w * 0.32;
            element = (
                <polygon
                    points={`${xc - hw},${cy - (a / 2) * sign} ${xc + hw},${cy - (b / 2) * sign} ${xc + hw},${cy + (b / 2) * sign} ${xc - hw},${cy + (a / 2) * sign}`}
                    transform={`rotate(${-12 * sign} ${xc} ${cy})`}
                    className={BODY_DARK} strokeWidth={1.3} />
            );
        }
        return (
            <g key={sign}>
                <rect x={x0} y={top(Ro, Ro - ring)} width={w} height={h(Ro, Ro - ring)} className={BODY} strokeWidth={1.3} />
                <rect x={x0} y={top(Ri, Ri + ring)} width={w} height={h(Ri, Ri + ring)} className={BODY} strokeWidth={1.3} />
                {element}
            </g>
        );
    };

    return (
        <g>
            {/* shaft through the bore */}
            <rect x={60} y={y0 - Ri} width={xc + w / 2 + 40 - 60} height={2 * Ri} className="fill-muted/60 stroke-current text-muted-foreground" strokeWidth={0.8} />
            <line x1={40} y1={y0} x2={xc + w / 2 + 60} y2={y0} stroke="currentColor" strokeDasharray="10 3 2 3" strokeWidth={0.8} className="text-muted-foreground" />
            {half(1)}
            {half(-1)}
            <Dim x1={xc + w / 2 + 26} y1={y0 - Ro} x2={xc + w / 2 + 26} y2={y0 + Ro} label={`Ø${g(D)}`} id={id} />
            <Dim x1={x0 - 22} y1={y0 - Ri} x2={x0 - 22} y2={y0 + Ri} label={`Ø${g(d)}`} id={id} />
            <Dim x1={x0} y1={y0 + Ro + 16} x2={x0 + w} y2={y0 + Ro + 16} label={g(B)} id={id} />
        </g>
    );
}

const BearingSection: DiagramComponent = ({ params }) => {
    const id = useId().replace(/:/g, "");
    const d = num(params.d), D = num(params.D), B = num(params.B);
    const kind = (params.kind || "ball") as Kind;
    const y0 = 128, xc = 230;

    if (d === null || D === null || B === null) {
        return (
            <DiagramSvg w={560} h={120} label="No bearing selected" id={id}>
                <Tag x={280} y={64} anchor="middle" text="No bearing in the database fits these requirements." tone="bad" />
            </DiagramSvg>
        );
    }
    const s = 170 / D;
    const top = y0 - (D / 2) * s;
    const w = Math.max(B * s, 34);
    const envelope = params.mode === "envelope";

    return (
        <DiagramSvg w={560} h={268} label={`Bearing ${params.designation ?? ""} cross-section`} id={id}>
            <Section id={id} kind={kind} d={d} D={D} B={B} xc={xc} y0={y0} />

            {params.Fr && (
                <Arrow x1={xc} y1={top - 34} x2={xc} y2={top - 3} label={`Fr ${params.Fr}`} id={id} dx={8} dy={10} />
            )}
            {params.Fa && (
                <Arrow x1={14} y1={y0} x2={58} y2={y0} label={`Fa ${params.Fa}`} id={id} dx={0} dy={-10} />
            )}

            <g>
                <Tag x={392} y={42} text={String(params.designation ?? "")} />
                <text x={392} y={60} className="fill-muted-foreground" fontSize={11}>{params.type}</text>
                <text x={392} y={78} className="fill-muted-foreground" fontSize={11}>{`${g(d)} × ${g(D)} × ${g(B)} mm`}</text>
                {params.L10h && <Tag x={392} y={110} text={`L10h  ${params.L10h}`} />}
                {params.Lnmh && (
                    <Tag x={392} y={params.L10h ? 128 : 110} text={`${envelope ? "Life" : "Lnmh"}  ${params.Lnmh}`}
                        tone={params.life_ok === false ? "bad" : params.ok === false && envelope ? "bad" : "ok"} />
                )}
                {params.s0 && <Tag x={392} y={params.L10h ? 146 : 128} text={`s0  ${params.s0}`} />}
                {params.n && <text x={392} y={164} className="fill-muted-foreground" fontSize={11}>{params.n}</text>}
                {envelope && num(params.bore_min) !== null && (
                    <text x={392} y={200} className="fill-muted-foreground" fontSize={11}>
                        {`Bore range ${g(params.bore_min)}${num(params.bore_max) !== null ? `–${g(params.bore_max)}` : "+"} mm`}
                    </text>
                )}
                {envelope && num(params.od_max) !== null && (
                    <text x={392} y={216} className="fill-muted-foreground" fontSize={11}>{`OD limit ${g(params.od_max)} mm`}</text>
                )}
                {envelope && num(params.width_max) !== null && (
                    <text x={392} y={232} className="fill-muted-foreground" fontSize={11}>{`Width limit ${g(params.width_max)} mm`}</text>
                )}
            </g>
            {envelope && num(params.od_max) !== null && (params.od_max as number) >= D && (
                <rect x={xc - w / 2 - 6} y={y0 - ((params.od_max as number) / 2) * s} width={w + 12}
                    height={(params.od_max as number) * s} fill="none" stroke="currentColor" strokeDasharray="4 3"
                    className="text-emerald-500" strokeWidth={1} />
            )}
        </DiagramSvg>
    );
};

export const DIAGRAMS: Record<string, DiagramComponent> = {
    bearing_section: BearingSection,
    bearing_envelope: BearingSection,
};
