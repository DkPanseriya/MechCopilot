"use client";

// Transmission diagrams: shafts, keys & fits, gears. Schematic (not to scale)
// except where proportions carry meaning (key section, tolerance zones, gears).

import { useId } from "react";
import { Arrow, BODY, BODY_DARK, DiagramComponent, DiagramSvg, Dim, MomentArrow, PinSupport, Tag, Wall } from "./primitives";

const num = (v: any, fallback = 0) => {
    const n = typeof v === "number" ? v : parseFloat(String(v ?? ""));
    return isFinite(n) ? n : fallback;
};

const useSvgId = () => useId().replace(/:/g, "");

// ---------------------------------------------------------------------------
// Shaft fatigue: stepped shaft with a shoulder fillet under bending + torsion
// ---------------------------------------------------------------------------
const ShaftFatigue: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ok = params.ok !== false;
    return (
        <DiagramSvg w={560} h={240} label="Stepped shaft under bending and torsion" id={id}>
            <line x1={30} y1={110} x2={520} y2={110} stroke="currentColor" strokeDasharray="10 3 2 3"
                strokeWidth={0.8} className="text-muted-foreground" />
            <path d="M60,75 H250 V79 A8,8 0 0 0 258,87 H470 V133 H258 A8,8 0 0 0 250,141 V145 H60 Z"
                className={BODY} strokeWidth={1.5} />
            {/* fillet highlight */}
            <circle cx={254} cy={83} r={9} fill="none" stroke="currentColor" strokeWidth={1.4}
                strokeDasharray="3 2" className="text-rose-500" />
            <Tag x={262} y={64} text={`Kf ${params.Kf ?? "–"} · Kfs ${params.Kfs ?? "–"}`} tone="load" />
            <Tag x={262} y={50} text={String(params.feature ?? "")} />

            <MomentArrow cx={40} cy={110} r={20} label="" id={id} ccw />
            <MomentArrow cx={492} cy={110} r={20} label="" id={id} />
            <Tag x={18} y={76} text={`M ${params.Ma ?? ""}`} tone="moment" />
            <MomentArrow cx={430} cy={175} r={14} label={`T ${params.Tm ?? ""}`} id={id} color="text-violet-500" ccw />

            <Dim x1={400} y1={87} x2={400} y2={133} label={`Ø${params.d ?? ""}`} id={id} />
            <text x={150} y={170} textAnchor="middle" className="fill-muted-foreground" fontSize={11}>
                rotating: bending reverses each revolution
            </text>

            <Tag x={60} y={222} text={`Se = ${params.Se ?? "–"}`} />
            <Tag x={230} y={222} text={`n (DE-Goodman) = ${params.n ?? "–"}`} tone={ok ? "ok" : "bad"} />
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// Critical speed: shaft on supports with point masses and first mode shape
// ---------------------------------------------------------------------------
const ShaftCriticalSpeed: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const x0 = 70, x1 = 490, y = 120;
    const span = x1 - x0;
    const support = String(params.support ?? "simply_supported");
    const ok = params.ok !== false;
    const masses: { pos: number; label: string }[] = Array.isArray(params.masses) ? params.masses : [];

    const mode = (t: number) => {
        if (support === "cantilever") return 1 - Math.cos((Math.PI * t) / 2);
        if (support === "fixed_fixed") return (1 - Math.cos(2 * Math.PI * t)) / 2;
        return Math.sin(Math.PI * t);
    };
    const pts = Array.from({ length: 61 }, (_, i) => {
        const t = i / 60;
        return `${i === 0 ? "M" : "L"}${(x0 + t * span).toFixed(1)},${(y - 34 * mode(t)).toFixed(1)}`;
    }).join("");

    return (
        <DiagramSvg w={560} h={230} label="Shaft on supports with masses" id={id}>
            <path d={pts} fill="none" stroke="currentColor" strokeDasharray="5 4" strokeWidth={1.4}
                className="text-cyan-500" />
            <text x={x0 + span / 2} y={y - 44} textAnchor="middle" className="fill-cyan-500" fontSize={10}>first mode</text>
            <rect x={x0} y={y - 6} width={span} height={12} rx={2} className={BODY} strokeWidth={1.4} />

            {support === "simply_supported" && (<><PinSupport x={x0} y={y + 6} /><PinSupport x={x1} y={y + 6} roller /></>)}
            {support === "cantilever" && <Wall x={x0} y={y - 40} h={80} id={id} />}
            {support === "fixed_fixed" && (<><Wall x={x0} y={y - 40} h={80} id={id} /><Wall x={x1} y={y - 40} h={80} side="right" id={id} /></>)}

            {masses.map((m, i) => {
                const mx = x0 + Math.min(Math.max(m.pos, 0), 1) * span;
                return (
                    <g key={i}>
                        <rect x={mx - 7} y={y - 30} width={14} height={60} rx={2} className={BODY_DARK} strokeWidth={1.3} />
                        <Tag x={mx} y={y + 48} anchor="middle" text={m.label} />
                    </g>
                );
            })}

            <Dim x1={x0} y1={y + 70} x2={x1} y2={y + 70} label={`L ${params.L ?? ""} mm · Ø${params.d ?? ""}`} id={id} />
            <Tag x={x0} y={24} text={`n_crit ≈ ${params.n_crit ?? "–"}`} tone={ok ? "ok" : "bad"} />
            <Tag x={x0 + 200} y={24} text={`n_op = ${params.n_op ?? "–"}`} />
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// Parallel key: shaft cross-section with keyway, key and hub (to scale)
// ---------------------------------------------------------------------------
const ParallelKey: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const d = num(params.d, 40), b = num(params.b, 12), h = num(params.h, 8);
    const t1 = num(params.t1, 5), t2 = num(params.t2, 3.3);
    const cx = 230, cy = 125, r = 70, R = 108;
    const s = (2 * r) / d;
    const shaftTop = cy - r;
    const keyBottom = shaftTop + t1 * s;
    const keyTop = keyBottom - h * s;
    const kw = b * s;
    const ok = params.ok !== false;

    return (
        <DiagramSvg w={560} h={250} label="Parallel key in shaft and hub, cross-section" id={id}>
            <circle cx={cx} cy={cy} r={R} className="fill-muted stroke-current" strokeWidth={1.4} />
            {/* hub keyway */}
            <rect x={cx - kw / 2} y={shaftTop - t2 * s} width={kw} height={t2 * s + 2} className="fill-background" />
            <circle cx={cx} cy={cy} r={r} className={BODY} strokeWidth={1.4} />
            {/* shaft keyway */}
            <rect x={cx - kw / 2} y={shaftTop - 1} width={kw} height={t1 * s + 1} className="fill-background" />
            {/* key */}
            <rect x={cx - kw / 2} y={keyTop} width={kw} height={h * s} className="fill-amber-500/30 stroke-current" strokeWidth={1.4} />

            <Arrow x1={cx - kw / 2 - 46} y1={keyBottom - (t1 * s) / 2} x2={cx - kw / 2 - 2} y2={keyBottom - (t1 * s) / 2}
                label={`F ${params.F ?? ""}`} id={id} dx={-6} dy={-8} />
            <Arrow x1={cx + kw / 2 + 46} y1={keyTop + (h * s - t1 * s) / 2} x2={cx + kw / 2 + 2} y2={keyTop + (h * s - t1 * s) / 2}
                id={id} color="text-amber-500" />

            <Dim x1={cx - kw / 2} y1={keyTop - 12} x2={cx + kw / 2} y2={keyTop - 12} label={`b ${b}`} id={id} />
            <Tag x={cx + kw / 2 + 52} y={keyTop + 4} text={`h ${h} · t1 ${t1} · t2 ${t2}`} />
            <Dim x1={cx - r} y1={cy + R + 14} x2={cx + r} y2={cy + R + 14} label={`Ø${params.d ?? ""}`} id={id} />

            <Tag x={400} y={150} text={`τ = ${params.tau ?? "–"}`} />
            <Tag x={400} y={170} text={`p = ${params.p ?? "–"}`} tone="load" />
            <Tag x={400} y={190} text={`n = ${params.n ?? "–"}`} tone={ok ? "ok" : "bad"} />
            <text x={400} y={130} className="fill-muted-foreground" fontSize={11}>hub</text>
            <text x={cx} y={cy + 8} textAnchor="middle" className="fill-muted-foreground" fontSize={11}>shaft</text>
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// ISO fits: tolerance zone diagram (to scale in µm)
// ---------------------------------------------------------------------------
const IsoFits: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const ES = num(params.ES), EI = num(params.EI), es = num(params.es), ei = num(params.ei);
    const y0 = 125;
    const vmax = Math.max(Math.abs(ES), Math.abs(EI), Math.abs(es), Math.abs(ei), 1);
    const k = 85 / vmax;
    const Y = (v: number) => y0 - v * k;
    const zone = (x: number, top: number, bot: number, cls: string, label: string, up: number, lo: number) => (
        <g>
            <rect x={x} y={Y(top)} width={110} height={Math.max(Y(bot) - Y(top), 1.5)} className={cls} strokeWidth={1.4} />
            <text x={x + 55} y={(Y(top) + Y(bot)) / 2 + 4} textAnchor="middle" className="fill-foreground" fontSize={13} fontWeight={600}>{label}</text>
            <text x={x + 116} y={Y(top) + 4} className="fill-muted-foreground" fontSize={11}>{up > 0 ? `+${up}` : up}</text>
            <text x={x + 116} y={Y(bot) + 4} className="fill-muted-foreground" fontSize={11}>{lo > 0 ? `+${lo}` : lo}</text>
        </g>
    );
    return (
        <DiagramSvg w={560} h={250} label="ISO 286 tolerance zone diagram" id={id}>
            <Arrow x1={60} y1={232} x2={60} y2={18} width={1} head={8} color="text-muted-foreground" id={id} />
            <text x={66} y={24} className="fill-muted-foreground" fontSize={10}>µm</text>
            <line x1={50} y1={y0} x2={530} y2={y0} stroke="currentColor" strokeWidth={1.6} className="text-foreground" />
            <text x={526} y={y0 - 6} textAnchor="end" className="fill-foreground" fontSize={11}>0 line · Ø{params.size} mm</text>
            {zone(120, ES, EI, "fill-cyan-500/25 stroke-cyan-500", `${params.hole ?? "hole"}`, ES, EI)}
            {zone(320, es, ei, "fill-amber-500/25 stroke-amber-500", `${params.shaft ?? "shaft"}`, es, ei)}
            <text x={175} y={240} textAnchor="middle" className="fill-cyan-500" fontSize={11}>hole</text>
            <text x={375} y={240} textAnchor="middle" className="fill-amber-500" fontSize={11}>shaft</text>
            <Tag x={300} y={22} anchor="middle" text={String(params.type ?? "")}
                tone={params.type === "Clearance fit" ? "ok" : params.type === "Interference fit" ? "load" : "moment"} />
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// Interference fit: hub on shaft, longitudinal section with contact pressure
// ---------------------------------------------------------------------------
const InterferenceFit: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const d = num(params.d, 40), D = num(params.D, 80), L = num(params.L, 40), di = num(params.di, 0);
    const cy = 120, H = 70;
    const hs = (H * d) / D;
    const hb = (H * di) / D;
    const Lpx = Math.min(Math.max((2 * H * L) / D, 60), 240);
    const hx = 280 - Lpx / 2;
    const ok = params.ok !== false;
    const nArrows = Math.max(3, Math.round(Lpx / 30));
    const xs = Array.from({ length: nArrows }, (_, i) => hx + ((i + 0.5) * Lpx) / nArrows);

    return (
        <DiagramSvg w={560} h={250} label="Hub shrunk on shaft with contact pressure" id={id}>
            <line x1={40} y1={cy} x2={520} y2={cy} stroke="currentColor" strokeDasharray="10 3 2 3" strokeWidth={0.8} className="text-muted-foreground" />
            <rect x={60} y={cy - hs} width={440} height={2 * hs} className={BODY} strokeWidth={1.4} />
            {di > 0 && <rect x={60} y={cy - hb} width={440} height={2 * hb} className="fill-background stroke-current" strokeWidth={1} strokeDasharray="4 3" />}
            <rect x={hx} y={cy - H} width={Lpx} height={H - hs} className={BODY_DARK} strokeWidth={1.4} />
            <rect x={hx} y={cy + hs} width={Lpx} height={H - hs} className={BODY_DARK} strokeWidth={1.4} />
            {xs.map((x, i) => (
                <g key={i}>
                    <Arrow x1={x} y1={cy - hs - 16} x2={x} y2={cy - hs - 1} id={id} width={1.4} />
                    <Arrow x1={x} y1={cy + hs + 16} x2={x} y2={cy + hs + 1} id={id} width={1.4} />
                </g>
            ))}
            <Tag x={hx + Lpx + 10} y={cy - hs - 6} text={`p = ${params.p ?? "–"}`} tone="load" />
            <Dim x1={hx - 18} y1={cy - H} x2={hx - 18} y2={cy + H} label={`Ø${params.D}`} id={id} />
            <Dim x1={hx + Lpx + 18} y1={cy - hs} x2={hx + Lpx + 18} y2={cy + hs} label={`Ø${params.d}`} id={id} />
            <Dim x1={hx} y1={cy + H + 16} x2={hx + Lpx} y2={cy + H + 16} label={`L ${params.L}`} id={id} />
            <MomentArrow cx={80} cy={cy - hs - 26} r={14} label={`T_cap ${params.T ?? ""}`} id={id} color="text-violet-500" />
            <Tag x={60} y={238} text={`δ = ${params.delta ?? "–"}`} />
            <Tag x={220} y={238} text={`n = ${params.n ?? "–"}`} tone={ok ? "ok" : "bad"} />
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// Spur gear pair: meshing gears with pitch circles (proportional)
// ---------------------------------------------------------------------------
function gearPath(cx: number, cy: number, r: number, z: number, m: number, phase: number): string {
    const ra = r + m, rf = Math.max(r - 1.25 * m, r * 0.5);
    const p = (2 * Math.PI) / z;
    const pt = (rad: number, a: number) => `${(cx + rad * Math.cos(a)).toFixed(1)},${(cy + rad * Math.sin(a)).toFixed(1)}`;
    let d = "";
    for (let i = 0; i < z; i++) {
        const a = phase + i * p;
        const seg = [pt(rf, a - 0.3 * p), pt(ra, a - 0.14 * p), pt(ra, a + 0.14 * p), pt(rf, a + 0.3 * p), pt(rf, a + 0.7 * p)];
        d += `${i === 0 ? "M" : "L"}${seg.join("L")}`;
    }
    return d + "Z";
}

const SpurGear: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const z1 = Math.round(num(params.z1, 20)), z2 = Math.round(num(params.z2, 50));
    const d1 = num(params.d1, 40), d2 = num(params.d2, 100), mm = num(params.m, 2);
    const a = (d1 + d2) / 2;
    const s = Math.min(205 / a, 128 / (d2 / 2 + mm));
    const r1 = (d1 / 2) * s, r2 = (d2 / 2) * s, m = mm * s;
    const cy = 160;
    const cx1 = 280 - (r1 + r2) / 2 - 0, cx2 = cx1 + r1 + r2;
    const ok = params.ok !== false;
    const p2 = (2 * Math.PI) / z2;

    return (
        <DiagramSvg w={560} h={320} label="Spur gear pair" id={id}>
            <path d={gearPath(cx1, cy, r1, z1, m, 0)} className={BODY} strokeWidth={1.1} />
            <path d={gearPath(cx2, cy, r2, z2, m, Math.PI + p2 / 2)} className={BODY_DARK} strokeWidth={1.1} />
            <circle cx={cx1} cy={cy} r={r1} fill="none" stroke="currentColor" strokeDasharray="4 3" strokeWidth={0.8} className="text-muted-foreground" />
            <circle cx={cx2} cy={cy} r={r2} fill="none" stroke="currentColor" strokeDasharray="4 3" strokeWidth={0.8} className="text-muted-foreground" />
            <circle cx={cx1} cy={cy} r={3} className="fill-foreground" />
            <circle cx={cx2} cy={cy} r={3} className="fill-foreground" />

            <MomentArrow cx={cx1} cy={cy} r={Math.min(18, r1 * 0.45)} label="" id={id} color="text-violet-500" />
            <MomentArrow cx={cx2} cy={cy} r={18} label="" id={id} color="text-violet-500" ccw />
            <Tag x={cx1} y={cy + r1 * 0.55 + 14} anchor="middle" text={`z1 = ${z1} · ${params.n1 ?? ""}`} />
            <Tag x={cx2} y={cy + 36} anchor="middle" text={`z2 = ${z2} · ${params.n2 ?? ""}`} />

            <Arrow x1={cx1 + r1} y1={cy - 46} x2={cx1 + r1} y2={cy - 4} label={`Wt ${params.Wt ?? ""}`} id={id} dx={6} dy={-2} />
            <Dim x1={cx1} y1={cy + r2 + 22} x2={cx2} y2={cy + r2 + 22} label={`a = ${params.a ?? ""} mm`} id={id} />
            <Tag x={20} y={24} text={`m ${params.m ?? ""} · d1 ${params.d1 ?? ""} · d2 ${params.d2 ?? ""} mm`} />
            <Tag x={20} y={44} text={`Bending n = ${params.SF ?? "–"}   Contact n = ${params.SH ?? "–"}`} tone={ok ? "ok" : "bad"} />
        </DiagramSvg>
    );
};

export const DIAGRAMS: Record<string, DiagramComponent> = {
    shaft_fatigue: ShaftFatigue,
    shaft_critical_speed: ShaftCriticalSpeed,
    parallel_key: ParallelKey,
    iso_fits: IsoFits,
    interference_fit: InterferenceFit,
    spur_gear: SpurGear,
};
