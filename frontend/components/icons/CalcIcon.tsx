// Line-drawing icons for the calculator library: one small schematic per calculator.
// 48×48, drawn in the current text colour; the load or the feature being checked is in the
// accent colour (the <A> group). Unknown ids fall back to their category's icon.

const A = ({ children }: { children: React.ReactNode }) => <g className="text-blue-500">{children}</g>;

function Arrow({ x1, y1, x2, y2 }: { x1: number; y1: number; x2: number; y2: number }) {
    const a = Math.atan2(y2 - y1, x2 - x1), h = 3.2;
    const p = (s: number) => `${x2 - h * Math.cos(a + s)},${y2 - h * Math.sin(a + s)}`;
    return <><line x1={x1} y1={y1} x2={x2} y2={y2} /><polyline points={`${p(0.5)} ${x2},${y2} ${p(-0.5)}`} /></>;
}

/** A bearing seen face-on: outer and inner ring with balls between. */
function Bearing({ cx, cy, r }: { cx: number; cy: number; r: number }) {
    const balls = Array.from({ length: 8 }, (_, i) => (2 * Math.PI * i) / 8);
    return (
        <>
            <circle cx={cx} cy={cy} r={r} />
            <circle cx={cx} cy={cy} r={r * 0.42} />
            {balls.map((t, i) => <circle key={i} cx={cx + r * 0.71 * Math.cos(t)} cy={cy + r * 0.71 * Math.sin(t)} r={r * 0.13} />)}
        </>
    );
}

function gearPath(cx: number, cy: number, r: number, teeth: number): string {
    const pts: string[] = [];
    for (let i = 0; i < teeth; i++) {
        const a = (2 * Math.PI * i) / teeth, s = Math.PI / teeth;
        for (const [ang, rad] of [[a - s * 0.55, r - 2.4], [a - s * 0.3, r], [a + s * 0.3, r], [a + s * 0.55, r - 2.4]] as const) {
            pts.push(`${(cx + rad * Math.cos(ang)).toFixed(1)},${(cy + rad * Math.sin(ang)).toFixed(1)}`);
        }
    }
    return `M${pts.join("L")}Z`;
}

const BoltSide = ({ x, top, len, w = 8 }: { x: number; top: number; len: number; w?: number }) => (
    <>
        <rect x={x - w / 2 - 2} y={top} width={w + 4} height={5} rx={1} />
        <rect x={x - w / 2} y={top + 5} width={w} height={len} />
    </>
);

const ICONS: Record<string, () => React.ReactElement> = {
    // Fasteners
    bolt_group_eccentric: () => (<>
        <rect x={7} y={9} width={26} height={32} rx={2} />
        {[16, 24].flatMap((x) => [16, 25, 34].map((y) => <circle key={`${x}${y}`} cx={x} cy={y} r={2.2} />))}
        <A><Arrow x1={42} y1={9} x2={42} y2={25} /><line x1={33} y1={9} x2={42} y2={9} strokeDasharray="2 2" /></A>
    </>),
    fastener_lookup: () => (<>
        <BoltSide x={17} top={7} len={30} />
        {[16, 20, 24, 28, 32].map((y) => <line key={y} x1={13} y1={y} x2={21} y2={y + 2} />)}
        <path d="M30 22 l5 -3 l5 3 v6 l-5 3 l-5 -3 Z" />
        <A><circle cx={35} cy={25} r={1.8} /><line x1={30} y1={40} x2={40} y2={40} /><line x1={30} y1={38} x2={30} y2={42} /><line x1={40} y1={38} x2={40} y2={42} /></A>
    </>),
    bolted_joint: () => (<>
        <rect x={5} y={18} width={38} height={6} /><rect x={5} y={24} width={38} height={6} />
        <rect x={19} y={13} width={10} height={5} rx={1} /><rect x={21} y={18} width={6} height={14} /><rect x={19} y={30} width={10} height={5} rx={1} />
        <A><Arrow x1={9} y1={16} x2={9} y2={5} /><Arrow x1={39} y1={32} x2={39} y2={43} /></A>
    </>),
    bolt_shear_joint: () => (<>
        <rect x={4} y={17} width={26} height={6} /><rect x={18} y={23} width={26} height={6} />
        <rect x={21} y={12} width={8} height={5} rx={1} /><rect x={22.5} y={17} width={5} height={14} /><rect x={21} y={29} width={8} height={5} rx={1} />
        <A><Arrow x1={14} y1={20} x2={3} y2={20} /><Arrow x1={34} y1={26} x2={45} y2={26} /></A>
    </>),
    thread_engagement: () => (<>
        <path d="M8 22 H19 V42 M29 42 V22 H40 V42 H8 Z" />
        <BoltSide x={24} top={6} len={30} w={10} />
        {[24, 28, 32, 36].map((y) => <line key={y} x1={19} y1={y} x2={29} y2={y + 2} />)}
        <A><line x1={34} y1={22} x2={34} y2={36} /><line x1={32} y1={22} x2={36} y2={22} /><line x1={32} y1={36} x2={36} y2={36} /></A>
    </>),
    bolt_preload_torque: () => (<>
        <path d="M12 26 l5 -3 l5 3 v6 l-5 3 l-5 -3 Z" />
        <path d="M23 25 L40 10 M26 32 L43 17 M40 10 Q46 12 43 17" />
        <A><path d="M9 18 A12 12 0 0 1 22 13" fill="none" /><polyline points="19,10 22,13 18,15" /></A>
    </>),
    fastener_selector: () => (<>
        <BoltSide x={10} top={16} len={18} w={5} />
        <BoltSide x={36} top={8} len={30} w={9} />
        <A><BoltSide x={23} top={12} len={24} w={7} /></A>
    </>),
    // Bearings
    bearing_selector: () => (<>
        <Bearing cx={20} cy={21} r={13} />
        <A><circle cx={34} cy={34} r={6} /><line x1={38.5} y1={38.5} x2={44} y2={44} /></A>
    </>),
    bearing_life: () => (<>
        <Bearing cx={20} cy={22} r={13} />
        <A><circle cx={36} cy={36} r={7} /><polyline points="36,32 36,36 39,38" /></A>
    </>),
    bearing_required_c: () => (<>
        <Bearing cx={24} cy={28} r={14} />
        <A><Arrow x1={24} y1={3} x2={24} y2={12} /></A>
    </>),
    // Beams
    beam_analysis: () => (<>
        <rect x={5} y={16} width={38} height={5} />
        <path d="M8 21 l-3 6 h6 Z M40 21 l-3 6 h6 Z" />
        <A><Arrow x1={24} y1={5} x2={24} y2={15} /><path d="M8 33 Q24 47 40 33" fill="none" /></A>
    </>),
    beam_profile_selector: () => (<>
        <path d="M12 8 H36 V13 H27 V35 H36 V40 H12 V35 H21 V13 H12 Z" />
        <A><line x1={42} y1={8} x2={42} y2={40} /><line x1={40} y1={8} x2={44} y2={8} /><line x1={40} y1={40} x2={44} y2={40} /></A>
    </>),
    section_properties: () => (<>
        <rect x={8} y={10} width={18} height={28} rx={1} /><rect x={12} y={14} width={10} height={20} />
        <circle cx={36} cy={24} r={8} />
        <A><line x1={4} y1={24} x2={46} y2={24} strokeDasharray="3 2" /><line x1={17} y1={5} x2={17} y2={43} strokeDasharray="3 2" /></A>
    </>),
    // Shafts
    shaft_critical_speed: () => (<>
        <line x1={4} y1={24} x2={44} y2={24} strokeWidth={2.4} />
        <rect x={20} y={14} width={8} height={20} rx={1.5} />
        <path d="M6 24 l-2 6 h4 Z M42 24 l-2 6 h4 Z" />
        <A><path d="M6 24 Q24 40 42 24" fill="none" strokeDasharray="3 2" /></A>
    </>),
    shaft_fatigue: () => (<>
        <path d="M4 18 H24 Q24 14 28 14 H44 V34 H28 Q24 34 24 30 H4 Z" />
        <A><circle cx={25.5} cy={15.5} r={3.5} /><path d="M40 8 A8 8 0 0 1 44 15" fill="none" /><polyline points="41,13 44,15 46,12" /></A>
    </>),
    drive_loads: () => (<>
        <circle cx={17} cy={24} r={11} /><circle cx={17} cy={24} r={3} />
        <line x1={17} y1={13} x2={44} y2={13} /><line x1={17} y1={35} x2={44} y2={35} strokeDasharray="3 2" />
        <A><Arrow x1={33} y1={7} x2={44} y2={7} /><path d="M10 17 A9 9 0 0 1 23 16" fill="none" /></A>
    </>),
    // Keys & fits
    iso_fits: () => (<>
        <line x1={4} y1={26} x2={44} y2={26} />
        <rect x={9} y={14} width={12} height={12} />
        <A><rect x={27} y={10} width={12} height={10} fill="currentColor" fillOpacity={0.15} /></A>
    </>),
    interference_fit: () => (<>
        <circle cx={24} cy={24} r={17} /><circle cx={24} cy={24} r={9} />
        <A>{[0, 90, 180, 270].map((d) => {
            const t = (d * Math.PI) / 180;
            return <Arrow key={d} x1={24 + 15 * Math.cos(t)} y1={24 + 15 * Math.sin(t)} x2={24 + 10.5 * Math.cos(t)} y2={24 + 10.5 * Math.sin(t)} />;
        })}</A>
    </>),
    parallel_key: () => (<>
        <circle cx={24} cy={26} r={18} /><circle cx={24} cy={26} r={11} />
        <A><rect x={20} y={11} width={8} height={7} fill="currentColor" fillOpacity={0.2} /></A>
    </>),
    // Gears
    spur_gear: () => (<>
        <path d={gearPath(18, 26, 13, 12)} /><circle cx={18} cy={26} r={3} />
        <A><path d={gearPath(37, 15, 8, 8)} /></A>
    </>),
    // Springs
    compression_spring: () => (<>
        <line x1={12} y1={10} x2={36} y2={10} /><line x1={12} y1={40} x2={36} y2={40} />
        <polyline points="24,10 16,14 32,18 16,22 32,26 16,30 32,34 24,40" />
        <A><Arrow x1={42} y1={4} x2={42} y2={16} /></A>
    </>),
    torsion_spring: () => (<>
        {[16, 21, 26, 31].map((x) => <ellipse key={x} cx={x} cy={26} rx={5} ry={9} />)}
        <line x1={11} y1={26} x2={4} y2={42} /><line x1={36} y1={26} x2={44} y2={10} />
        <A><path d="M36 6 A9 9 0 0 1 46 14" fill="none" /><polyline points="43,13 46,14 47,10" /></A>
    </>),
    // Welds
    fillet_weld: () => (<>
        <rect x={4} y={34} width={40} height={7} /><rect x={20} y={8} width={8} height={26} />
        <A><path d="M20 34 L14 34 L20 28 Z M28 34 L34 34 L28 28 Z" fill="currentColor" fillOpacity={0.35} /></A>
    </>),
    // Columns
    column_buckling: () => (<>
        <path d="M24 12 Q33 24 24 36" fill="none" strokeWidth={2.2} />
        <path d="M24 36 l-4 6 h8 Z M24 12 l-4 -4 h8 Z" />
        <A><Arrow x1={24} y1={1} x2={24} y2={8} /></A>
    </>),
    // Pressure vessels
    pressure_vessel: () => (<>
        <rect x={6} y={13} width={36} height={22} rx={11} />
        <A>{[[16, 24, 16, 17], [24, 24, 24, 17], [32, 24, 32, 17], [16, 24, 16, 31], [24, 24, 24, 31], [32, 24, 32, 31]].map(([a, b, c, d], i) => (
            <Arrow key={i} x1={a} y1={b} x2={c} y2={d} />
        ))}</A>
    </>),
    // Fatigue
    fatigue_life: () => (<>
        <polyline points="7,6 7,41 44,41" />
        <A><path d="M9 12 Q16 13 22 26 T44 32" fill="none" /></A>
    </>),
    stress_concentration: () => (<>
        <rect x={6} y={12} width={36} height={24} /><circle cx={24} cy={24} r={5} />
        <A><path d="M6 6 H18 Q24 6 24 1 Q24 6 30 6 H42" fill="none" /></A>
    </>),
    // Stress
    round_bar_combined: () => (<>
        <rect x={8} y={17} width={30} height={14} rx={2} /><ellipse cx={38} cy={24} rx={3} ry={7} />
        <A><Arrow x1={2} y1={24} x2={8} y2={24} /><path d="M40 10 A12 12 0 0 1 46 20" fill="none" /><polyline points="43,19 46,20 47,16" /></A>
    </>),
};

const BY_CATEGORY: Record<string, string> = {
    Fasteners: "bolted_joint", Bearings: "bearing_life", Beams: "beam_analysis", Shafts: "shaft_fatigue",
    "Keys & Fits": "iso_fits", Gears: "spur_gear", Springs: "compression_spring", Welds: "fillet_weld",
    Columns: "column_buckling", "Pressure Vessels": "pressure_vessel", Fatigue: "fatigue_life",
    Stress: "round_bar_combined",
};

export default function CalcIcon({ id, category, className = "" }: { id: string; category?: string; className?: string }) {
    const draw = ICONS[id] ?? ICONS[BY_CATEGORY[category ?? ""] ?? "beam_analysis"];
    return (
        <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round"
            strokeLinejoin="round" className={className} aria-hidden="true">
            {draw()}
        </svg>
    );
}
