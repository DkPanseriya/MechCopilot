"use client";

import { useState } from "react";
import { ExternalLink } from "lucide-react";
import type { RunTable } from "@/types/calculator";

const STATUS_DOT: Record<string, string> = {
    ok: "bg-emerald-500",
    warn: "bg-amber-500",
    fail: "bg-rose-500",
};

function cell(v: any): string {
    if (v === null || v === undefined || v === "") return "–";
    if (typeof v === "boolean") return v ? "yes" : "no";
    return String(v);
}

export default function DataTable({ table, maxRows = 12 }: { table: RunTable; maxRows?: number }) {
    const [expanded, setExpanded] = useState(false);
    const isHighlight = (row: Record<string, any>) =>
        !!table.highlight && Object.entries(table.highlight).every(([k, v]) => row[k] === v);
    const rows = expanded ? table.rows : table.rows.slice(0, maxRows);
    const hasLinks = table.rows.some((r) => r._links?.length);
    const hasStatus = table.rows.some((r) => r._status);

    return (
        <div>
            <div className="text-xs font-semibold text-foreground mb-2">{table.title}</div>
            <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-xs">
                    <thead className="bg-muted/60 text-muted-foreground">
                        <tr>
                            {hasStatus && <th className="w-6" />}
                            {table.columns.map((c) => (
                                <th key={c.key} className="px-3 py-2 text-left font-medium whitespace-nowrap">
                                    {c.label}{c.unit ? <span className="opacity-60"> ({c.unit})</span> : null}
                                </th>
                            ))}
                            {hasLinks && <th className="px-3 py-2 text-left font-medium">Source</th>}
                        </tr>
                    </thead>
                    <tbody className="font-mono tabular-nums">
                        {rows.map((row, i) => (
                            <tr key={i} className={`border-t border-border ${isHighlight(row) ? "bg-blue-500/10" : ""} ${row._status === "fail" ? "opacity-50" : ""}`}>
                                {hasStatus && (
                                    <td className="pl-3">
                                        <span className={`inline-block w-2 h-2 rounded-full ${STATUS_DOT[row._status] || "bg-muted"}`} />
                                    </td>
                                )}
                                {table.columns.map((c) => (
                                    <td key={c.key} className="px-3 py-1.5 whitespace-nowrap">{cell(row[c.key])}</td>
                                ))}
                                {hasLinks && (
                                    <td className="px-3 py-1.5 whitespace-nowrap font-sans">
                                        {(row._links || []).map((l: { label: string; url: string }) => (
                                            <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1 text-blue-500 hover:text-blue-400 mr-3">
                                                {l.label}<ExternalLink size={11} />
                                            </a>
                                        ))}
                                    </td>
                                )}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <div className="flex items-center justify-between mt-1.5">
                {table.note ? <p className="text-[11px] text-muted-foreground italic">{table.note}</p> : <span />}
                {table.rows.length > maxRows && (
                    <button onClick={() => setExpanded(!expanded)} className="text-[11px] text-blue-500 hover:text-blue-400 shrink-0 ml-3">
                        {expanded ? "Show fewer" : `Show all ${table.rows.length}`}
                    </button>
                )}
            </div>
        </div>
    );
}
