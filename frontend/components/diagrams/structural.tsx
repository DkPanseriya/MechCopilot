"use client";

// Structural diagrams: springs, welds, columns, pressure vessels, fatigue.
// Schematic (not to scale) but labelled with the live values from the backend.

import { useId, type ReactElement } from "react";
import { Arrow, BODY, DiagramComponent, DiagramSvg, Dim, MomentArrow, PinSupport, Tag, Wall } from "./primitives";

const num = (v: any, fallback = 0): number => {
    const n = typeof v === "number" ? v : parseFloat(String(v ?? ""));
    return isFinite(n) ? n : fallback;
};
const useSvgId = () => useId().replace(/:/g, "");

// --------------------------------------------------------------------------
// Compression spring between two plates
// --------------------------------------------------------------------------
const CompressionSpring: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ok = params.ok !== false;
    const ratio = Math.min(1, Math.max(0.25, num(params.ratio, 0.8)));
    const x0 = 70, Lfree = 360, y0 = 105, half = 34;
    const L = Lfree * ratio;
    const coils = Math.min(14, Math.max(3, Math.round(num(params.Na, 6)))) + 2;
    const pts: string[] = [];
    const segs = coils * 2;
    for (let i = 0; i <= segs; i++) {
        const x = x0 + 6 + ((L - 12) * i) / segs;
        const y = i === 0 || i === segs ? y0 : y0 + (i % 2 ? -half : half);
        pts.push(`${x.toFixed(1)},${y}`);
    }
    return (
        <DiagramSvg w={560} h={235} label="Helical compression spring under load" id={id}>
            <Wall x={x0} y={y0 - 55} h={110} id={id} />
            {/* free-length ghost */}
            <line x1={x0 + Lfree} y1={y0 - 50} x2={x0 + Lfree} y2={y0 + 50} stroke="currentColor"
                strokeDasharray="4 4" className="text-muted-foreground/60" strokeWidth={1.5} />
            <text x={x0 + Lfree + 4} y={y0 - 54} className="fill-muted-foreground" fontSize={10}>free</text>
            <polyline points={pts.join(" ")} fill="none" stroke="currentColor" strokeWidth={3.2}
                strokeLinejoin="round" className="text-cyan-500" />
            {/* moving plate */}
            <rect x={x0 + L} y={y0 - 50} width={8} height={100} className={BODY} strokeWidth={1.5} />
            <Arrow x1={x0 + L + 70} y1={y0} x2={x0 + L + 12} y2={y0} label={`F ${params.F ?? ""}`} id={id} dx={-30} dy={-12} />

            <Dim x1={x0} y1={y0 + 70} x2={x0 + L} y2={y0 + 70} label={`L = ${params.L ?? "–"} mm`} id={id} />
            <Dim x1={x0} y1={y0 + 96} x2={x0 + Lfree} y2={y0 + 96} label={`L0 = ${params.L0 ?? "–"} mm`} id={id} />
            <Dim x1={x0 + 30} y1={y0 - half} x2={x0 + 30} y2={y0 + half} label={`Ø${params.OD ?? ""}`} id={id} />

            <Tag x={430} y={30} text={`d = ${params.d ?? "–"} mm, D = ${params.D ?? "–"} mm`} />
            <Tag x={430} y={48} text={`Na = ${params.Na ?? "–"}, Ls = ${params.Ls ?? "–"} mm`} />
            <Tag x={430} y={66} text={`k = ${params.k ?? "–"}`} />
            <Tag x={430} y={84} text={`τ = ${params.tau ?? "–"}`} tone="load" />
            <Tag x={430} y={102} text={`n = ${params.n ?? "–"}`} tone={ok ? "ok" : "bad"} />
        </DiagramSvg>
    );
};

// --------------------------------------------------------------------------
// Torsion spring, end view
// --------------------------------------------------------------------------
const TorsionSpring: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ok = params.ok !== false;
    const cx = 210, cy = 120, R = 56;
    const ang = Math.min(Math.max(num(params.angle_deg, 30), 0), 300);
    const legLen = 120;
    const a0 = -20; // free-leg angle (deg, screen coords)
    const a1 = a0 - ang;
    const rad = (a: number) => (a * Math.PI) / 180;
    const leg = (a: number) => {
        const sx = cx + R * Math.cos(rad(a)), sy = cy + R * Math.sin(rad(a));
        return { sx, sy, ex: sx + legLen * Math.cos(rad(a)), ey: sy + legLen * Math.sin(rad(a)) };
    };
    const free = leg(a0), loaded = leg(a1);
    return (
        <DiagramSvg w={560} h={250} label="Helical torsion spring, end view" id={id}>
            <circle cx={cx} cy={cy} r={R} fill="none" stroke="currentColor" strokeWidth={7} className="text-cyan-500/70" />
            <circle cx={cx} cy={cy} r={R - 16} fill="none" stroke="currentColor" strokeDasharray="4 3" className="text-muted-foreground" strokeWidth={1.2} />
            <text x={cx} y={cy + 4} textAnchor="middle" className="fill-muted-foreground" fontSize={10}>arbor</text>
            {/* fixed leg */}
            <line x1={cx - R} y1={cy} x2={cx - R - legLen} y2={cy} stroke="currentColor" strokeWidth={5} className="text-cyan-500" strokeLinecap="round" />
            <PinSupport x={cx - R - legLen + 6} y={cy + 3} />
            {/* unloaded ghost and loaded leg */}
            <line x1={free.sx} y1={free.sy} x2={free.ex} y2={free.ey} stroke="currentColor" strokeWidth={3} strokeDasharray="6 4" className="text-muted-foreground/60" />
            <line x1={loaded.sx} y1={loaded.sy} x2={loaded.ex} y2={loaded.ey} stroke="currentColor" strokeWidth={5} className="text-cyan-500" strokeLinecap="round" />
            <MomentArrow cx={cx} cy={cy} r={R + 26} label={`M ${params.M ?? ""}`} id={id} ccw />
            <Tag x={loaded.ex + 6} y={loaded.ey} text={`θ = ${params.angle ?? "–"}`} tone="moment" />

            <Tag x={400} y={40} text={`d = ${params.d ?? "–"} mm`} />
            <Tag x={400} y={58} text={`D = ${params.D ?? "–"} mm`} />
            <Tag x={400} y={76} text={`Nb = ${params.Nb ?? "–"}`} />
            <Tag x={400} y={94} text={`legs ${params.l1 ?? "–"} / ${params.l2 ?? "–"} mm`} />
            <Tag x={400} y={124} text={`σ = ${params.sigma ?? "–"}`} tone="load" />
            <Tag x={400} y={142} text={`n = ${params.n ?? "–"}`} tone={ok ? "ok" : "bad"} />
        </DiagramSvg>
    );
};

// --------------------------------------------------------------------------
// Fillet weld group
// --------------------------------------------------------------------------
const FilletWeld: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ok = params.ok !== false;
    const pattern: string = params.pattern || "two_vertical";
    const b = num(params.b, 60), d = num(params.d, 100), e = num(params.e, 0);
    const span = Math.max(b, d, 1);
    const S = 150 / span; // px per mm
    const W = pattern === "line" ? 0 : pattern === "circle" ? d * S : b * S;
    const H = d * S;
    const cx = 170, cy = 125;
    // Geometry bounding box relative to the centroid.
    const xbarPx = pattern === "c_shape" ? num(params.xbar_frac, 0) * W : W / 2;
    const left = cx - xbarPx, top = cy - H / 2;
    const weld = "text-violet-500";
    const lines: ReactElement[] = [];
    const L = (x1: number, y1: number, x2: number, y2: number, k: string) =>
        lines.push(<line key={k} x1={x1} y1={y1} x2={x2} y2={y2} stroke="currentColor" strokeWidth={7} strokeLinecap="round" className={weld} />);
    if (pattern === "line") L(cx, top, cx, top + H, "a");
    if (pattern === "two_vertical") { L(left, top, left, top + H, "a"); L(left + W, top, left + W, top + H, "b"); }
    if (pattern === "two_horizontal") { L(left, top, left + W, top, "a"); L(left, top + H, left + W, top + H, "b"); }
    if (pattern === "c_shape") { L(left, top, left, top + H, "a"); L(left, top, left + W, top, "b"); L(left, top + H, left + W, top + H, "c"); }
    if (pattern === "box") {
        L(left, top, left + W, top, "a"); L(left + W, top, left + W, top + H, "b");
        L(left + W, top + H, left, top + H, "c"); L(left, top + H, left, top, "d");
    }
    const ePx = Math.min(e * S, 520 - cx - 30);
    const crit = { x: cx + num(params.crit_x, 0) * 150, y: cy - num(params.crit_y, 0) * 150 };
    const inPlane = params.case !== "out_of_plane";
    return (
        <DiagramSvg w={560} h={260} label="Fillet weld group with eccentric load" id={id}>
            {/* attached plate */}
            {pattern === "circle"
                ? <circle cx={cx} cy={cy} r={H / 2} className={BODY} strokeWidth={1} />
                : <rect x={pattern === "line" ? cx - 40 : left} y={top} width={pattern === "line" ? 40 : W} height={H} className={BODY} strokeWidth={1} />}
            {pattern === "circle" && <circle cx={cx} cy={cy} r={H / 2} fill="none" stroke="currentColor" strokeWidth={7} className={weld} />}
            {lines}
            {/* centroid */}
            <g className="text-foreground">
                <circle cx={cx} cy={cy} r={5} fill="none" stroke="currentColor" strokeWidth={1.2} />
                <line x1={cx - 9} y1={cy} x2={cx + 9} y2={cy} stroke="currentColor" strokeWidth={1} />
                <line x1={cx} y1={cy - 9} x2={cx} y2={cy + 9} stroke="currentColor" strokeWidth={1} />
            </g>
            {/* critical point */}
            <circle cx={crit.x} cy={crit.y} r={5} className="fill-rose-500" />
            {/* load */}
            {inPlane ? (
                <>
                    <line x1={cx} y1={cy} x2={cx + ePx} y2={cy} stroke="currentColor" strokeDasharray="4 3" className="text-muted-foreground" />
                    <Arrow x1={cx + ePx} y1={cy - 70} x2={cx + ePx} y2={cy - 4} label={`V ${params.V ?? ""}`} id={id} dx={6} dy={8} />
                    {ePx > 20 && <Dim x1={cx} y1={cy + H / 2 + 26} x2={cx + ePx} y2={cy + H / 2 + 26} label={`e = ${params.e} mm`} id={id} />}
                </>
            ) : (
                <g className="text-rose-500">
                    <circle cx={cx + Math.max(ePx, 40)} cy={cy} r={10} fill="none" stroke="currentColor" strokeWidth={2} />
                    <line x1={cx + Math.max(ePx, 40) - 7} y1={cy - 7} x2={cx + Math.max(ePx, 40) + 7} y2={cy + 7} stroke="currentColor" strokeWidth={2} />
                    <line x1={cx + Math.max(ePx, 40) - 7} y1={cy + 7} x2={cx + Math.max(ePx, 40) + 7} y2={cy - 7} stroke="currentColor" strokeWidth={2} />
                    <text x={cx + Math.max(ePx, 40) + 14} y={cy - 12} className="fill-rose-500" fontSize={12} fontWeight={600}>V {params.V} (out of plane, lever {params.e} mm)</text>
                </g>
            )}
            {pattern !== "circle" && pattern !== "line" && (
                <Dim x1={left} y1={top - 18} x2={left + W} y2={top - 18} label={`b = ${params.b} mm`} id={id} />
            )}
            <Dim x1={(pattern === "line" ? cx : left) - 26} y1={top} x2={(pattern === "line" ? cx : left) - 26} y2={top + H}
                label={pattern === "circle" ? `Ø${params.d}` : `d = ${params.d}`} id={id} />

            <Tag x={360} y={190} text={`leg h = ${params.h ?? "–"} mm`} />
            <Tag x={360} y={208} text={`τ = ${params.tau ?? "–"}`} tone="load" />
            <Tag x={360} y={226} text={`utilisation ${params.util ?? "–"}`} tone={ok ? "ok" : "bad"} />
            <Tag x={360} y={244} text="● critical point" tone="bad" />
        </DiagramSvg>
    );
};

// --------------------------------------------------------------------------
// Column with end conditions
// --------------------------------------------------------------------------
const FixedEnd = ({ x, y, up, id }: { x: number; y: number; up: boolean; id: string }) => (
    <g className="text-muted-foreground">
        <rect x={x - 34} y={up ? y - 12 : y} width={68} height={12} fill={`url(#${id}-hatch)`} />
        <line x1={x - 34} y1={y} x2={x + 34} y2={y} stroke="currentColor" strokeWidth={2} />
    </g>
);

const ColumnBuckling: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ok = params.ok !== false;
    const ends: string = params.ends || "pinned_pinned";
    const x = 160, yb = 225, yt = 45;
    const bottomFixed = ends !== "pinned_pinned";
    const topKind = ends.startsWith("fixed_fixed") ? "fixed" : ends === "fixed_free" ? "free" : "pinned";
    // Buckled mode shape (lateral offset as function of s in [0,1] from bottom).
    const shape = (s: number) => {
        if (ends === "pinned_pinned") return Math.sin(Math.PI * s);
        if (ends === "fixed_free") return 1 - Math.cos((Math.PI / 2) * s);
        if (ends.startsWith("fixed_fixed")) return (1 - Math.cos(2 * Math.PI * s)) / 2;
        return Math.sin(1.43 * Math.PI * s) * (1 - s) * 1.6; // fixed–pinned approx.
    };
    const pts = Array.from({ length: 41 }, (_, i) => {
        const s = i / 40;
        return `${(x + 34 * shape(s)).toFixed(1)},${(yb - (yb - yt) * s).toFixed(1)}`;
    }).join(" ");
    return (
        <DiagramSvg w={560} h={255} label="Column with end conditions and buckled shape" id={id}>
            {bottomFixed ? <FixedEnd x={x} y={yb} up={false} id={id} /> : <PinSupport x={x} y={yb} />}
            {topKind === "fixed" && <FixedEnd x={x} y={yt} up id={id} />}
            {topKind === "pinned" && (
                <g className="text-muted-foreground">
                    <circle cx={x} cy={yt} r={5} fill="none" stroke="currentColor" strokeWidth={1.5} />
                    <text x={x - 44} y={yt + 4} className="fill-muted-foreground" fontSize={10}>guided</text>
                </g>
            )}
            <rect x={x - 7} y={yt} width={14} height={yb - yt} className={BODY} strokeWidth={1.5} />
            <polyline points={pts} fill="none" stroke="currentColor" strokeDasharray="6 4" strokeWidth={2} className="text-amber-500" />
            <Arrow x1={x} y1={yt - 40} x2={x} y2={yt - (topKind === "fixed" ? 14 : 2)} label={`P ${params.P ?? ""}`} id={id} dx={10} dy={10} />
            <Dim x1={x - 60} y1={yb} x2={x - 60} y2={yt} label={`L ${params.L} mm`} id={id} offset={-70} />

            <Tag x={300} y={60} text={`K = ${params.K ?? "–"}, Le = ${params.Le ?? "–"} mm`} />
            <Tag x={300} y={80} text={`Le/k = ${params.lam ?? "–"}`} />
            <Tag x={300} y={100} text={`${params.regime ?? ""}`} tone="moment" />
            <Tag x={300} y={128} text={`Pcr = ${params.Pcr ?? "–"}`} />
            <Tag x={300} y={148} text={`n = ${params.n ?? "–"}`} tone={ok ? "ok" : "bad"} />
            <text x={300} y={180} className="fill-muted-foreground" fontSize={10}>dashed: first buckling mode</text>
        </DiagramSvg>
    );
};

// --------------------------------------------------------------------------
// Pressure vessel section
// --------------------------------------------------------------------------
const PressureVessel: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ok = params.ok !== false;
    const cx = 160, cy = 128, ro = 92;
    const tf = Math.min(0.6, Math.max(0.09, num(params.t_frac, 0.1)));
    const ri = ro * (1 - tf);
    const arrows = Array.from({ length: 8 }, (_, i) => (i * Math.PI) / 4 + Math.PI / 8);
    return (
        <DiagramSvg w={560} h={255} label="Pressure vessel wall section" id={id}>
            <circle cx={cx} cy={cy} r={(ro + ri) / 2} fill="none" stroke="currentColor" strokeWidth={ro - ri}
                className="text-cyan-500/25" />
            <circle cx={cx} cy={cy} r={ro} fill="none" stroke="currentColor" strokeWidth={1.5} />
            <circle cx={cx} cy={cy} r={ri} fill="none" stroke="currentColor" strokeWidth={1.5} />
            {params.pi && arrows.map((a, i) => (
                <Arrow key={`i${i}`} id={id} width={1.6}
                    x1={cx + ri * 0.45 * Math.cos(a)} y1={cy + ri * 0.45 * Math.sin(a)}
                    x2={cx + (ri - 3) * Math.cos(a)} y2={cy + (ri - 3) * Math.sin(a)} />
            ))}
            {params.po && arrows.map((a, i) => (
                <Arrow key={`o${i}`} id={id} width={1.6} color="text-violet-500"
                    x1={cx + (ro + 26) * Math.cos(a)} y1={cy + (ro + 26) * Math.sin(a)}
                    x2={cx + (ro + 3) * Math.cos(a)} y2={cy + (ro + 3) * Math.sin(a)} />
            ))}
            <Dim x1={cx - ri} y1={cy} x2={cx + ri} y2={cy} label={`Di = ${params.Di} mm`} id={id} />
            <Dim x1={cx + ri} y1={cy - 30} x2={cx + ro} y2={cy - 30} label={`t = ${params.t}`} id={id} offset={-4} />

            <Tag x={330} y={50} text={params.shape === "sphere" ? "Sphere (section)" : "Cylinder (cross-section)"} />
            {params.pi && <Tag x={330} y={72} text={`pi = ${params.pi}`} tone="load" />}
            {params.po && <Tag x={330} y={90} text={`po = ${params.po}`} tone="moment" />}
            <Tag x={330} y={118} text={`σt (bore) = ${params.st ?? "–"}`} />
            <Tag x={330} y={136} text={`σ' max = ${params.vm ?? "–"}`} />
            <Tag x={330} y={154} text={`n = ${params.n ?? "–"}`} tone={ok ? "ok" : "bad"} />
        </DiagramSvg>
    );
};

// --------------------------------------------------------------------------
// Fatigue: stress–time waveform
// --------------------------------------------------------------------------
const FatigueLife: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ok = params.ok !== false;
    const amp = Math.max(0.05, Math.min(1, num(params.ratio, 0.5)));
    const mean = Math.max(-1, Math.min(1, num(params.mean_frac, 0.5)));
    const x0 = 60, x1 = 420, y0 = 128, S = 85; // y0 = zero stress line; S px per unit
    const yOf = (v: number) => y0 - v * S * 0.9;
    const pts = Array.from({ length: 121 }, (_, i) => {
        const t = i / 120;
        return `${(x0 + (x1 - x0) * t).toFixed(1)},${yOf(mean + amp * Math.sin(t * 6 * Math.PI)).toFixed(1)}`;
    }).join(" ");
    const sym = params.shear ? "τ" : "σ";
    return (
        <DiagramSvg w={560} h={250} label="Fluctuating stress versus time" id={id}>
            <line x1={x0} y1={20} x2={x0} y2={236} stroke="currentColor" className="text-muted-foreground/70" />
            <line x1={x0} y1={y0} x2={x1 + 10} y2={y0} stroke="currentColor" className="text-muted-foreground/70" />
            <text x={x1 + 12} y={y0 + 4} className="fill-muted-foreground" fontSize={10}>t</text>
            <text x={x0 - 8} y={18} textAnchor="end" className="fill-muted-foreground" fontSize={11}>{sym}</text>
            <line x1={x0} y1={yOf(mean)} x2={x1} y2={yOf(mean)} stroke="currentColor" strokeDasharray="6 4" className="text-amber-500" />
            <line x1={x0} y1={yOf(mean + amp)} x2={x1} y2={yOf(mean + amp)} stroke="currentColor" strokeDasharray="2 4" className="text-muted-foreground" />
            <line x1={x0} y1={yOf(mean - amp)} x2={x1} y2={yOf(mean - amp)} stroke="currentColor" strokeDasharray="2 4" className="text-muted-foreground" />
            <polyline points={pts} fill="none" stroke="currentColor" strokeWidth={2.4} className="text-cyan-500" />
            <Dim x1={x1 + 30} y1={yOf(mean)} x2={x1 + 30} y2={yOf(mean + amp)} label={`${sym}a`} id={id} />
            <Tag x={x0 + 6} y={yOf(mean + amp) - 6} text={`${sym}max ${params.smax ?? ""}`} />
            <Tag x={x0 + 6} y={yOf(mean - amp) + 16} text={`${sym}min ${params.smin ?? ""}`} />
            <Tag x={x1 - 4} y={yOf(mean) - 6} anchor="end" text={`${sym}m ${params.sm ?? ""}`} tone="moment" />

            <Tag x={455} y={60} text={`${sym}a = ${params.sa ?? "–"}`} />
            <Tag x={455} y={78} text={`R = ${params.R ?? "–"}`} />
            <Tag x={455} y={106} text={`nf = ${params.nf ?? "–"}`} tone={ok ? "ok" : "bad"} />
            <Tag x={455} y={124} text={`life ${params.life ?? "–"}`} />
        </DiagramSvg>
    );
};

// --------------------------------------------------------------------------
// Stress concentration features
// --------------------------------------------------------------------------
const StressConcentration: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ok = params.ok !== false;
    const geo: string = params.geometry || "stepped";
    const load: string = params.load || "bending";
    const cy = 120;
    const loadArrows = () => {
        if (load === "tension") return (<>
            <Arrow x1={70} y1={cy} x2={20} y2={cy} label="F" id={id} dx={-10} dy={-10} />
            <Arrow x1={420} y1={cy} x2={470} y2={cy} label="F" id={id} dx={10} dy={-10} />
        </>);
        if (load === "torsion") return (<>
            <MomentArrow cx={52} cy={cy} r={22} label="T" id={id} color="text-violet-500" />
            <MomentArrow cx={448} cy={cy} r={22} id={id} color="text-violet-500" ccw />
        </>);
        return (<>
            <MomentArrow cx={52} cy={cy} r={22} label="M" id={id} ccw />
            <MomentArrow cx={448} cy={cy} r={22} id={id} />
        </>);
    };
    if (geo === "plate_hole") {
        return (
            <DiagramSvg w={560} h={240} label="Plate with a central hole in tension" id={id}>
                <rect x={110} y={50} width={260} height={140} className={BODY} strokeWidth={1.5} />
                <circle cx={240} cy={120} r={34} className="fill-background stroke-current" strokeWidth={1.5} />
                <circle cx={240} cy={86} r={4} className="fill-rose-500" />
                <circle cx={240} cy={154} r={4} className="fill-rose-500" />
                <Arrow x1={110} y1={120} x2={60} y2={120} label="F" id={id} dx={-14} dy={-10} />
                <Arrow x1={370} y1={120} x2={420} y2={120} label="F" id={id} dx={10} dy={-10} />
                <Dim x1={240 - 34} y1={210} x2={240 + 34} y2={210} label={`d = ${params.dh} mm`} id={id} />
                <Dim x1={90} y1={50} x2={90} y2={190} label={`W ${params.W}`} id={id} offset={-50} />
                <Tag x={440} y={60} text={`Kt = ${params.kt ?? "–"}`} />
                <Tag x={440} y={80} text={`Kf = ${params.kf ?? "–"}`} tone={ok ? "ok" : "bad"} />
                <text x={440} y={104} className="fill-muted-foreground" fontSize={10}>● peak stress</text>
            </DiagramSvg>
        );
    }
    const Dh = 120, dh = Math.max(40, Math.min(110, Dh * (num(params.d, 30) / Math.max(num(params.D, 38), 1))));
    const r = Math.min(26, Math.max(6, (num(params.r, 3) / Math.max(num(params.d, 30), 1)) * 140));
    if (geo === "groove") {
        const gx = 245, depth = (Dh - dh) / 2;
        const path = `M70,${cy - Dh / 2} L${gx - r},${cy - Dh / 2} A${r},${Math.max(depth, 1)} 0 0 0 ${gx + r},${cy - Dh / 2} L420,${cy - Dh / 2}
            L420,${cy + Dh / 2} L${gx + r},${cy + Dh / 2} A${r},${Math.max(depth, 1)} 0 0 0 ${gx - r},${cy + Dh / 2} L70,${cy + Dh / 2} Z`;
        return (
            <DiagramSvg w={560} h={240} label="Round bar with a U-groove" id={id}>
                <path d={path} className={BODY} strokeWidth={1.5} />
                <circle cx={gx} cy={cy - dh / 2} r={4} className="fill-rose-500" />
                <circle cx={gx} cy={cy + dh / 2} r={4} className="fill-rose-500" />
                {loadArrows()}
                <Dim x1={110} y1={cy - Dh / 2} x2={110} y2={cy + Dh / 2} label={`D ${params.D}`} id={id} />
                <Dim x1={gx + 40} y1={cy - dh / 2} x2={gx + 40} y2={cy + dh / 2} label={`d ${params.d}`} id={id} />
                <Tag x={gx} y={cy - Dh / 2 - 12} anchor="middle" text={`r = ${params.r} mm`} />
                <Tag x={470} y={60} text={`Kt = ${params.kt ?? "–"}`} />
                <Tag x={470} y={80} text={`Kf = ${params.kf ?? "–"}`} tone={ok ? "ok" : "bad"} />
            </DiagramSvg>
        );
    }
    const xs = 240; // step location
    const path = `M70,${cy - Dh / 2} L${xs},${cy - Dh / 2} L${xs},${cy - dh / 2 - r} A${r},${r} 0 0 0 ${xs + r},${cy - dh / 2} L420,${cy - dh / 2}
        L420,${cy + dh / 2} L${xs + r},${cy + dh / 2} A${r},${r} 0 0 0 ${xs},${cy + dh / 2 + r} L${xs},${cy + Dh / 2} L70,${cy + Dh / 2} Z`;
    return (
        <DiagramSvg w={560} h={240} label="Stepped round bar with a shoulder fillet" id={id}>
            <path d={path} className={BODY} strokeWidth={1.5} />
            <circle cx={xs + r * 0.3} cy={cy - dh / 2 - r * 0.3} r={4} className="fill-rose-500" />
            <circle cx={xs + r * 0.3} cy={cy + dh / 2 + r * 0.3} r={4} className="fill-rose-500" />
            {loadArrows()}
            <Dim x1={120} y1={cy - Dh / 2} x2={120} y2={cy + Dh / 2} label={`D ${params.D}`} id={id} />
            <Dim x1={370} y1={cy - dh / 2} x2={370} y2={cy + dh / 2} label={`d ${params.d}`} id={id} />
            <Tag x={xs + r + 6} y={cy - dh / 2 - 8} text={`r = ${params.r} mm`} />
            <Tag x={470} y={60} text={`Kt = ${params.kt ?? "–"}`} />
            <Tag x={470} y={80} text={`Kf = ${params.kf ?? "–"}`} tone={ok ? "ok" : "bad"} />
            <text x={470} y={104} className="fill-muted-foreground" fontSize={10}>● peak stress</text>
        </DiagramSvg>
    );
};

export const DIAGRAMS: Record<string, DiagramComponent> = {
    compression_spring: CompressionSpring,
    torsion_spring: TorsionSpring,
    fillet_weld: FilletWeld,
    column_buckling: ColumnBuckling,
    pressure_vessel: PressureVessel,
    fatigue_life: FatigueLife,
    stress_concentration: StressConcentration,
};
