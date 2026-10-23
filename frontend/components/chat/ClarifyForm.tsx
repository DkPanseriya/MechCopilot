"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";

export interface ClarifyQuestion {
    id: string;
    label: string;
    unit: string;
    options: string[];
    placeholder: string;
}

export interface Clarify {
    message: string;
    questions: ClarifyQuestion[];
}

/** The copilot's questions about missing inputs, answered inline and sent back as one message. */
export default function ClarifyForm({ clarify, onSubmit, disabled }: {
    clarify: Clarify;
    onSubmit: (text: string) => void;
    disabled?: boolean;
}) {
    const [values, setValues] = useState<Record<string, string>>({});
    const set = (id: string, v: string) => setValues((prev) => ({ ...prev, [id]: v }));

    const answered = clarify.questions.filter((q) => (values[q.id] || "").trim());
    const compose = (typical: boolean) => {
        const lines = answered.map((q) => {
            const v = values[q.id].trim();
            const hasUnit = q.unit && !/[a-zA-Z°%]\s*$/.test(v);
            return `${q.label}: ${v}${hasUnit ? ` ${q.unit}` : ""}`;
        });
        if (typical) lines.push(lines.length ? "Use typical values for anything I haven't given." : "Use typical values and go ahead.");
        onSubmit(lines.join("\n"));
    };

    return (
        <form
            className="mt-3 rounded-xl border border-border bg-card p-4 space-y-3"
            onSubmit={(e) => { e.preventDefault(); if (answered.length) compose(false); }}
        >
            {clarify.questions.map((q, i) => (
                <div key={q.id}>
                    <label htmlFor={`cq-${q.id}`} className="block text-xs font-medium text-foreground mb-1.5">{q.label}</label>
                    {q.options.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={q.label}>
                            {q.options.map((o) => {
                                const on = values[q.id] === o;
                                return (
                                    <button key={o} type="button" role="radio" aria-checked={on} disabled={disabled}
                                        onClick={() => set(q.id, on ? "" : o)}
                                        className={`px-3 py-1.5 rounded-lg border text-xs transition-colors ${on
                                            ? "border-blue-500 bg-blue-500/10 text-foreground"
                                            : "border-border text-muted-foreground hover:text-foreground hover:border-blue-500/40"}`}>
                                        {o}
                                    </button>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="flex items-stretch max-w-xs rounded-lg border border-border bg-background overflow-hidden focus-within:ring-2 focus-within:ring-blue-500/40">
                            <input
                                id={`cq-${q.id}`}
                                autoFocus={i === 0}
                                disabled={disabled}
                                value={values[q.id] || ""}
                                onChange={(e) => set(q.id, e.target.value)}
                                placeholder={q.placeholder ? `e.g. ${q.placeholder}` : ""}
                                className="flex-1 min-w-0 bg-transparent px-3 py-2 text-sm font-mono tabular-nums focus:outline-none placeholder:font-sans placeholder:text-muted-foreground/70"
                            />
                            {q.unit && <span className="flex items-center bg-muted/60 text-muted-foreground text-xs px-2.5 border-l border-border">{q.unit}</span>}
                        </div>
                    )}
                </div>
            ))}
            <div className="flex flex-wrap items-center gap-2 pt-1">
                <button type="submit" disabled={disabled || !answered.length}
                    className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium disabled:opacity-40 disabled:cursor-not-allowed">
                    Continue<ArrowRight size={13} />
                </button>
                <button type="button" disabled={disabled} onClick={() => compose(true)}
                    className="px-3 py-2 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40">
                    {answered.length ? "Assume the rest" : "Use typical values"}
                </button>
                <span className="text-[11px] text-muted-foreground">Skip any you don’t know.</span>
            </div>
        </form>
    );
}
