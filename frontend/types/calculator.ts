// Mirrors backend/engineering/core.py (Calculator.to_dict / run_calculator).

export interface UnitChoice {
    value: string;
    label: string;
    factor: number; // canonical = value * factor + offset
    offset: number;
}

export type UnitChoices = Record<string, UnitChoice[]>;

export interface SelectOption {
    value: string | number;
    label: string;
}

export interface CalcParam {
    name: string;
    label: string;
    kind: "number" | "select" | "bool" | "text";
    dim: string;
    default: any;
    unit: string | null;
    options: SelectOption[] | null;
    min: number | null;
    max: number | null;
    help: string | null;
    group: string | null;
    advanced: boolean;
    show_if: Record<string, any[]> | null;
}

export interface CalcOutputDef {
    name: string;
    label: string;
    dim: string;
    unit: string;
    unit_label: string;
    primary: boolean;
    help: string | null;
}

export interface CalculatorDef {
    id: string;
    title: string;
    category: string;
    summary: string;
    description: string;
    diagram: string | null;
    formulas: string[];
    references: string[];
    keywords: string[];
    presets: { label: string; values: Record<string, any> }[];
    params: CalcParam[];
    outputs: CalcOutputDef[];
}

export interface CatalogResponse {
    unit_choices: UnitChoices;
    categories: string[];
    category_order: string[];
    calculators: CalculatorDef[];
}

export interface RunOutput extends CalcOutputDef {
    value: number | null;
    display: string;
    si_value: number | null;
}

export interface RunCheck {
    label: string;
    status: "ok" | "warn" | "fail";
    message: string;
    value: number | null;
    limit: number | null;
}

export interface RunStep {
    label: string;
    latex: string;
    display?: string;
    unit_label?: string;
}

export interface RunSeries {
    id: string;
    title: string;
    x: number[];
    y: number[];
    x_label: string;
    y_label: string;
    x_unit: string;
    y_unit: string;
    kind: "line" | "area" | "step" | "scatter";
    group: string | null;
    markers: { x: number; label: string }[];
    ref_lines: { y: number; label: string }[];
    x_scale?: "linear" | "log";
    y_scale?: "linear" | "log";
}

export interface RunTable {
    title: string;
    columns: { key: string; label: string; unit?: string }[];
    rows: Record<string, any>[];
    highlight: Record<string, any> | null;
    note: string | null;
}

export interface RunResult {
    id: string;
    outputs: RunOutput[];
    checks: RunCheck[];
    steps: RunStep[];
    series: RunSeries[];
    tables: RunTable[];
    diagram: { id: string; params: Record<string, any> } | null;
    notes: string[];
    links: { label: string; url: string }[];
    verdict: "ok" | "warn" | "fail" | "none";
}

// What a param value looks like in component state / API payloads.
export type ParamValue = { value: number | string; unit: string } | string | number | boolean;
