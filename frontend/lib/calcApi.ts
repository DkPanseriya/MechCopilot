import { API_BASE } from "@/lib/api";
import type { CalcParam, CatalogResponse, ParamValue, RunResult, UnitChoices } from "@/types/calculator";

let catalogPromise: Promise<CatalogResponse> | null = null;

/** Calculator catalog, fetched once per page load. */
export function getCatalog(): Promise<CatalogResponse> {
    if (!catalogPromise) {
        catalogPromise = fetch(`${API_BASE}/api/calculators`)
            .then((r) => {
                if (!r.ok) throw new Error(`Catalog request failed (${r.status})`);
                return r.json();
            })
            .catch((e) => {
                catalogPromise = null; // allow retry
                throw e;
            });
    }
    return catalogPromise;
}

export class CalcRunError extends Error {}

export async function runCalculator(
    id: string,
    inputs: Record<string, ParamValue>,
    signal?: AbortSignal,
): Promise<RunResult> {
    const res = await fetch(`${API_BASE}/api/calculators/${id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inputs }),
        signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new CalcRunError(data.detail || `Calculation failed (${res.status})`);
    return data as RunResult;
}

/** Initial state for every param, merged with any overrides (e.g. from the copilot). */
export function initialValues(
    params: CalcParam[],
    overrides: Record<string, any> = {},
): Record<string, ParamValue> {
    const v: Record<string, ParamValue> = {};
    for (const p of params) {
        const o = overrides[p.name];
        if (p.kind === "number") {
            if (o && typeof o === "object" && "value" in o) v[p.name] = { value: o.value, unit: o.unit || p.unit || "" };
            else if (o !== undefined && o !== null && o !== "") v[p.name] = { value: o, unit: p.unit || "" };
            else v[p.name] = { value: p.default ?? 0, unit: p.unit || "" };
        } else if (p.kind === "bool") {
            v[p.name] = o !== undefined ? Boolean(o) : Boolean(p.default);
        } else {
            v[p.name] = o !== undefined && o !== null ? o : p.default;
        }
    }
    return v;
}

/** Convert a number between two units of the same dimension. */
export function convertValue(v: number, from: string, to: string, dim: string, units: UnitChoices): number {
    const list = units[dim] || [];
    const a = list.find((u) => u.value === from);
    const b = list.find((u) => u.value === to);
    if (!a || !b || !isFinite(v)) return v;
    const canon = v * a.factor + a.offset;
    return (canon - b.offset) / b.factor;
}

/** Round to a readable number of significant figures for display in inputs. */
export function tidy(v: number): number {
    if (!isFinite(v) || v === 0) return v;
    return Number(v.toPrecision(6));
}

export function isVisible(p: CalcParam, values: Record<string, ParamValue>): boolean {
    if (!p.show_if) return true;
    return Object.entries(p.show_if).every(([dep, allowed]) => {
        const cur = values[dep];
        const raw = cur && typeof cur === "object" ? (cur as any).value : cur;
        return allowed.map(String).includes(String(raw));
    });
}
