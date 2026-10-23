// Zod mirror of backend/ui_spec.py. Keep the two in sync.
// The frontend validates any spec before rendering (defense in depth) and
// derives its types from these schemas.
import { z } from "zod";

export const unitTypeSchema = z.enum([
    "length", "force", "pressure", "area", "mass", "density",
    "modulus_of_elasticity", "torque", "acceleration", "velocity",
    "time", "energy", "power", "temperature", "angle",
]);

export const inputFieldSchema = z.object({
    name: z.string(),
    label: z.string(),
    type: z.enum(["number", "text"]).default("number"),
    unit: z.string().nullish(),
    unit_type: unitTypeSchema.nullish(),
    default_value: z.any().nullish(),
});

const specBase = {
    title: z.string(),
    description: z.string().nullish(),
    citations: z.array(z.string()).nullish(),
    suggestions: z.array(z.string()).nullish(),
};

const stepValue = z.union([z.number(), z.string()]);

export const calculatorSpecSchema = z.object({
    type: z.literal("calculator"),
    relation: z.string(),
    solve_for: z.string(),
    output_unit: z.string().nullish(),
    formula_latex: z.string().nullish(),
    inputs: z.array(inputFieldSchema).default([]),
    ...specBase,
});

export const workflowStepSchema = z.object({
    step_id: z.string(),
    relation: z.string(),
    solve_for: z.string(),
    explanation: z.string().nullish(),
    inputs: z.record(z.string(), stepValue).default({}),
    output_unit: z.string().nullish(),
});

export const workflowSpecSchema = z.object({
    type: z.literal("workflow"),
    steps: z.array(workflowStepSchema).default([]),
    ...specBase,
});

export const chartSpecSchema = z.object({
    type: z.literal("chart"),
    chart_kind: z.enum(["line", "bar", "scatter"]).default("line"),
    relation: z.string(),
    solve_for: z.string(),
    sweep_var: z.string(),
    sweep_range: z.object({ min: z.number(), max: z.number(), steps: z.number().default(25) }),
    sweep_unit: z.string().nullish(),
    output_unit: z.string().nullish(),
    fixed_inputs: z.record(z.string(), stepValue).default({}),
    ...specBase,
});

export const figureSpecSchema = z.object({
    type: z.literal("figure"),
    figure_id: z.string(),
    annotations: z.record(z.string(), z.any()).nullish(),
    caption: z.string().nullish(),
    ...specBase,
});

export const selectorSpecSchema = z.object({
    type: z.literal("selector"),
    service: z.enum(["bearing", "fastener"]),
    constraints: z.record(z.string(), z.any()).default({}),
    ...specBase,
});

export const comparisonSpecSchema = z.object({
    type: z.literal("comparison"),
    columns: z.array(z.string()).default([]),
    options: z.array(z.record(z.string(), z.any())).default([]),
    recommendation: z.string().nullish(),
    ...specBase,
});

export const materialCardSpecSchema = z.object({
    type: z.literal("material"),
    material_key: z.string(),
    ...specBase,
});

export const calcSpecSchema = z.object({
    type: z.literal("calc"),
    calculator: z.string(),
    inputs: z.record(z.string(), z.any()).default({}),
    purpose: z.string().nullish(),
    ...specBase,
});

export const uiSpecSchema = z.discriminatedUnion("type", [
    calcSpecSchema,
    calculatorSpecSchema,
    workflowSpecSchema,
    chartSpecSchema,
    figureSpecSchema,
    selectorSpecSchema,
    comparisonSpecSchema,
    materialCardSpecSchema,
]);

export type UISpec = z.infer<typeof uiSpecSchema>;
export type CalcSpec = z.infer<typeof calcSpecSchema>;
export type CalculatorSpec = z.infer<typeof calculatorSpecSchema>;
export type WorkflowSpec = z.infer<typeof workflowSpecSchema>;
export type ChartSpec = z.infer<typeof chartSpecSchema>;
export type FigureSpec = z.infer<typeof figureSpecSchema>;
export type SelectorSpec = z.infer<typeof selectorSpecSchema>;
export type ComparisonSpec = z.infer<typeof comparisonSpecSchema>;
export type MaterialCardSpec = z.infer<typeof materialCardSpecSchema>;

/** Validate an unknown value into a UISpec, or return null (never throws). */
export function parseUISpec(data: unknown): UISpec | null {
    const result = uiSpecSchema.safeParse(data);
    return result.success ? result.data : null;
}
