"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { BlockMath } from "react-katex";
import "katex/dist/katex.min.css";
import { ToolInput, ToolOutput } from "@/types";
import { API_BASE } from "@/lib/api";
import { Lightbulb, AlertCircle, Calculator } from "lucide-react";

const UNITS: Record<string, string[]> = {
    length: ["m", "cm", "mm", "in", "ft", "km", "mi"],
    force: ["N", "kN", "lbf", "kgf"],
    pressure: ["Pa", "kPa", "MPa", "GPa", "psi", "bar", "atm"],
    area: ["m2", "cm2", "mm2", "in2", "ft2"],
    mass: ["kg", "g", "lb", "oz", "ton"],
    density: ["kg/m3", "g/cm3", "lb/in3"],
    modulus_of_elasticity: ["Pa", "GPa", "MPa", "psi", "ksi"],
    torque: ["N*m", "N*mm", "kN*m", "lbf*ft", "lbf*in"],
    acceleration: ["m/s2", "ft/s2", "g"],
    velocity: ["m/s", "km/h", "mph", "ft/s", "knots"],
    time: ["s", "min", "h", "ms"],
    energy: ["J", "kJ", "cal", "kcal", "Btu", "kWh"],
    power: ["W", "kW", "hp", "MW"],
    temperature: ["C", "F", "K"],
    angle: ["deg", "rad"],
};

// Map the frontend unit tokens to Pint-parseable unit strings (backend uses Pint).
const PINT: Record<string, string> = {
    m2: "m**2", cm2: "cm**2", mm2: "mm**2", in2: "in**2", ft2: "ft**2",
    "kg/m3": "kg/m**3", "g/cm3": "g/cm**3", "lb/in3": "lb/in**3",
    "m/s2": "m/s**2", "ft/s2": "ft/s**2",
    C: "degC", F: "degF", K: "kelvin",
    deg: "degree", rad: "radian",
};

const toPint = (u: string): string => PINT[u] ?? u;

interface DynamicToolProps {
    tool: {
        tool_name?: string;
        workflow_name?: string;
        description: string;
        relation?: string;
        solve_for?: string;
        output_unit?: string;
        formula_latex?: string;
        inputs?: ToolInput[];
        outputs?: ToolOutput[];
        suggestions?: string[];
        steps?: any[]; // Workflow steps
    };
    onClose?: () => void;
}

export default function ToolCard({ tool, onClose }: DynamicToolProps) {
    const [inputs, setInputs] = useState<Record<string, any>>(() => {
        const defaults: Record<string, any> = {};
        if (tool.inputs) {
            tool.inputs.forEach((inp) => {
                defaults[inp.name] = inp.default_value ?? "";
                defaults[`${inp.name}_unit`] = inp.unit || (inp.unit_type ? UNITS[inp.unit_type]?.[0] : "");
            });
        }
        return defaults;
    });

    const [result, setResult] = useState<{ value: string; unit: string; raw: number } | null>(null);
    const [workflowResults, setWorkflowResults] = useState<Record<string, { value: number; unit: string }>>({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const isWorkflow = !!tool.steps;

    const executeWorkflow = async () => {
        if (!tool.steps) return;
        setLoading(true);
        setError(null);

        const results: Record<string, { value: number; unit: string }> = {};

        for (const step of tool.steps) {
            const resolvedInputs: Record<string, any> = {};
            for (const [key, val] of Object.entries(step.inputs)) {
                if (typeof val === "string" && val.startsWith("step_")) {
                    const refStepId = val.split(".")[0];
                    if (results[refStepId]) {
                        resolvedInputs[key] = results[refStepId].value;
                    } else {
                        setError(`Dependency for step ${step.step_id} failed`);
                        setLoading(false);
                        return;
                    }
                } else if (typeof val === "string" && isNaN(Number(val))) {
                    resolvedInputs[key] = val; // e.g. "10 mm" — Pint parses it
                } else {
                    resolvedInputs[key] = Number(val);
                }
            }

            try {
                const res = await fetch(`${API_BASE}/api/workflow/step`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        relation_name: step.relation,
                        target_var: step.solve_for,
                        inputs: resolvedInputs,
                    }),
                });
                if (!res.ok) throw new Error("Step failed");
                const data = await res.json();
                results[`step_${step.step_id}`] = { value: data.result, unit: data.unit };
                setWorkflowResults({ ...results });
            } catch (e) {
                setError(`Step ${step.step_id} calculation failed`);
                break;
            }
        }
        setLoading(false);
    };

    const handleChange = (name: string, value: string) => {
        setInputs((prev) => ({ ...prev, [name]: value }));
        setError(null);
    };

    const handleUnitChange = (name: string, unit: string) => {
        setInputs((prev) => ({ ...prev, [`${name}_unit`]: unit }));
    };

    // Build the kernel payload: {varName: {value, unit}} for each known input
    // (every input except the one we solve for).
    const buildKernelInputs = useCallback(() => {
        const payload: Record<string, { value: number; unit: string }> = {};
        (tool.inputs || []).forEach((inp) => {
            if (inp.name === tool.solve_for) return;
            const raw = inputs[inp.name];
            const value = parseFloat(raw);
            if (isNaN(value)) return;
            const unit = inputs[`${inp.name}_unit`] || inp.unit || "";
            payload[inp.name] = { value, unit: toPint(unit) };
        });
        return payload;
    }, [inputs, tool.inputs, tool.solve_for]);

    // Server-side compute via the physics kernel. No client-side formula execution.
    const compute = useCallback(async () => {
        if (!tool.relation || !tool.solve_for) {
            setError("This calculator is missing its relation definition.");
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/calculate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    relation: tool.relation,
                    solve_for: tool.solve_for,
                    output_unit: tool.output_unit || tool.outputs?.[0]?.unit,
                    inputs: buildKernelInputs(),
                }),
            });
            const data = await res.json();
            if (data.error) {
                setError(data.error);
                setResult(null);
            } else {
                setResult({ value: String(data.value), unit: data.unit, raw: data.raw });
            }
        } catch (e) {
            setError("Connection Error - Server unavailable");
            setResult(null);
        } finally {
            setLoading(false);
        }
    }, [tool.relation, tool.solve_for, tool.output_unit, tool.outputs, buildKernelInputs]);

    // Debounced auto-recompute as the user edits inputs (single-calc only).
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    useEffect(() => {
        if (isWorkflow || !tool.relation) return;
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            compute();
        }, 400);
        return () => {
            if (debounceRef.current) clearTimeout(debounceRef.current);
        };
    }, [inputs, isWorkflow, tool.relation, compute]);

    return (
        <div className="bg-card/95 backdrop-blur-xl border border-border rounded-2xl p-6 shadow-xl w-full max-w-md my-4 animate-in fade-in slide-in-from-bottom-4 duration-500 ring-1 ring-black/5 dark:ring-white/5 transition-colors">
            <div className="flex justify-between items-center mb-4 border-b border-border pb-3">
                <h3 className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-cyan-400 flex items-center gap-2">
                    {isWorkflow ? <Calculator className="text-blue-500" size={20} /> : null}
                    {isWorkflow ? tool.workflow_name : tool.tool_name}
                </h3>
                {onClose && (
                    <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors p-1 hover:bg-muted rounded-full">✕</button>
                )}
            </div>

            <p className="text-muted-foreground text-sm mb-4 leading-relaxed">{tool.description}</p>

            {isWorkflow ? (
                <div className="space-y-4">
                    {tool.steps?.map((step) => (
                        <div key={step.step_id} className="border border-border rounded-lg p-3 bg-muted/30">
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-xs font-mono text-muted-foreground">Step {step.step_id}</span>
                                <span className="text-xs font-semibold text-blue-600 dark:text-blue-400">{step.relation}</span>
                            </div>
                            {step.explanation && (
                                <p className="text-muted-foreground text-sm italic mb-3 border-l-2 border-border pl-2">
                                    {step.explanation}
                                </p>
                            )}
                            <div className="text-sm font-mono mb-2">
                                Solving for: <span className="font-bold">{step.solve_for}</span>
                            </div>
                            {workflowResults[`step_${step.step_id}`] ? (
                                <div className="mt-2 bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-300 p-2 rounded text-sm font-mono flex justify-between">
                                    <span>Result:</span>
                                    <span>{workflowResults[`step_${step.step_id}`].value.toFixed(4)} {workflowResults[`step_${step.step_id}`].unit}</span>
                                </div>
                            ) : (
                                <div className="text-xs text-muted-foreground italic">Pending...</div>
                            )}
                        </div>
                    ))}

                    {error && (
                        <div className="text-red-500 text-sm flex items-center gap-1 font-sans p-2 bg-red-50 dark:bg-red-900/10 rounded">
                            <AlertCircle size={14} />
                            {error}
                        </div>
                    )}

                    <button
                        onClick={executeWorkflow}
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-all shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                        {loading ? "Running Analysis..." : (
                            <>
                                <Calculator size={18} />
                                Run Analysis Chain
                            </>
                        )}
                    </button>
                </div>
            ) : (
                <>
                    {tool.formula_latex && (
                        <div className="bg-muted/50 p-4 rounded-xl mb-6 flex justify-center overflow-x-auto text-foreground border border-border shadow-inner">
                            <BlockMath math={tool.formula_latex} />
                        </div>
                    )}

                    <div className="space-y-5">
                        {tool.inputs?.filter((inp) => inp.name !== tool.solve_for).map((inp) => (
                            <div key={inp.name} className="flex flex-col">
                                <label className="text-xs uppercase font-bold text-muted-foreground mb-1.5 ml-1">{inp.label}</label>
                                <div className="flex items-center shadow-sm">
                                    <input
                                        type={inp.type}
                                        className="bg-background border border-border text-foreground rounded-l-xl p-3 flex-grow focus:outline-none focus:ring-2 focus:ring-blue-500/50 min-w-0 transition-all font-mono text-sm"
                                        placeholder={String(inp.default_value || "0.00")}
                                        value={inputs[inp.name]}
                                        onChange={(e) => handleChange(inp.name, e.target.value)}
                                    />
                                    {inp.unit_type || inp.unit ? (
                                        <div className="relative">
                                            {(inp.unit_type && UNITS[inp.unit_type]) ? (
                                                <select
                                                    value={inputs[`${inp.name}_unit`]}
                                                    onChange={(e) => handleUnitChange(inp.name, e.target.value)}
                                                    className="appearance-none bg-muted hover:bg-muted/80 text-muted-foreground px-4 py-3 rounded-r-xl text-sm border border-l-0 border-border focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer font-medium transition-colors pr-8"
                                                >
                                                    {UNITS[inp.unit_type].map(u => (
                                                        <option key={u} value={u}>{u}</option>
                                                    ))}
                                                </select>
                                            ) : (
                                                <span className="bg-muted text-muted-foreground px-4 py-3 rounded-r-xl text-sm border border-l-0 border-border font-medium block">
                                                    {inp.unit || "-"}
                                                </span>
                                            )}
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Result Display */}
                    <div className="mt-8 flex justify-between items-center bg-muted/30 p-4 rounded-xl border border-border/50">
                        <div className="flex flex-col">
                            <span className="text-xs font-semibold text-muted-foreground uppercase mb-1">Result</span>
                            <div className="text-2xl font-mono font-bold flex gap-2 items-baseline">
                                {error ? (
                                    <span className="text-red-500 text-sm flex items-center gap-1 font-sans">
                                        <AlertCircle size={14} />
                                        {error}
                                    </span>
                                ) : result ? (
                                    <>
                                        <span className="text-green-600 dark:text-green-400">{result.value}</span>
                                        <span className="text-sm text-muted-foreground font-sans">{result.unit}</span>
                                    </>
                                ) : (
                                    <span className="text-muted-foreground/50">--</span>
                                )}
                            </div>
                        </div>

                        <button
                            onClick={compute}
                            disabled={loading}
                            className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg font-semibold text-sm transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50 disabled:shadow-none active:scale-95"
                        >
                            {loading ? "Calculating..." : "Calculate"}
                        </button>
                    </div>

                    {/* Proactive Suggestions */}
                    {tool.suggestions && tool.suggestions.length > 0 && (
                        <div className="mt-6 pt-4 border-t border-border">
                            <div className="flex items-center gap-2 text-amber-500 dark:text-amber-400 text-xs font-bold mb-3 uppercase tracking-wide">
                                <Lightbulb size={14} className="fill-current" />
                                <span>AI Suggestions</span>
                            </div>
                            <ul className="space-y-3">
                                {tool.suggestions.map((suggestion, i) => (
                                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-3 bg-muted/30 p-2.5 rounded-lg border border-border/30">
                                        <span className="text-amber-500 dark:text-amber-400 mt-0.5 text-lg leading-none">•</span>
                                        <span className="leading-relaxed">{suggestion}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
