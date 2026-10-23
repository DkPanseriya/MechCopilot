"use client";

// Beam diagrams: loaded beam with supports/reactions/deflected shape, and a
// dimensioned cross-section (shared by section properties and profile selector).

import { useId } from "react";
import { Arrow, BODY, DiagramComponent, DiagramSvg, Dim, MomentArrow, PinSupport, Tag, Wall } from "./primitives";

// --------------------------------------------------------------------------
// Loaded beam
// --------------------------------------------------------------------------

const X0 = 60, X1 = 500, BY = 118, BH = 10;
const SPAN = X1 - X0;
const xf = (f: number) => X0 + Math.min(Math.max(f, 0), 1) * SPAN;

type Dist = { a: number; b: number; wa: number; wb: number; label: string; self?: boolean };

function DistLoadGlyph({ d, id, level }: { d: Dist; id: string; level: number }) {
    const xa = xf(d.a), xb = xf(d.b);
    const top = (w: number) => BY - BH / 2 - 8 - 34 * Math.min(Math.abs(w), 1) - level * 6;
    const ya = top(d.wa), yb = top(d.wb);
    const n = Math.max(2, Math.round((xb - xa) / 26));
    const color = d.self ? "text-muted-foreground" : "text-rose-500";
    return (
        <g className={color}>
            <line x1={xa} y1={ya} x2={xb} y2={yb} stroke="currentColor" strokeWidth={1.4} />
            {Array.from({ length: n + 1 }, (_, i) => {
                const x = xa + ((xb - xa) * i) / n;
                const y = ya + ((yb - ya) * i) / n;
                return Math.abs(BY - BH / 2 - 2 - y) > 6 ? (
                    <Arrow key={i} x1={x} y1={y} x2={x} y2={BY - BH / 2 - 2} color="" width={1} head={6} id={id} />
                ) : null;
            })}
            <text x={(xa + xb) / 2} y={Math.min(ya, yb) - 5} textAnchor="middle" className="fill-current"
                fontSize={11} fontWeight={d.self ? 400 : 600}>{d.self ? `self-weight ${d.label}` : `w ${d.label}`}</text>
        </g>
    );
}

const BeamAnalysis: DiagramComponent = ({ params }) => {
    const id = useId().replace(/:/g, "");
    const supports: { f: number; type: string }[] = params.supports || [];
    const points: { f: number; label: string; up: boolean }[] = params.points || [];
    const dists: Dist[] = params.dists || [];
    const moments: { f: number; label: string; ccw: boolean }[] = params.moments || [];
    const reactions: { f: number; label: string; mlabel: string | null }[] = params.reactions || [];
    const shape: [number, number][] = params.shape || [];
    const ok = params.ok !== false;

    const shapePath = shape.map(([f, v], i) => `${i ? "L" : "M"}${xf(f).toFixed(1)},${(BY - 24 * v).toFixed(1)}`).join("");
    // Real (non self-weight) distributed loads stack above the self-weight band.
    const ordered = [...dists].sort((a, b) => Number(Boolean(b.self)) - Number(Boolean(a.self)));

    return (
        <DiagramSvg w={560} h={262} label="Beam with supports, loads and deflected shape" id={id}>
            <Tag x={12} y={18} text={params.section ?? ""} />

            {ordered.map((d, i) => <DistLoadGlyph key={i} d={d} id={id} level={d.self ? 0 : i} />)}

            <rect x={X0} y={BY - BH / 2} width={SPAN} height={BH} rx={2} className={BODY} strokeWidth={1.4} />
            {shapePath && (
                <path d={shapePath} fill="none" stroke="currentColor" strokeWidth={1.5} strokeDasharray="5 3"
                    className="text-violet-500" />
            )}

            {supports.map((s, i) => {
                const x = xf(s.f);
                if (s.type === "fixed") {
                    const left = s.f < 0.5;
                    return <Wall key={i} x={left ? X0 : X1} y={BY - 30} h={60} side={left ? "left" : "right"} id={id} />;
                }
                return <PinSupport key={i} x={x} y={BY + BH / 2} roller={s.type === "roller"} />;
            })}

            {points.map((p, i) => {
                const x = xf(p.f);
                return p.up ? (
                    <Arrow key={i} x1={x} y1={BY + 70} x2={x} y2={BY + BH / 2 + 2} label={p.label} id={id} dx={5} dy={12} />
                ) : (
                    <Arrow key={i} x1={x} y1={BY - 72 - (i % 2) * 10} x2={x} y2={BY - BH / 2 - 2} label={p.label} id={id} dx={5} dy={4} />
                );
            })}

            {moments.map((m, i) => (
                <MomentArrow key={i} cx={xf(m.f)} cy={BY} r={17} label={m.label} id={id} ccw={m.ccw} />
            ))}

            {reactions.map((r, i) => {
                const x = Math.min(Math.max(xf(r.f), X0 + 28), X1 - 28);
                return (
                    <g key={i}>
                        <Tag x={x} y={BY + 46} anchor="middle" text={`R${i + 1} ${r.label}`} tone="ok" />
                        {r.mlabel && <Tag x={x} y={BY + 60} anchor="middle" text={`M ${r.mlabel}`} tone="moment" />}
                    </g>
                );
            })}

            <Dim x1={X0} y1={BY + 84} x2={X1} y2={BY + 84} label={`L = ${params.L ?? ""}`} id={id} />

            {params.maxM && (
                <g>
                    <circle cx={xf(params.maxM.f)} cy={BY} r={3} className="fill-amber-500" />
                    <Tag x={X0} y={252} text={params.maxM.label} tone="moment" />
                </g>
            )}
            {params.maxD && (
                <g>
                    <circle cx={xf(params.maxD.f)} cy={BY + 24} r={3} className="fill-violet-500" />
                    <Tag x={X1} y={252} anchor="end" text={params.maxD.label} tone={ok ? "neutral" : "bad"} />
                </g>
            )}
        </DiagramSvg>
    );
};

// --------------------------------------------------------------------------
// Cross-section
// --------------------------------------------------------------------------

type Pt = [number, number];

function outline(d: Record<string, any>): { solid: Pt[] | null; kind: string } {
    const b = Number(d.b), h = Number(d.h), tw = Number(d.tw), tf = Number(d.tf), t = Number(d.t);
    switch (d.shape) {
        case "i":
            return { kind: "poly", solid: [[0, 0], [b, 0], [b, tf], [b / 2 + tw / 2, tf], [b / 2 + tw / 2, h - tf], [b, h - tf], [b, h], [0, h], [0, h - tf], [b / 2 - tw / 2, h - tf], [b / 2 - tw / 2, tf], [0, tf]] };
        case "channel":
            return { kind: "poly", solid: [[0, 0], [b, 0], [b, tf], [tw, tf], [tw, h - tf], [b, h - tf], [b, h], [0, h]] };
        case "tee":
            return { kind: "poly", solid: [[b / 2 - tw / 2, 0], [b / 2 + tw / 2, 0], [b / 2 + tw / 2, h - tf], [b, h - tf], [b, h], [0, h], [0, h - tf], [b / 2 - tw / 2, h - tf]] };
        case "angle":
            return { kind: "poly", solid: [[0, 0], [b, 0], [b, t], [t, t], [t, h], [0, h]] };
        default:
            return { kind: d.shape, solid: null };
    }
}

function CrossSection({ d, box, id }: { d: Record<string, any>; box: { x: number; y: number; w: number; h: number }; id: string }) {
    const round = d.shape === "round" || d.shape === "chs";
    const B = round ? Number(d.D) : Number(d.b);
    const H = round ? Number(d.D) : Number(d.h);
    if (!(B > 0 && H > 0)) return null;
    const s = Math.min(box.w / B, box.h / H);
    const ox = box.x + (box.w - B * s) / 2;
    const oy = box.y + box.h - (box.h - H * s) / 2;          // bottom of section
    const X = (z: number) => ox + z * s;
    const Y = (y: number) => oy - y * s;
    const zc = d.zc ?? B / 2, yc = d.yc ?? H / 2;
    const { solid } = outline(d);

    let body: React.ReactNode = null;
    if (solid) {
        body = <path d={solid.map(([z, y], i) => `${i ? "L" : "M"}${X(z)},${Y(y)}`).join("") + "Z"} className={BODY} strokeWidth={1.5} />;
    } else if (d.shape === "rect") {
        body = <rect x={X(0)} y={Y(H)} width={B * s} height={H * s} className={BODY} strokeWidth={1.5} />;
    } else if (d.shape === "rhs") {
        const t = Number(d.t), r = Number(d.r ?? 0);
        body = (
            <g>
                <rect x={X(0)} y={Y(H)} width={B * s} height={H * s} rx={r * s} className={BODY} strokeWidth={1.5} />
                <rect x={X(t)} y={Y(H - t)} width={(B - 2 * t) * s} height={(H - 2 * t) * s} rx={Math.max(r - t, 0) * s}
                    className="fill-background stroke-current" strokeWidth={1.2} />
            </g>
        );
    } else if (d.shape === "round") {
        body = <circle cx={X(B / 2)} cy={Y(H / 2)} r={(B / 2) * s} className={BODY} strokeWidth={1.5} />;
    } else if (d.shape === "chs") {
        const t = Number(d.t);
        body = (
            <g>
                <circle cx={X(B / 2)} cy={Y(H / 2)} r={(B / 2) * s} className={BODY} strokeWidth={1.5} />
                <circle cx={X(B / 2)} cy={Y(H / 2)} r={(B / 2 - t) * s} className="fill-background stroke-current" strokeWidth={1.2} />
            </g>
        );
    }

    const cx = X(zc), cy = Y(yc);
    return (
        <g>
            {body}
            <g className="text-muted-foreground" strokeDasharray="8 3 2 3">
                <line x1={X(0) - 16} y1={cy} x2={X(B) + 16} y2={cy} stroke="currentColor" strokeWidth={0.8} />
                <line x1={cx} y1={Y(H) - 14} x2={cx} y2={Y(0) + 14} stroke="currentColor" strokeWidth={0.8} />
            </g>
            <text x={X(B) + 20} y={cy + 4} className="fill-muted-foreground" fontSize={11} fontStyle="italic">y</text>
            <text x={cx + 4} y={Y(H) - 16} className="fill-muted-foreground" fontSize={11} fontStyle="italic">z</text>
            <circle cx={cx} cy={cy} r={3.2} className="fill-amber-500" />
            <Dim x1={X(0)} y1={Y(0) + 26} x2={X(B)} y2={Y(0) + 26} label={round ? `Ø${d.D}` : `b ${d.b}`} id={id} />
            {!round && <Dim x1={X(0) - 26} y1={Y(H)} x2={X(0) - 26} y2={Y(0)} label={`h ${d.h}`} id={id} />}
        </g>
    );
}

function thicknessNote(d: Record<string, any>): string {
    switch (d.shape) {
        case "i":
        case "channel":
        case "tee":
            return `tw ${d.tw} · tf ${d.tf}${d.r ? ` · r ${d.r}` : ""} mm`;
        case "rhs":
        case "chs":
        case "angle":
            return `t ${d.t} mm`;
        default:
            return "mm";
    }
}

function SectionPanel({ params, title }: { params: Record<string, any>; title?: string }) {
    const id = useId().replace(/:/g, "");
    if (!params?.shape) {
        return (
            <DiagramSvg w={560} h={120} label="No section" id={id}>
                <Tag x={280} y={64} anchor="middle" text={params?.label || "No section to draw"} tone="bad" />
            </DiagramSvg>
        );
    }
    return (
        <DiagramSvg w={560} h={270} label={`Cross-section ${params.label ?? ""}`} id={id}>
            <CrossSection d={params} box={{ x: 90, y: 30, w: 220, h: 190 }} id={id} />
            <g>
                {title && <Tag x={350} y={50} text={title} />}
                <Tag x={350} y={title ? 74 : 56} text={params.label ?? ""} />
                <text x={350} y={title ? 94 : 76} className="fill-muted-foreground" fontSize={11}>{thicknessNote(params)}</text>
                {params.A && <Tag x={350} y={128} text={params.A} />}
                {params.Iy && <Tag x={350} y={150} text={params.Iy} tone="moment" />}
                {params.Wy && <Tag x={350} y={172} text={params.Wy} tone="load" />}
                <circle cx={354} cy={198} r={3.2} className="fill-amber-500" />
                <text x={362} y={202} className="fill-muted-foreground" fontSize={11}>centroid, axes y–y / z–z</text>
            </g>
        </DiagramSvg>
    );
}

const SectionProperties: DiagramComponent = ({ params }) => <SectionPanel params={params} />;
const ProfileSelector: DiagramComponent = ({ params }) => <SectionPanel params={params} title="Lightest passing profile" />;

export const DIAGRAMS: Record<string, DiagramComponent> = {
    beam_analysis: BeamAnalysis,
    section_properties: SectionProperties,
    beam_profile_selector: ProfileSelector,
};
