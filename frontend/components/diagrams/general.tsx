"use client";

// REFERENCE diagram — copy this structure for new diagrams.
// Read display-ready values from `params` (backend result.diagram.params),
// keep geometry schematic (not to scale) but label it with the real numbers.

import { useId } from "react";
import { Arrow, BODY, DiagramComponent, DiagramSvg, Dim, MomentArrow, Tag, Wall } from "./primitives";

const RoundBarCombined: DiagramComponent = ({ params }) => {
    const id = useId().replace(/:/g, "");
    const hollow = Number(params.d) > 0;
    const ok = params.ok !== false;
    const y0 = 110, h = 44, xL = 60, xR = 330;

    return (
        <DiagramSvg w={560} h={230} label="Round bar under axial load, bending and torsion" id={id}>
            <Wall x={xL} y={y0 - h / 2 - 22} h={h + 44} id={id} />
            <rect x={xL} y={y0 - h / 2} width={xR - xL} height={h} rx={3} className={BODY} strokeWidth={1.5} />
            {hollow && (
                <rect x={xL} y={y0 - h / 5} width={xR - xL} height={(2 * h) / 5} fill="none"
                    stroke="currentColor" strokeWidth={1} strokeDasharray="5 4" className="text-muted-foreground" />
            )}
            <line x1={xL - 20} y1={y0} x2={xR + 70} y2={y0} stroke="currentColor" strokeDasharray="10 3 2 3"
                strokeWidth={0.8} className="text-muted-foreground" />

            <Arrow x1={xR + 8} y1={y0} x2={xR + 62} y2={y0} label={`F ${params.F ?? ""}`} id={id} dx={-4} dy={-10} />
            <MomentArrow cx={xR - 50} cy={y0 - 52} r={16} label={`M ${params.M ?? ""}`} id={id} />
            <MomentArrow cx={xR + 30} cy={y0 + 48} r={14} label={`T ${params.T ?? ""}`} id={id} color="text-violet-500" ccw />

            <Dim x1={xR - 120} y1={y0 - h / 2} x2={xR - 120} y2={y0 + h / 2} label={`D ${params.D ?? ""} mm`} id={id} />

            {/* cross-section */}
            <g transform={`translate(440 ${y0})`}>
                <circle r={34} className={BODY} strokeWidth={1.5} />
                {hollow && <circle r={14} className="fill-background stroke-current" strokeWidth={1.2} />}
                <circle r={3} className="fill-muted-foreground" />
                <Tag x={0} y={56} anchor="middle" text={hollow ? `Ø${params.D} / Ø${params.d}` : `Ø${params.D}`} />
            </g>

            {/* stress element at worst fibre */}
            <g transform="translate(120 28)">
                <rect x={0} y={0} width={34} height={34} className="fill-background stroke-current" strokeWidth={1.2} />
                <Arrow x1={-16} y1={17} x2={0} y2={17} width={1.6} head={7} color="text-rose-500" />
                <Arrow x1={50} y1={17} x2={34} y2={17} width={1.6} head={7} color="text-rose-500" />
                <Arrow x1={3} y1={-7} x2={31} y2={-7} width={1.4} head={7} color="text-violet-500" />
                <Tag x={58} y={14} text={`σx ${params.s_x ?? ""}`} tone="load" />
                <Tag x={58} y={30} text={`τ ${params.tau ?? ""}`} tone="moment" />
            </g>

            <Tag x={xL + 6} y={214} text={`σ' = ${params.s_vm ?? "–"}`} />
            <Tag x={xL + 150} y={214} text={`n = ${params.n ?? "–"}`} tone={ok ? "ok" : "bad"} />
        </DiagramSvg>
    );
};

export const DIAGRAMS: Record<string, DiagramComponent> = {
    round_bar_combined: RoundBarCombined,
};
