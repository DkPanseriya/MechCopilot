"use client";

// Shared SVG building blocks for engineering diagrams. Every color uses theme
// classes (text-*/fill-*) so diagrams read in light and dark mode.
//
// Conventions:
//   loads/forces  -> rose     moments/torques -> amber    dimensions -> muted
//   geometry body -> cyan tint fill + foreground stroke    results -> emerald/rose

import React from "react";

export type DiagramProps = {
    /** Display-ready values computed by the backend (result.diagram.params). */
    params: Record<string, any>;
    /** Current raw calculator inputs. */
    inputs: Record<string, any>;
};

export type DiagramComponent = (props: DiagramProps) => React.ReactElement | null;

/** Arrow-head markers. Place <Defs /> once inside each <svg>.
 *  Prefer the Arrow / Dim / MomentArrow components: they draw their own heads in the
 *  line's colour. The markers remain for ad-hoc lines; `context-stroke` colours them
 *  where supported and the fill-current class is the fallback elsewhere. */
export function Defs({ id = "d" }: { id?: string }) {
    return (
        <defs>
            <marker id={`${id}-arrow`} markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10"
                refX="9" refY="5" orient="auto-start-reverse">
                <path d="M0,1 L9,5 L0,9 Z" className="fill-current" style={{ fill: "context-stroke" }} />
            </marker>
            <marker id={`${id}-tick`} markerUnits="userSpaceOnUse" markerWidth="2" markerHeight="12" refX="1" refY="6" orient="auto">
                <line x1="1" y1="0" x2="1" y2="12" className="stroke-current" style={{ stroke: "context-stroke" }} strokeWidth="1.2" />
            </marker>
            <pattern id={`${id}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" strokeWidth="1" />
            </pattern>
        </defs>
    );
}

/** Filled arrowhead with its tip at (x,y), pointing along `angle` (radians). Inherits colour. */
export function Head({ x, y, angle, size = 9 }: { x: number; y: number; angle: number; size?: number }) {
    const w = size * 0.42;
    const bx = x - size * Math.cos(angle), by = y - size * Math.sin(angle);
    const px = -Math.sin(angle) * w, py = Math.cos(angle) * w;
    return <path d={`M${x},${y} L${bx + px},${by + py} L${bx - px},${by - py} Z`} fill="currentColor" stroke="none" />;
}

/** Halo so labels stay legible over hatching, centrelines and other strokes. */
const HALO = { paintOrder: "stroke" as const, stroke: "var(--background)", strokeWidth: 3, strokeLinejoin: "round" as const };

/** Straight force arrow from (x1,y1) to (x2,y2) with optional label at the tail. */
export function Arrow({ x1, y1, x2, y2, label, color = "text-rose-500", dx = 6, dy = -4, width = 2, head = 9 }: {
    x1: number; y1: number; x2: number; y2: number; label?: string; color?: string; id?: string;
    dx?: number; dy?: number; width?: number; head?: number;
}) {
    const a = Math.atan2(y2 - y1, x2 - x1);
    const len = Math.hypot(x2 - x1, y2 - y1);
    const back = Math.min(head * 0.8, len);
    return (
        <g className={color}>
            <line x1={x1} y1={y1} x2={x2 - back * Math.cos(a)} y2={y2 - back * Math.sin(a)} stroke="currentColor" strokeWidth={width} />
            <Head x={x2} y={y2} angle={a} size={head} />
            {label && <text x={x1 + dx} y={y1 + dy} className="fill-current" fontSize={12} fontWeight={600} style={HALO}>{label}</text>}
        </g>
    );
}

/** Curved moment / torque arrow around (cx,cy). */
export function MomentArrow({ cx, cy, r = 18, label, color = "text-amber-500", ccw = false }: {
    cx: number; cy: number; r?: number; label?: string; color?: string; id?: string; ccw?: boolean;
}) {
    const a0 = ccw ? 200 : -20, a1 = ccw ? -70 : 250;
    const rad = (a: number) => (a * Math.PI) / 180;
    const p = (a: number) => [cx + r * Math.cos(rad(a)), cy + r * Math.sin(rad(a))];
    const [sx, sy] = p(a0), [ex, ey] = p(a1);
    // Tangent at the arc end: +90° when sweeping with increasing angle (clockwise on screen).
    const tangent = rad(a1 + (ccw ? -90 : 90));
    return (
        <g className={color}>
            <path d={`M${sx},${sy} A${r},${r} 0 1 ${ccw ? 0 : 1} ${ex},${ey}`} fill="none" stroke="currentColor" strokeWidth={2} />
            <Head x={ex + 4 * Math.cos(tangent)} y={ey + 4 * Math.sin(tangent)} angle={tangent} size={9} />
            {label && <text x={cx + r + 4} y={cy - r + 2} className="fill-current" fontSize={12} fontWeight={600} style={HALO}>{label}</text>}
        </g>
    );
}

/** Dimension line with arrowheads at both ends. Vertical dimensions get a rotated
 *  label beside the line (drawing convention), horizontal ones a label above it. */
export function Dim({ x1, y1, x2, y2, label, offset = 0 }: {
    x1: number; y1: number; x2: number; y2: number; label: string; id?: string; offset?: number;
}) {
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    const vertical = Math.abs(x2 - x1) < Math.abs(y2 - y1);
    const a = Math.atan2(y2 - y1, x2 - x1);
    const lx = vertical ? mx + 12 + offset : mx;
    const ly = vertical ? my : my - 5 + offset;
    return (
        <g className="text-muted-foreground">
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="currentColor" strokeWidth={0.9} />
            <Head x={x2} y={y2} angle={a} size={7} />
            <Head x={x1} y={y1} angle={a + Math.PI} size={7} />
            <text
                x={lx} y={ly}
                textAnchor="middle"
                dominantBaseline={vertical ? "middle" : "auto"}
                transform={vertical ? `rotate(-90 ${lx} ${ly})` : undefined}
                className="fill-muted-foreground" fontSize={11} style={HALO}
            >{label}</text>
        </g>
    );
}

/** Small value tag (pill) — use for computed results on the drawing. */
export function Tag({ x, y, text, tone = "neutral", anchor = "start" }: {
    x: number; y: number; text: string; tone?: "neutral" | "ok" | "bad" | "load" | "moment"; anchor?: "start" | "middle" | "end";
}) {
    const tones: Record<string, string> = {
        neutral: "fill-foreground", ok: "fill-emerald-500", bad: "fill-rose-500",
        load: "fill-rose-500", moment: "fill-amber-500",
    };
    return <text x={x} y={y} textAnchor={anchor} className={tones[tone]} fontSize={11} fontWeight={600} style={HALO}>{text}</text>;
}

/** Fixed wall / clamp with hatching. side: which side the hatching is on. */
export function Wall({ x, y, h, side = "left", id = "d" }: { x: number; y: number; h: number; side?: "left" | "right"; id?: string }) {
    const w = 12;
    const rx = side === "left" ? x - w : x;
    return (
        <g className="text-muted-foreground">
            <rect x={rx} y={y} width={w} height={h} fill={`url(#${id}-hatch)`} />
            <line x1={x} y1={y} x2={x} y2={y + h} stroke="currentColor" strokeWidth={2} />
        </g>
    );
}

/** Pin support (triangle) at (x,y) = contact point. */
export function PinSupport({ x, y, roller = false }: { x: number; y: number; roller?: boolean }) {
    return (
        <g className="text-muted-foreground">
            <path d={`M${x},${y} L${x - 9},${y + 14} L${x + 9},${y + 14} Z`} fill="none" stroke="currentColor" strokeWidth={1.5} />
            {roller ? (
                <>
                    <circle cx={x - 5} cy={y + 18} r={3} fill="none" stroke="currentColor" strokeWidth={1.2} />
                    <circle cx={x + 5} cy={y + 18} r={3} fill="none" stroke="currentColor" strokeWidth={1.2} />
                    <line x1={x - 13} y1={y + 22} x2={x + 13} y2={y + 22} stroke="currentColor" strokeWidth={1.2} />
                </>
            ) : (
                <line x1={x - 13} y1={y + 15} x2={x + 13} y2={y + 15} stroke="currentColor" strokeWidth={1.2} />
            )}
        </g>
    );
}

/** Standard frame for a diagram. */
export function DiagramSvg({ w, h, label, children, id = "d" }: {
    w: number; h: number; label: string; children: React.ReactNode; id?: string;
}) {
    return (
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto text-foreground" role="img" aria-label={label}>
            <Defs id={id} />
            {children}
        </svg>
    );
}

/** Body fill/stroke classes for solid parts. */
export const BODY = "fill-cyan-500/10 stroke-current";
export const BODY_DARK = "fill-cyan-500/25 stroke-current";
