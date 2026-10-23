"use client";

import ToolCard from "@/components/ToolCard";
import ChartWidget from "@/components/ChartWidget";
import FigureWidget from "@/components/FigureWidget";
import SelectorWidget from "@/components/SelectorWidget";
import CalculatorView from "@/components/calc/CalculatorView";
import { parseUISpec } from "@/types/uiSpec";
import type { ToolData } from "@/types";

/**
 * Renders a message's widget by its UISpec `type` (component registry).
 * Unknown/invalid specs fall back to the legacy ToolCard, never to eval.
 */
export default function WidgetRenderer({ toolData }: { toolData: ToolData & { ui_spec?: unknown } }) {
    const spec = parseUISpec(toolData.ui_spec);

    if (!spec) {
        // Legacy tool_data (calculator/workflow) without a valid UISpec.
        return <ToolCard tool={toolData as any} />;
    }

    switch (spec.type) {
        case "calc":
            return <CalculatorView calculatorId={spec.calculator} initial={spec.inputs} compact />;
        case "calculator":
        case "workflow":
            // ToolCard already understands this shape (relation/solve_for/steps).
            return <ToolCard tool={toolData as any} />;
        case "chart":
            return <ChartWidget spec={spec} />;
        case "figure":
            return <FigureWidget spec={spec} />;
        case "selector":
            return <SelectorWidget spec={spec} />;
        case "comparison":
            return (
                <div className="bg-card/95 border border-border rounded-2xl p-6 shadow-xl w-full max-w-2xl my-4">
                    <h3 className="text-base font-bold text-foreground mb-3">{spec.title}</h3>
                    <div className="overflow-x-auto rounded-lg border border-border">
                        <table className="w-full text-xs">
                            <thead className="bg-muted/50 text-muted-foreground">
                                <tr>{spec.columns.map((c) => <th key={c} className="px-3 py-2 text-left">{c}</th>)}</tr>
                            </thead>
                            <tbody className="font-mono">
                                {spec.options.map((o, i) => (
                                    <tr key={i} className="border-t border-border">
                                        {spec.columns.map((c) => <td key={c} className="px-3 py-1.5">{String((o as any)[c] ?? "—")}</td>)}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {spec.recommendation && <p className="text-sm text-green-600 dark:text-green-400 mt-3">Recommended: {spec.recommendation}</p>}
                </div>
            );
        case "material":
            return (
                <div className="bg-card/95 border border-border rounded-2xl p-6 shadow-xl w-full max-w-md my-4">
                    <h3 className="text-base font-bold text-foreground">{spec.title}</h3>
                    <p className="text-sm text-muted-foreground mt-2">{spec.material_key}</p>
                </div>
            );
        default:
            return <ToolCard tool={toolData as any} />;
    }
}
