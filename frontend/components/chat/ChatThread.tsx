"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import {
    AlertTriangle, ArrowUp, Bot, ChevronDown, ChevronRight, Download, Loader2, Sparkles,
} from "lucide-react";
import { API_BASE } from "@/lib/api";
import CalculatorView from "@/components/calc/CalculatorView";
import OnboardingModal, { type Profile } from "@/components/OnboardingModal";
import ClarifyForm, { type Clarify } from "@/components/chat/ClarifyForm";
import type { Provenance } from "@/types/calculator";

type Tool = {
    type: string; calculator?: string; title?: string; inputs?: Record<string, any>; purpose?: string;
    provenance?: Provenance; example?: boolean; provisional?: string[];
    // inputs the user changed in the card, stored with the reply and re-run on the server
    edited?: { inputs: Record<string, any>; changed: string[]; verdict: string };
};

interface ChatMessage {
    id?: number;
    role: "user" | "assistant";
    content: string;
    tools: Tool[];
    notices: string[];
    assumptions: string[];
    missing: string[];
    clarify?: Clarify;
    status?: string;
    pending?: boolean;
}

// Starting points: picking one tells the copilot what you're working on; it then asks for
// the loads, sizes and constraints it needs instead of assuming them.
const TOPICS = [
    { title: "Bolted joint", hint: "Size, class, preload, torque", says: "a bolted joint" },
    { title: "Bearings", hint: "Selection, life, part numbers", says: "a bearing arrangement" },
    { title: "Shaft", hint: "Fatigue, critical speed, keys", says: "a shaft" },
    { title: "Beam or frame", hint: "Stress, deflection, profiles", says: "a beam or frame member" },
    { title: "Fit or press fit", hint: "ISO fits, torque capacity", says: "a fit or press fit between a shaft and hub" },
    { title: "Gear pair", hint: "Bending and contact strength", says: "a spur gear pair" },
    { title: "Spring", hint: "Compression or torsion", says: "a spring" },
    { title: "Welded joint", hint: "Fillet weld groups", says: "a welded joint" },
    { title: "Pressure vessel or pipe", hint: "Wall stress, thickness", says: "a pressure vessel or pipe" },
];

function fromStored(m: any): ChatMessage {
    const td = m.tool_data;
    // Only library calculators are rendered; anything else (pre-v1 widgets) shows as text only.
    const tools = td && Array.isArray(td.tools) ? td.tools.filter((t: Tool) => t.type === "calc" && t.calculator) : [];
    return {
        id: m.id ?? undefined,
        role: m.role === "user" ? "user" : "assistant",
        content: m.content || "",
        tools,
        notices: td?.notices || [],
        assumptions: td?.assumptions || [],
        missing: td?.missing || [],
        clarify: td?.clarify || undefined,
    };
}

function AssistantMeta({ m }: { m: ChatMessage }) {
    const [open, setOpen] = useState(false);
    if (!m.assumptions.length && !m.missing.length) return null;
    return (
        <div className="mt-3 border-t border-border/60 pt-2">
            <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground">
                {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                Assumptions{m.assumptions.length ? ` (${m.assumptions.length})` : ""}{m.missing.length ? ` · missing info (${m.missing.length})` : ""}
            </button>
            {open && (
                <ul className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
                    {m.assumptions.map((a, i) => <li key={`a${i}`}>· {a}</li>)}
                    {m.missing.map((a, i) => <li key={`m${i}`} className="text-amber-600 dark:text-amber-400">· Needed: {a}</li>)}
                </ul>
            )}
        </div>
    );
}

export default function ChatThread({ sessionId: initialId }: { sessionId: number | null }) {
    const [sid, setSid] = useState<number | null>(initialId);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [tier, setTier] = useState<"efficient" | "deep">("efficient");
    const [profile, setProfile] = useState<Profile | null>(null);
    const [showOnboarding, setShowOnboarding] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    const textRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        try {
            const saved = localStorage.getItem("mech_copilot_profile");
            if (saved) setProfile(JSON.parse(saved));
            else setShowOnboarding(true);
        } catch {
            setShowOnboarding(true);
        }
    }, []);

    useEffect(() => {
        if (!initialId) return;
        fetch(`${API_BASE}/api/sessions/${initialId}`)
            .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
            .then((d) => setMessages((d.messages || []).map(fromStored)))
            .catch(() => setLoadError("Could not load this session. Is the backend running on port 8001?"));
    }, [initialId]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, [messages.length, loading]);

    const patchLast = useCallback((fn: (m: ChatMessage) => ChatMessage) => {
        setMessages((prev) => {
            const next = [...prev];
            const i = next.length - 1;
            if (i >= 0 && next[i].role === "assistant") next[i] = fn(next[i]);
            return next;
        });
    }, []);

    const ensureSession = async (): Promise<number> => {
        if (sid) return sid;
        const res = await fetch(`${API_BASE}/api/sessions/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "New Chat", context_type: "general" }),
        });
        if (!res.ok) throw new Error("Could not create a session");
        const data = await res.json();
        setSid(data.id);
        window.history.replaceState(null, "", `/chat/${data.id}`);
        window.dispatchEvent(new Event("mech:sessions-changed"));
        return data.id;
    };

    const send = async (text: string) => {
        const message = text.trim();
        if (!message || loading) return;
        setInput("");
        setLoading(true);
        setMessages((prev) => [
            ...prev,
            { role: "user", content: message, tools: [], notices: [], assumptions: [], missing: [] },
            { role: "assistant", content: "", tools: [], notices: [], assumptions: [], missing: [], pending: true, status: "Thinking…" },
        ]);

        try {
            const id = await ensureSession();
            const res = await fetch(`${API_BASE}/api/sessions/${id}/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message, tier, user_profile: profile }),
            });
            if (!res.ok || !res.body) throw new Error(`Server returned ${res.status}`);

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            for (;;) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const frames = buffer.split("\n\n");
                buffer = frames.pop() ?? "";
                for (const frame of frames) {
                    const line = frame.split("\n").find((l) => l.startsWith("data: "));
                    if (!line) continue;
                    let ev: any;
                    try { ev = JSON.parse(line.slice(6)); } catch { continue; }
                    switch (ev.type) {
                        case "status": patchLast((m) => ({ ...m, status: ev.content })); break;
                        case "notice": patchLast((m) => ({ ...m, notices: [...m.notices, ev.content] })); break;
                        case "plan": patchLast((m) => ({ ...m, assumptions: ev.assumptions || [], missing: ev.missing || [] })); break;
                        case "tool": patchLast((m) => ({ ...m, tools: [...m.tools, ev.data] })); break;
                        case "clarify": patchLast((m) => ({ ...m, clarify: { message: ev.message, questions: ev.questions } })); break;
                        case "token": patchLast((m) => ({ ...m, content: m.content + ev.content, status: undefined })); break;
                        case "replace_content": patchLast((m) => ({ ...m, content: ev.content })); break;
                        case "error": patchLast((m) => ({ ...m, notices: [...m.notices, ev.content] })); break;
                        case "saved": patchLast((m) => ({ ...m, id: ev.id })); break;
                        case "done": patchLast((m) => ({ ...m, pending: false, status: undefined })); break;
                    }
                }
            }
        } catch (e: any) {
            patchLast((m) => ({ ...m, notices: [...m.notices, `Could not reach the backend: ${e?.message || e}`] }));
        } finally {
            patchLast((m) => ({ ...m, pending: false, status: undefined }));
            setLoading(false);
            window.dispatchEvent(new Event("mech:sessions-changed"));
            textRef.current?.focus();
        }
    };

    // Card edits are saved against the reply, so the next question sees them (and a reload
    // restores them). Debounced per card: typing a number fires one save, not one per key.
    const editTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
    const saveEdit = useCallback((messageId: number, index: number, calculator: string, inputs: Record<string, any>) => {
        const key = `${messageId}-${index}`;
        clearTimeout(editTimers.current.get(key));
        editTimers.current.set(key, setTimeout(() => {
            if (!sid) return;
            fetch(`${API_BASE}/api/sessions/${sid}/messages/${messageId}/tools/${index}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ calculator, inputs }),
            }).catch(() => { /* the card still works; the copilot just won't see this edit */ });
        }, 800));
    }, [sid]);

    const exportReport = async () => {
        if (!sid) return;
        const res = await fetch(`${API_BASE}/api/reports/${sid}`);
        if (!res.ok) return;
        const data = await res.json();
        const url = URL.createObjectURL(new Blob([data.markdown], { type: "text/markdown" }));
        const a = Object.assign(document.createElement("a"), { href: url, download: data.filename || "report.md" });
        a.click();
        URL.revokeObjectURL(url);
    };

    const empty = messages.length === 0 && !loadError;

    return (
        <div className="flex flex-col h-screen">
            <header className="flex-none flex items-center justify-between gap-3 px-6 py-3 border-b border-border">
                <div className="flex bg-muted rounded-lg p-0.5 border border-border">
                    {(["efficient", "deep"] as const).map((t) => (
                        <button key={t} onClick={() => setTier(t)}
                            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${tier === t ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>
                            {t === "efficient" ? "Fast" : "Deep review"}
                        </button>
                    ))}
                </div>
                {sid && messages.length > 0 && (
                    <button onClick={exportReport} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted">
                        <Download size={13} />Export report
                    </button>
                )}
            </header>

            <div className="flex-1 overflow-y-auto">
                <div className="max-w-4xl mx-auto px-4 md:px-6 py-6 space-y-6">
                    {loadError && <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-500">{loadError}</div>}

                    {empty && (
                        <div className="pt-10 md:pt-16">
                            <h1 className="text-3xl font-semibold text-foreground">What are you working on?</h1>
                            <p className="text-muted-foreground mt-2 max-w-2xl">
                                Describe the problem in your own words below: the part, the loads, the space you have and
                                what you need to decide. Or pick a starting point, and I’ll ask for what the calculation needs.
                            </p>
                            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 mt-8">
                                {TOPICS.map((t) => (
                                    <button key={t.title} onClick={() => send(`I'm working on ${t.says}.`)} disabled={loading}
                                        className="text-left rounded-xl border border-border bg-card px-4 py-3 hover:border-blue-500/50 transition-colors disabled:opacity-50">
                                        <div className="text-sm font-medium text-foreground">{t.title}</div>
                                        <div className="text-xs text-muted-foreground mt-0.5">{t.hint}</div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {messages.map((m, i) => (
                        <div key={i} className="space-y-3">
                            {m.role === "user" ? (
                                <div className="flex justify-end">
                                    <div className="max-w-[85%] rounded-2xl rounded-br-md bg-blue-600 text-white px-4 py-2.5 text-sm whitespace-pre-wrap">{m.content}</div>
                                </div>
                            ) : (
                                <div className="flex gap-3">
                                    <div className="w-8 h-8 rounded-full bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0 mt-0.5">
                                        <Bot size={16} />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        {m.notices.map((n, j) => (
                                            <div key={j} className="mb-2 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                                                <AlertTriangle size={13} className="mt-0.5 shrink-0" />{n}
                                            </div>
                                        ))}
                                        {m.content ? (
                                            <div className="prose max-w-none text-sm">
                                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{m.content}</ReactMarkdown>
                                            </div>
                                        ) : m.pending ? (
                                            <div className="flex items-center gap-2 text-sm text-muted-foreground py-1">
                                                <Loader2 size={14} className="animate-spin" />{m.status || "Thinking…"}
                                            </div>
                                        ) : null}
                                        {m.pending && m.content && m.status && (
                                            <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5"><Loader2 size={11} className="animate-spin" />{m.status}</div>
                                        )}
                                        {m.clarify && i === messages.length - 1 && !m.pending && (
                                            <ClarifyForm clarify={m.clarify} onSubmit={send} disabled={loading} />
                                        )}
                                        <AssistantMeta m={m} />
                                    </div>
                                </div>
                            )}
                            {m.role === "assistant" && m.tools.length > 0 && (
                                <div className="md:pl-11 space-y-4">
                                    {m.tools.map((t, j) => t.calculator && (
                                        <CalculatorView key={`${i}-${j}`} calculatorId={t.calculator} compact
                                            initial={{ ...t.inputs, ...t.edited?.inputs }} editedNames={t.edited?.changed}
                                            provenance={t.provenance} example={t.example} provisional={t.provisional}
                                            onEdit={m.id ? (inputs) => saveEdit(m.id!, j, t.calculator!, inputs) : undefined} />
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                    <div ref={bottomRef} />
                </div>
            </div>

            <div className="flex-none border-t border-border bg-background/90 backdrop-blur px-4 md:px-6 py-3">
                <form className="max-w-4xl mx-auto" onSubmit={(e) => { e.preventDefault(); send(input); }}>
                    <div className="flex items-end gap-2 rounded-2xl border border-border bg-muted/40 px-3 py-2 focus-within:ring-2 focus-within:ring-blue-500/40">
                        <Sparkles size={16} className="text-muted-foreground mb-2 shrink-0" />
                        <textarea
                            ref={textRef}
                            value={input}
                            rows={1}
                            onChange={(e) => {
                                setInput(e.target.value);
                                e.target.style.height = "auto";
                                e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
                            }}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
                            }}
                            placeholder="Describe the part, loads and what you need to decide…"
                            className="flex-1 resize-none bg-transparent text-sm py-1.5 focus:outline-none placeholder:text-muted-foreground max-h-44"
                        />
                        <button type="submit" disabled={!input.trim() || loading}
                            className="mb-0.5 w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                            aria-label="Send">
                            {loading ? <Loader2 size={15} className="animate-spin" /> : <ArrowUp size={16} />}
                        </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground text-center mt-2">
                        Calculations run on validated engineering formulas; the language model only chooses and explains them. Verify before manufacture.
                    </p>
                </form>
            </div>

            {showOnboarding && (
                <OnboardingModal onComplete={(p) => {
                    try { localStorage.setItem("mech_copilot_profile", JSON.stringify(p)); } catch { /* storage unavailable */ }
                    setProfile(p);
                    setShowOnboarding(false);
                }} />
            )}
        </div>
    );
}
