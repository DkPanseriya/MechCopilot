"""
Data-driven selectors: bearings (ISO 281) and ISO metric fasteners.

Bearing life math is public (ISO 281). Catalog C/C0 values here are REPRESENTATIVE
estimates for a POC, not manufacturer-certified data — results are labelled
accordingly. See product/GENERATIVE_ENGINE_PLAN.md §7.4.
"""
from typing import Any, Dict, List, Optional

# --- Bearing catalog (deep-groove ball, representative C/C0 in newtons) ---
# d = bore (mm), C = dynamic load rating (N), C0 = static load rating (N).
BEARINGS: List[Dict[str, Any]] = [
    {"designation": "608",  "bore_mm": 8,  "od_mm": 22,  "C": 3450,  "C0": 1370},
    {"designation": "6000", "bore_mm": 10, "od_mm": 26,  "C": 4620,  "C0": 1960},
    {"designation": "6200", "bore_mm": 10, "od_mm": 30,  "C": 5400,  "C0": 2360},
    {"designation": "6004", "bore_mm": 20, "od_mm": 42,  "C": 9360,  "C0": 5000},
    {"designation": "6204", "bore_mm": 20, "od_mm": 47,  "C": 12700, "C0": 6550},
    {"designation": "6304", "bore_mm": 20, "od_mm": 52,  "C": 15900, "C0": 7800},
    {"designation": "6006", "bore_mm": 30, "od_mm": 55,  "C": 13300, "C0": 8300},
    {"designation": "6206", "bore_mm": 30, "od_mm": 62,  "C": 19500, "C0": 11200},
    {"designation": "6306", "bore_mm": 30, "od_mm": 72,  "C": 28100, "C0": 16000},
    {"designation": "6208", "bore_mm": 40, "od_mm": 80,  "C": 29600, "C0": 18000},
    {"designation": "6308", "bore_mm": 40, "od_mm": 90,  "C": 41000, "C0": 24000},
    {"designation": "6210", "bore_mm": 50, "od_mm": 90,  "C": 35100, "C0": 23200},
]


def select_bearing(
    P: float,
    speed_rpm: float = 0.0,
    bore_min_mm: float = 0.0,
    bore_max_mm: Optional[float] = None,
    p_exp: float = 3.0,
) -> Dict[str, Any]:
    """Rank bearings by ISO 281 basic rating life for an equivalent dynamic load P (N)."""
    rows: List[Dict[str, Any]] = []
    for b in BEARINGS:
        if b["bore_mm"] < bore_min_mm:
            continue
        if bore_max_mm is not None and b["bore_mm"] > bore_max_mm:
            continue
        if P <= 0:
            continue
        l10 = (b["C"] / P) ** p_exp  # million revolutions
        l10h = (1_000_000.0 / (60.0 * speed_rpm)) * l10 if speed_rpm > 0 else None
        s0 = b["C0"] / P  # static safety factor (approx, P0≈P)
        rows.append({
            **b,
            "L10_Mrev": round(l10, 2),
            "L10h_hours": round(l10h, 0) if l10h is not None else None,
            "static_safety": round(s0, 2),
        })
    rows.sort(key=lambda r: r["L10_Mrev"], reverse=True)
    return {
        "service": "bearing",
        "basis": "ISO 281 basic rating life L10 = (C/P)^p (representative catalog data — estimated)",
        "inputs": {"P_N": P, "speed_rpm": speed_rpm, "bore_min_mm": bore_min_mm},
        "columns": ["designation", "bore_mm", "od_mm", "C", "C0", "L10_Mrev", "L10h_hours", "static_safety"],
        "rows": rows,
    }


# --- ISO metric fasteners -------------------------------------------------
# At = tensile stress area (mm^2). Coarse pitch.
STRESS_AREA_MM2: Dict[str, float] = {
    "M5": 14.2, "M6": 20.1, "M8": 36.6, "M10": 58.0, "M12": 84.3,
    "M16": 157.0, "M20": 245.0, "M24": 353.0,
}
NOMINAL_DIA_MM: Dict[str, float] = {
    "M5": 5, "M6": 6, "M8": 8, "M10": 10, "M12": 12, "M16": 16, "M20": 20, "M24": 24,
}
# Proof strength Sp and yield Sy by property class (MPa).
GRADES: Dict[str, Dict[str, float]] = {
    "4.6": {"Sp": 225, "Sy": 240, "Su": 400},
    "8.8": {"Sp": 600, "Sy": 640, "Su": 800},
    "10.9": {"Sp": 830, "Sy": 940, "Su": 1040},
    "12.9": {"Sp": 970, "Sy": 1100, "Su": 1220},
}


def select_fastener(
    axial_load_N: float,
    grade: str = "8.8",
    preload_factor: float = 0.9,
    k_factor: float = 0.2,
    min_safety: float = 1.5,
) -> Dict[str, Any]:
    """Recommend ISO metric bolt sizes for an axial load at a given grade."""
    g = GRADES.get(grade, GRADES["8.8"])
    Sp = g["Sp"]
    rows: List[Dict[str, Any]] = []
    for size, At in STRESS_AREA_MM2.items():
        proof_load_N = At * Sp            # N (At mm^2 * MPa = N)
        preload_N = preload_factor * proof_load_N
        d = NOMINAL_DIA_MM[size]
        torque_Nm = k_factor * preload_N * (d / 1000.0)
        safety = proof_load_N / axial_load_N if axial_load_N > 0 else float("inf")
        rows.append({
            "size": size,
            "stress_area_mm2": At,
            "proof_load_kN": round(proof_load_N / 1000.0, 2),
            "preload_kN": round(preload_N / 1000.0, 2),
            "tightening_torque_Nm": round(torque_Nm, 1),
            "safety_vs_proof": round(safety, 2) if safety != float("inf") else None,
            "adequate": safety >= min_safety,
        })
    recommended = next((r["size"] for r in rows if r["adequate"]), None)
    return {
        "service": "fastener",
        "basis": f"ISO metric grade {grade}: Fi = {preload_factor}·At·Sp, T = {k_factor}·Fi·d",
        "inputs": {"axial_load_N": axial_load_N, "grade": grade},
        "recommended": recommended,
        "columns": ["size", "stress_area_mm2", "proof_load_kN", "preload_kN", "tightening_torque_Nm", "safety_vs_proof", "adequate"],
        "rows": rows,
    }
