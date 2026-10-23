"use client";

// Fastener diagrams. Schematic (not to scale) but proportioned from the real
// dimensions where it helps reading, and labelled with live backend values.

import { useId } from "react";
import { Arrow, BODY, BODY_DARK, DiagramComponent, DiagramSvg, Dim, MomentArrow, Tag } from "./primitives";

const num = (v: unknown, d = 0): number => (typeof v === "number" && isFinite(v) ? v : d);
const str = (v: unknown, d = "–"): string => (v === undefined || v === null || v === "" ? d : String(v));
const useSvgId = () => useId().replace(/:/g, "");

/** Saw-tooth thread profile along a horizontal edge. */
function ThreadTeeth({ x0, x1, y, depth, pitch, up }: { x0: number; x1: number; y: number; depth: number; pitch: number; up: boolean }) {
    const pts: string[] = [];
    const s = up ? -1 : 1;
    for (let x = x0, i = 0; x <= x1; x += pitch / 2, i++) pts.push(`${x},${y + (i % 2 ? s * depth : 0)}`);
    return <polyline points={pts.join(" ")} fill="none" stroke="currentColor" strokeWidth={1} className="text-foreground/70" />;
}

/** Hexagon (flat-top) centred at cx,cy with across-flats s (px). */
function hexPoints(cx: number, cy: number, s: number): string {
    const r = s / Math.sqrt(3);
    return Array.from({ length: 6 }, (_, i) => {
        const a = (Math.PI / 3) * i;
        return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
    }).join(" ");
}

// ---------------------------------------------------------------------------
// 1. Bolt dimensions
// ---------------------------------------------------------------------------
const BoltDimensions: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const head = str(params.head, "shcs");
    const d = num(params.d, 10), k = num(params.k, 10), P = num(params.P, 1.5);
    const dk = num(params.dk, 16), s = num(params.s, 8), e = num(params.e, 0);
    const headW = head === "hex" ? (e || s * 1.15) : dk;
    const sc = 96 / Math.max(headW, d * 1.6);
    const cy = 112, xHead = 70;
    const kp = Math.max(k * sc, 10), hw = headW * sc, dp = d * sc;
    const xShank = xHead + kp, xEnd = xShank + 250, xThread = xShank + 100;
    const pitchPx = Math.max(P * sc, 4);

    return (
        <DiagramSvg w={560} h={235} label={`${str(params.designation)} bolt dimensions`} id={id}>
            {/* head (side view) */}
            {head === "countersunk" ? (
                <path d={`M${xHead},${cy - hw / 2} L${xShank},${cy - dp / 2} L${xShank},${cy + dp / 2} L${xHead},${cy + hw / 2} Z`} className={BODY_DARK} strokeWidth={1.5} />
            ) : (
                <rect x={xHead} y={cy - hw / 2} width={kp} height={hw} rx={head === "shcs" ? 3 : 1} className={BODY_DARK} strokeWidth={1.5} />
            )}
            {head === "hex" && (
                <>
                    <line x1={xHead} y1={cy - hw / 4} x2={xShank} y2={cy - hw / 4} stroke="currentColor" strokeWidth={0.7} className="text-foreground/50" />
                    <line x1={xHead} y1={cy + hw / 4} x2={xShank} y2={cy + hw / 4} stroke="currentColor" strokeWidth={0.7} className="text-foreground/50" />
                </>
            )}
            {/* shank + thread */}
            <rect x={xShank} y={cy - dp / 2} width={xEnd - xShank} height={dp} className={BODY} strokeWidth={1.5} />
            <ThreadTeeth x0={xThread} x1={xEnd} y={cy - dp / 2} depth={Math.min(pitchPx * 0.55, dp * 0.12)} pitch={pitchPx} up={false} />
            <ThreadTeeth x0={xThread} x1={xEnd} y={cy + dp / 2} depth={Math.min(pitchPx * 0.55, dp * 0.12)} pitch={pitchPx} up />
            <line x1={xHead - 14} y1={cy} x2={xEnd + 14} y2={cy} stroke="currentColor" strokeDasharray="10 3 2 3" strokeWidth={0.8} className="text-muted-foreground" />

            <Dim x1={xShank + 50} y1={cy - dp / 2} x2={xShank + 50} y2={cy + dp / 2} label={`d ${d}`} id={id} />
            <Dim x1={xHead} y1={cy + hw / 2 + 16} x2={xShank} y2={cy + hw / 2 + 16} label={`k ${k}`} id={id} />
            <Dim x1={xHead - 18} y1={cy - hw / 2} x2={xHead - 18} y2={cy + hw / 2} label="" id={id} />
            <Tag x={xHead - 22} y={cy - hw / 2 - 8} anchor="middle" text={head === "hex" ? `e ${e}` : `dk ${dk}`} />
            <Tag x={(xThread + xEnd) / 2} y={cy - dp / 2 - 12} anchor="middle" text={`P ${P}`} tone="moment" />

            {/* end view of the head */}
            <g transform={`translate(470 ${cy})`}>
                {head === "hex" ? (
                    <polygon points={hexPoints(0, 0, s * sc * 0.75)} className={BODY_DARK} strokeWidth={1.5} />
                ) : (
                    <>
                        <circle r={(hw / 2) * 0.75} className={BODY_DARK} strokeWidth={1.5} />
                        <polygon points={hexPoints(0, 0, s * sc * 0.75)} className="fill-background stroke-current" strokeWidth={1.2} />
                    </>
                )}
                <Tag x={0} y={(hw / 2) * 0.75 + 18} anchor="middle" text={head === "hex" ? `spanner ${s}` : `hex key ${s}`} />
            </g>

            <Tag x={20} y={24} text={`${str(params.designation)} – ${str(params.cls)}`} />
            <Tag x={20} y={218} text={`As ${str(params.As)} mm²`} />
            <Tag x={150} y={218} text={`FM ${str(params.FM)}`} tone="load" />
            <Tag x={270} y={218} text={`MA ${str(params.MA)}`} tone="moment" />
            <Tag x={400} y={218} text={`tap Ø${str(params.tap)} · hole Ø${str(params.hole)}`} />
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// shared: bolt clamping plates (section view, vertical bolt)
// ---------------------------------------------------------------------------
function ClampedSection({ id, tapped, washer, cx, top, lK, plateW, boltW, headW, headH, plates }: {
    id: string; tapped: boolean; washer: boolean; cx: number; top: number; lK: number; plateW: number;
    boltW: number; headW: number; headH: number; plates: number;
}) {
    const bottom = top + lK;
    const holeW = boltW + 6;
    const plateH = lK / Math.max(plates, 1);
    return (
        <g>
            {Array.from({ length: plates }, (_, i) => {
                const y = top + i * plateH;
                const last = i === plates - 1;
                const h = tapped && last ? plateH + 40 : plateH;
                return (
                    <g key={i}>
                        <rect x={cx - plateW / 2} y={y} width={plateW / 2 - holeW / 2} height={h} fill={`url(#${id}-hatch)`} className="text-muted-foreground" stroke="currentColor" strokeWidth={1} />
                        <rect x={cx + holeW / 2} y={y} width={plateW / 2 - holeW / 2} height={h} fill={`url(#${id}-hatch)`} className="text-muted-foreground" stroke="currentColor" strokeWidth={1} />
                    </g>
                );
            })}
            {washer && <rect x={cx - headW / 2 - 8} y={top - 5} width={headW + 16} height={5} className={BODY_DARK} strokeWidth={1} />}
            <rect x={cx - headW / 2} y={top - (washer ? 5 : 0) - headH} width={headW} height={headH} rx={2} className={BODY_DARK} strokeWidth={1.5} />
            <rect x={cx - boltW / 2} y={top} width={boltW} height={lK + (tapped ? 30 : 26)} className={BODY} strokeWidth={1.5} />
            {!tapped && <rect x={cx - headW / 2} y={bottom} width={headW} height={headH * 0.8} rx={1} className={BODY_DARK} strokeWidth={1.5} />}
        </g>
    );
}

// ---------------------------------------------------------------------------
// 2. Tightening
// ---------------------------------------------------------------------------
const BoltTightening: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const cx = 200, top = 92, lK = 96;
    return (
        <DiagramSvg w={560} h={250} label="Bolt tightening: torque produces clamp force" id={id}>
            <ClampedSection id={id} tapped={false} washer={false} cx={cx} top={top} lK={lK} plateW={240} boltW={26} headW={50} headH={22} plates={2} />
            {/* wrench */}
            <g className="text-muted-foreground">
                <rect x={cx - 30} y={top - 36} width={60} height={14} rx={3} className="fill-muted stroke-current" strokeWidth={1} />
                <rect x={cx + 28} y={top - 33} width={120} height={8} rx={4} className="fill-muted stroke-current" strokeWidth={1} />
            </g>
            <MomentArrow cx={cx} cy={top - 60} r={20} label={`MA ${str(params.MA)}`} id={id} />
            <Arrow x1={cx - 100} y1={top - 30} x2={cx - 100} y2={top - 4} id={id} label="" />
            <Arrow x1={cx - 100} y1={top + lK + 30} x2={cx - 100} y2={top + lK + 4} id={id} label="" />
            <Tag x={cx - 150} y={top + lK / 2 + 4} text={`FM ${str(params.FMmax)}`} tone="load" anchor="middle" />

            <g transform="translate(372 70)">
                <Tag x={0} y={0} text={`${str(params.designation)} – ${str(params.cls)}`} />
                <Tag x={0} y={26} text={`FM,max ${str(params.FMmax)}`} tone="load" />
                <Tag x={0} y={46} text={`FM,min ${str(params.FMmin)}`} tone="load" />
                <Tag x={0} y={66} text={`αA = ${str(params.alpha)}`} />
                <Tag x={0} y={86} text={str(params.mu)} />
                <Tag x={0} y={112} text={`MA = ${str(params.MA)}`} tone="moment" />
            </g>
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// 3. Bolted joint with deformation cone
// ---------------------------------------------------------------------------
const BoltedJoint: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const tapped = params.joint_type === "tapped";
    const washer = Boolean(params.washer);
    const cx = 210, top = 70, lK = 110, headW = 54;
    const plates = tapped ? Math.max(1, num(params.interfaces, 0) + 1) : Math.max(2, num(params.interfaces, 1) + 1);
    const coneTop = (headW + (washer ? 16 : 0)) / 2;
    const coneSpread = 46;
    const ok = params.ok_clamp !== false;
    return (
        <DiagramSvg w={560} h={270} label="Bolted joint section with deformation cone" id={id}>
            <ClampedSection id={id} tapped={tapped} washer={washer} cx={cx} top={top} lK={lK} plateW={300} boltW={28} headW={headW} headH={22} plates={Math.min(plates, 4)} />
            {/* deformation cone */}
            <g className="text-cyan-500" strokeDasharray="5 4" strokeWidth={1.3} stroke="currentColor" fill="none">
                <path d={`M${cx - coneTop},${top} L${cx - coneTop - coneSpread},${top + lK / 2} L${cx - coneTop},${top + lK}`} />
                <path d={`M${cx + coneTop},${top} L${cx + coneTop + coneSpread},${top + lK / 2} L${cx + coneTop},${top + lK}`} />
            </g>
            <Dim x1={cx + 150 + 14} y1={top} x2={cx + 150 + 14} y2={top + lK} label={`lK ${str(params.lK)} mm`} id={id} />
            <Dim x1={cx - 150} y1={top + lK + 52} x2={cx + 150} y2={top + lK + 52} label={`DA ${str(params.DA)} mm`} id={id} />
            {/* external load pulls the plates apart */}
            <Arrow x1={cx - 120} y1={top + 26} x2={cx - 120} y2={top - 26} id={id} label="" />
            <Arrow x1={cx + 120} y1={top + 26} x2={cx + 120} y2={top - 26} id={id} label="" />
            <Arrow x1={cx - 120} y1={top + lK - 26} x2={cx - 120} y2={top + lK + 26} id={id} label="" />
            <Tag x={cx - 120} y={top - 32} anchor="middle" text={`FA ${str(params.FA)}`} tone="load" />

            <g transform="translate(400 46)">
                <Tag x={0} y={0} text={`${str(params.designation)} – ${str(params.cls)}`} />
                <Tag x={0} y={22} text={tapped ? "tapped hole (ESV)" : "through bolt (DSV)"} />
                <Tag x={0} y={46} text={`FM,zul ${str(params.FM)}`} tone="load" />
                <Tag x={0} y={66} text={`Φn = ${str(params.phi)}`} />
                <Tag x={0} y={86} text={`deformation body: ${str(params.body)}`} />
                <Tag x={0} y={112} text={`FKR ${str(params.FKR)}`} tone={ok ? "ok" : "bad"} />
                {washer && <Tag x={0} y={132} text="hardened washer" />}
            </g>
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// 4. Lap joint in shear (plan + side)
// ---------------------------------------------------------------------------
const BoltShearJoint: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const n = Math.max(1, Math.round(num(params.n, 4)));
    const shown = Math.min(n, 6);
    const double = num(params.planes, 1) === 2;
    const x0 = 150, w = 230, y0 = 40, h = 92;
    const pitch = shown > 1 ? (w - 70) / (shown - 1) : 0;
    const ok = params.ok !== false;
    return (
        <DiagramSvg w={560} h={260} label="Bolted lap joint loaded in shear" id={id}>
            {/* plan view: plate A from left, plate B from right, overlapping */}
            <rect x={40} y={y0} width={x0 + w - 40} height={h} className={BODY} strokeWidth={1.3} />
            <rect x={x0} y={y0 + 6} width={w + 130} height={h - 12} className="fill-amber-500/10 stroke-current" strokeWidth={1.3} />
            {Array.from({ length: shown }, (_, i) => (
                <circle key={i} cx={x0 + 35 + i * pitch} cy={y0 + h / 2} r={Math.max(6, Math.min(12, num(params.d, 16) * 0.6))} className="fill-background stroke-current" strokeWidth={1.6} />
            ))}
            {n > shown && <Tag x={x0 + w / 2} y={y0 + h + 16} anchor="middle" text={`${n} bolts total`} />}
            <Arrow x1={70} y1={y0 + h / 2} x2={20} y2={y0 + h / 2} id={id} label="" />
            <Arrow x1={x0 + w + 80} y1={y0 + h / 2} x2={x0 + w + 130} y2={y0 + h / 2} id={id} label="" />
            <Tag x={x0 + w + 104} y={y0 + h / 2 - 10} anchor="middle" text={`F ${str(params.F)}`} tone="load" />
            <Dim x1={x0 + 35 + (shown - 1) * pitch} y1={y0 + h + 4} x2={x0 + w} y2={y0 + h + 4} label={`e1 ${str(params.e1)}`} id={id} />
            <Dim x1={x0 + 35} y1={y0 + h / 2} x2={x0 + 35} y2={y0 + 6} label="" id={id} />
            <Tag x={x0 + 42} y={y0 + 22} text={`e2 ${str(params.e2)}`} />

            {/* side view */}
            <g transform="translate(60 190)">
                {double ? (
                    <>
                        <rect x={0} y={0} width={220} height={10} className={BODY} strokeWidth={1} />
                        <rect x={120} y={12} width={260} height={12} className="fill-amber-500/10 stroke-current" strokeWidth={1} />
                        <rect x={0} y={26} width={220} height={10} className={BODY} strokeWidth={1} />
                    </>
                ) : (
                    <>
                        <rect x={0} y={4} width={220} height={12} className={BODY} strokeWidth={1} />
                        <rect x={120} y={18} width={260} height={12} className="fill-amber-500/10 stroke-current" strokeWidth={1} />
                    </>
                )}
                <rect x={160} y={-8} width={14} height={52} className={BODY_DARK} strokeWidth={1} />
                <Tag x={400} y={22} text={double ? "double shear (2 planes)" : "single shear (1 plane)"} />
                <Tag x={400} y={40} text={`t ${str(params.t)} mm`} />
            </g>

            <Tag x={20} y={24} text={`${n} × ${str(params.designation)} – ${str(params.cls)}`} />
            <Tag x={540} y={24} anchor="end" text={`utilisation ${str(params.util)} (${str(params.mode)})`} tone={ok ? "ok" : "bad"} />
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// 5. Thread engagement in a tapped hole
// ---------------------------------------------------------------------------
const ThreadEngagement: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const LE = num(Number(params.LE), 10), Lreq = num(Number(params.L_req), 8), d = num(params.d, 8);
    const ok = params.ok !== false;
    const sc = 120 / Math.max(LE, Lreq, d * 1.2);
    const cx = 200, surf = 70, boltW = Math.max(d * sc * 0.9, 24);
    const lePx = LE * sc, reqPx = Lreq * sc;
    return (
        <DiagramSvg w={560} h={250} label="Bolt engaged in a tapped hole" id={id}>
            <rect x={60} y={surf} width={cx - boltW / 2 - 60} height={160} fill={`url(#${id}-hatch)`} stroke="currentColor" className="text-muted-foreground" strokeWidth={1} />
            <rect x={cx + boltW / 2} y={surf} width={340 - (cx + boltW / 2) + 0} height={160} fill={`url(#${id}-hatch)`} stroke="currentColor" className="text-muted-foreground" strokeWidth={1} />
            <rect x={cx - boltW / 2} y={surf - 50} width={boltW} height={50 + lePx} className={BODY} strokeWidth={1.5} />
            {/* thread teeth along the engaged length (drawn horizontally, rotated to vertical) */}
            <g transform={`rotate(90 ${cx} ${surf})`}>
                <ThreadTeeth x0={cx} x1={cx + lePx} y={surf - boltW / 2} depth={4} pitch={8} up />
                <ThreadTeeth x0={cx} x1={cx + lePx} y={surf + boltW / 2} depth={4} pitch={8} up={false} />
            </g>
            <line x1={cx - boltW / 2 - 30} y1={surf + reqPx} x2={cx + boltW / 2 + 30} y2={surf + reqPx} stroke="currentColor" strokeDasharray="5 4" strokeWidth={1.4} className={ok ? "text-emerald-500" : "text-rose-500"} />
            <Tag x={cx + boltW / 2 + 34} y={surf + reqPx + 4} text={`required ${str(params.L_req)} mm`} tone={ok ? "ok" : "bad"} />
            <Dim x1={cx - boltW / 2 - 18} y1={surf} x2={cx - boltW / 2 - 18} y2={surf + lePx} label="" id={id} />
            <Tag x={cx - boltW / 2 - 24} y={surf + lePx / 2 + 4} anchor="end" text={`LE ${str(params.LE)}`} />
            <Tag x={20} y={24} text={`${str(params.designation)} into ${str(params.material)}`} />
            <Tag x={380} y={120} text={ok ? "bolt breaks first ✓" : "thread strips first ✗"} tone={ok ? "ok" : "bad"} />
            <Tag x={380} y={140} text={`tap drill Ø${str(params.tap)}`} />
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// 6. Bolt group with per-bolt force vectors
// ---------------------------------------------------------------------------
const BoltGroup: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const bolts: { x: number; y: number; fx: number; fy: number; R: number }[] = Array.isArray(params.bolts) ? params.bolts : [];
    if (!bolts.length) return null;
    const crit = num(params.crit, 0);
    const e = num(params.e, 0);
    const ext = Math.max(...bolts.map((b) => Math.max(Math.abs(b.x), Math.abs(b.y))), 1);
    const cx = 190, cy = 130, box = 85;
    const sc = box / ext;
    const eShown = Math.min(Math.abs(e) * sc, 230);
    const broken = Math.abs(e) * sc > 230;
    const Rmax = Math.max(...bolts.map((b) => b.R), 1);
    const vec = 55 / Rmax;
    const ok = params.ok !== false;
    return (
        <DiagramSvg w={560} h={270} label="Bolt group under eccentric load" id={id}>
            <rect x={cx - box - 26} y={cy - box - 26} width={2 * box + 52} height={2 * box + 52} rx={6} className={BODY} strokeWidth={1.2} />
            <line x1={cx - 10} y1={cy} x2={cx + 10} y2={cy} stroke="currentColor" strokeWidth={1} className="text-muted-foreground" />
            <line x1={cx} y1={cy - 10} x2={cx} y2={cy + 10} stroke="currentColor" strokeWidth={1} className="text-muted-foreground" />
            {bolts.map((b, i) => {
                const bx = cx + b.x * sc, by = cy - b.y * sc;
                const isCrit = i === crit;
                return (
                    <g key={i}>
                        <circle cx={bx} cy={by} r={7} className={isCrit ? "fill-rose-500/30 stroke-current text-rose-500" : "fill-background stroke-current"} strokeWidth={1.6} />
                        {Math.hypot(b.fx * vec, b.fy * vec) > 3 && (
                            <Arrow x1={bx} y1={by} x2={bx + b.fx * vec} y2={by - b.fy * vec} width={1.8} head={8}
                                color={isCrit ? "text-rose-500" : "text-violet-500"} id={id} />
                        )}
                        <text x={bx - 9} y={by - 10} textAnchor="end" className="fill-muted-foreground" fontSize={10}>{i + 1}</text>
                    </g>
                );
            })}
            {/* applied load at eccentricity e */}
            <Arrow x1={cx} y1={cy + box + 34} x2={cx + eShown} y2={cy + box + 34} width={0.9} head={7} color="text-muted-foreground" id={id} />
            <Tag x={cx + eShown / 2} y={cy + box + 50} anchor="middle" text={`e ${Math.round(e)} mm${broken ? " (not to scale)" : ""}`} />
            <Arrow x1={cx + eShown} y1={cy - 70} x2={cx + eShown} y2={cy - 10} id={id} label={`F ${str(params.F)}`} dx={8} dy={4} />
            <Tag x={540} y={30} anchor="end" text={`critical bolt ${crit + 1}: ${str(params.Rmax)}`} tone={ok ? "ok" : "bad"} />
            <Tag x={540} y={50} anchor="end" text="arrows: resultant force per bolt" />
        </DiagramSvg>
    );
};

// ---------------------------------------------------------------------------
// 7. Fastener stack (selector result)
// ---------------------------------------------------------------------------
const BoltStack: DiagramComponent = ({ params }) => {
    const id = useSvgId();
    const jt = str(params.joint_type, "through");
    const tapped = jt !== "through";
    const ok = params.ok !== false;
    const cx = 190, top = 80, lK = 90;
    return (
        <DiagramSvg w={560} h={250} label="Selected fastener assembly" id={id}>
            <ClampedSection id={id} tapped={tapped} washer={!tapped} cx={cx} top={top} lK={lK} plateW={220} boltW={24} headW={46} headH={22} plates={tapped ? 1 : 2} />
            {!tapped && <rect x={cx - 31} y={top + lK} width={62} height={5} className={BODY_DARK} strokeWidth={1} />}
            <Dim x1={cx + 120} y1={top} x2={cx + 120} y2={top + lK} label={`clamp ${str(params.lK)} mm`} id={id} />
            <Dim x1={cx - 130} y1={top} x2={cx - 130} y2={top + lK + (tapped ? 30 : 26)} label="" id={id} />
            <Tag x={cx - 136} y={top + lK / 2} anchor="end" text={`L ${str(params.L, "?")}`} />
            <g transform="translate(345 70)">
                <Tag x={0} y={0} text={ok ? "Recommended" : "No adequate size"} tone={ok ? "ok" : "bad"} />
                {String(params.designation || "").split(" + ").map((line, i) => (
                    <Tag key={i} x={0} y={24 + i * 20} text={(i ? "+ " : "") + line} />
                ))}
                <Tag x={0} y={110} text={tapped ? (jt === "tapped_al" ? "tapped into aluminium" : "tapped into steel") : "through bolt with nut"} />
            </g>
        </DiagramSvg>
    );
};

export const DIAGRAMS: Record<string, DiagramComponent> = {
    bolt_dimensions: BoltDimensions,
    bolt_tightening: BoltTightening,
    bolted_joint: BoltedJoint,
    bolt_shear_joint: BoltShearJoint,
    thread_engagement: ThreadEngagement,
    bolt_group: BoltGroup,
    bolt_stack: BoltStack,
};
