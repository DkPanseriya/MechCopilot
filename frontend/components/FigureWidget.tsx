"use client";

import type { FigureSpec } from "@/types/uiSpec";
import { BlockMath } from "react-katex";
import "katex/dist/katex.min.css";
import { Shapes } from "lucide-react";

// Annotated engineering diagrams, authored once. The model only references a
// figure_id; it never draws. Colors use theme tokens so both themes read well.

function ShaftBendingTorsion() {
    return (
        <svg viewBox="0 0 460 240" className="w-full h-auto" role="img" aria-label="Shaft under combined bending and torsion">
            {/* wall */}
            <rect x="20" y="70" width="18" height="90" className="fill-muted" stroke="currentColor" strokeWidth="1" />
            <g className="text-muted-foreground" stroke="currentColor" strokeWidth="1">
                {[78, 96, 114, 132, 150].map((y) => <line key={y} x1="20" y1={y} x2="10" y2={y + 8} />)}
            </g>
            {/* shaft */}
            <rect x="38" y="100" width="300" height="30" rx="4" className="fill-cyan-500/15" stroke="currentColor" strokeWidth="1.5" />
            <ellipse cx="338" cy="115" rx="8" ry="15" className="fill-cyan-500/25" stroke="currentColor" strokeWidth="1.5" />
            {/* transverse load F (bending) */}
            <line x1="338" y1="60" x2="338" y2="100" className="text-rose-500" stroke="currentColor" strokeWidth="2" markerEnd="url(#arrow)" />
            <text x="345" y="66" className="fill-rose-500" fontSize="13" fontStyle="italic">F</text>
            {/* torque T (torsion) — circular arrow */}
            <path d="M 300 90 A 22 22 0 1 1 298 92" fill="none" className="text-amber-500" stroke="currentColor" strokeWidth="2" markerEnd="url(#arrow)" />
            <text x="286" y="78" className="fill-amber-500" fontSize="13" fontStyle="italic">T</text>
            {/* length dim */}
            <line x1="38" y1="150" x2="338" y2="150" className="text-muted-foreground" stroke="currentColor" strokeWidth="0.75" markerStart="url(#tick)" markerEnd="url(#tick)" />
            <text x="188" y="164" textAnchor="middle" className="fill-muted-foreground" fontSize="11" fontStyle="italic">L</text>
            {/* diameter */}
            <text x="352" y="118" className="fill-muted-foreground" fontSize="11" fontStyle="italic">d</text>

            {/* stress element at outer fibre */}
            <g transform="translate(360 150)">
                <rect x="0" y="0" width="60" height="60" className="fill-background" stroke="currentColor" strokeWidth="1.5" />
                {/* sigma_b arrows (normal, horizontal) */}
                <line x1="-16" y1="30" x2="0" y2="30" className="text-rose-500" stroke="currentColor" strokeWidth="2" markerEnd="url(#arrow)" />
                <line x1="76" y1="30" x2="60" y2="30" className="text-rose-500" stroke="currentColor" strokeWidth="2" markerEnd="url(#arrow)" />
                <text x="30" y="-6" textAnchor="middle" className="fill-rose-500" fontSize="11">σb</text>
                {/* tau arrows (shear, vertical edges) */}
                <line x1="0" y1="-10" x2="60" y2="-10" className="text-amber-500" stroke="currentColor" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <text x="72" y="40" className="fill-amber-500" fontSize="11">τt</text>
            </g>

            <defs>
                <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor" /></marker>
                <marker id="tick" markerWidth="6" markerHeight="8" refX="3" refY="4" orient="auto"><line x1="3" y1="0" x2="3" y2="8" stroke="currentColor" strokeWidth="1" /></marker>
            </defs>
        </svg>
    );
}

function StressElement() {
    return (
        <svg viewBox="0 0 220 200" className="w-full h-auto max-w-[260px] mx-auto" role="img" aria-label="2D stress element">
            <rect x="70" y="60" width="80" height="80" className="fill-cyan-500/10" stroke="currentColor" strokeWidth="1.5" />
            <line x1="40" y1="100" x2="70" y2="100" className="text-rose-500" stroke="currentColor" strokeWidth="2" markerEnd="url(#a2)" />
            <line x1="180" y1="100" x2="150" y2="100" className="text-rose-500" stroke="currentColor" strokeWidth="2" markerEnd="url(#a2)" />
            <text x="30" y="104" className="fill-rose-500" fontSize="12">σx</text>
            <line x1="110" y1="30" x2="110" y2="60" className="text-rose-500" stroke="currentColor" strokeWidth="2" markerEnd="url(#a2)" />
            <text x="116" y="34" className="fill-rose-500" fontSize="12">σy</text>
            <line x1="70" y1="50" x2="150" y2="50" className="text-amber-500" stroke="currentColor" strokeWidth="1.5" markerEnd="url(#a2)" />
            <text x="150" y="150" className="fill-amber-500" fontSize="12">τxy</text>
            <defs><marker id="a2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor" /></marker></defs>
        </svg>
    );
}

const FIGURES: Record<string, { render: () => React.ReactNode; formulas: string[] }> = {
    shaft_bending_torsion: {
        render: ShaftBendingTorsion,
        formulas: [
            "\\sigma_b = \\frac{32 M}{\\pi d^3}",
            "\\tau_t = \\frac{16 T}{\\pi d^3}",
            "\\sigma' = \\sqrt{\\sigma_b^2 + 3\\tau_t^2}",
        ],
    },
    stress_element: { render: StressElement, formulas: ["\\sigma_{1,2} = \\frac{\\sigma_x+\\sigma_y}{2} \\pm \\sqrt{\\left(\\frac{\\sigma_x-\\sigma_y}{2}\\right)^2 + \\tau_{xy}^2}"] },
};

export default function FigureWidget({ spec }: { spec: FigureSpec }) {
    const fig = FIGURES[spec.figure_id];
    return (
        <div className="bg-card/95 border border-border rounded-2xl p-6 shadow-xl w-full max-w-lg my-4">
            <div className="flex items-center gap-2 mb-3 border-b border-border pb-3">
                <Shapes className="text-cyan-500" size={18} />
                <h3 className="text-base font-bold text-foreground">{spec.title}</h3>
            </div>
            {fig ? (
                <>
                    <div className="bg-muted/30 rounded-xl p-4 border border-border/50">{fig.render()}</div>
                    {spec.caption && <p className="text-muted-foreground text-xs italic mt-2">{spec.caption}</p>}
                    <div className="mt-4 space-y-2">
                        {fig.formulas.map((f, i) => (
                            <div key={i} className="bg-muted/40 rounded-lg px-3 py-2 overflow-x-auto"><BlockMath math={f} /></div>
                        ))}
                    </div>
                </>
            ) : (
                <p className="text-muted-foreground text-sm">No diagram available for &quot;{spec.figure_id}&quot;.</p>
            )}
            {spec.suggestions && spec.suggestions.length > 0 && (
                <ul className="mt-4 pt-3 border-t border-border space-y-1.5">
                    {spec.suggestions.map((s, i) => (
                        <li key={i} className="text-xs text-muted-foreground flex gap-2"><span className="text-amber-500">•</span>{s}</li>
                    ))}
                </ul>
            )}
        </div>
    );
}
