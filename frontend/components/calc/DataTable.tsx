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
            <div className="text-xs text-muted-foreground mb-1.5">{table.title}</div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="text-xs text-muted-foreground">
                        <tr>
                            {hasStatus && <th className="w-6" />}
                            {table.columns.map((c) => (
                                <th key={c.key} className="pr-4 py-1.5 text-left font-normal whitespace-nowrap">
                                    {c.label}{c.unit ? <span className="opacity-60"> ({c.unit})</span> : null}
                                </th>
                            ))}
                            {hasLinks && <th className="pr-4 py-1.5 text-left font-normal">Source</th>}
                        </tr>
                    </thead>
                    <tbody className="tabular-nums">
                        {rows.map((row, i) => (
                            <tr key={i} className={`border-t border-border/60 ${isHighlight(row) ? "bg-blue-500/[0.06] font-medium" : ""} ${row._status === "fail" ? "text-muted-foreground" : ""}`}>
                                {hasStatus && (
                                    <td className="pr-2 w-4">
                                        <span className={`inline-block w-2 h-2 rounded-full ${STATUS_DOT[row._status] || "bg-muted"}`} />
                                    </td>
                                )}
                                {table.columns.map((c) => (
                                    <td key={c.key} className="pr-4 py-1.5 whitespace-nowrap">{cell(row[c.key])}</td>
                                ))}
                                {hasLinks && (
                                    <td className="pr-4 py-1.5 whitespace-nowrap">
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
                {table.note ? <p className="text-xs text-muted-foreground">{table.note}</p> : <span />}
                {table.rows.length > maxRows && (
                    <button onClick={() => setExpanded(!expanded)} className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 decoration-border shrink-0 ml-3">
                        {expanded ? "Show fewer" : `Show all ${table.rows.length}`}
                    </button>
                )}
            </div>
        </div>
    );
}
