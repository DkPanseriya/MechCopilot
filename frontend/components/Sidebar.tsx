"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { PlusCircle, MessageSquare, History, Trash2, Pencil, Check, X, Database, Calculator, Settings } from "lucide-react";
import { Session } from "@/types";
import { ThemeToggle } from "@/components/ThemeToggle";
import { API_BASE } from "@/lib/api";

export default function Sidebar() {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editTitle, setEditTitle] = useState("");
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    // Chats live at /chat?id=N (query string, so the desktop app can ship pre-built pages).
    const activeChat = pathname?.startsWith("/chat") ? searchParams.get("id") : null;

    const [status, setStatus] = useState<{ provider: string; model: string; configured: boolean; calculators: number; key_valid: boolean | null } | null>(null);

    useEffect(() => {
        fetchSessions();
    }, [pathname]); // Refresh when path changes (e.g. after creating new session)

    useEffect(() => {
        const refresh = () => fetchSessions();
        const loadStatus = () =>
            fetch(`${API_BASE}/api/status`).then((r) => r.json()).then(setStatus).catch(() => setStatus(null));
        window.addEventListener("mech:sessions-changed", refresh);
        window.addEventListener("mech:status-changed", loadStatus);   // after Settings saves a key
        loadStatus();
        return () => {
            window.removeEventListener("mech:sessions-changed", refresh);
            window.removeEventListener("mech:status-changed", loadStatus);
        };
    }, []);

    // First run: no key and setup never finished or skipped -> show the setup page once.
    useEffect(() => {
        if (!status || status.configured || pathname?.startsWith("/setup")) return;
        let done = false;
        try { done = localStorage.getItem("mech_setup_done") === "1"; } catch { /* private mode: ask again */ }
        if (!done) router.replace("/setup");
    }, [status, pathname, router]);

    // "anthropic/claude-4.5-haiku" -> "Claude Haiku 4.5"; other slugs are shown as-is.
    const modelName = (m: string) => {
        const slug = m.split("/").pop() || m;
        const parts = slug.split("-");
        if (parts[0] !== "claude") return slug;
        const version = parts.find((p) => /^\d+(\.\d+)?$/.test(p)) || "";
        const family = parts.find((p) => /^[a-z]+$/.test(p) && p !== "claude") || "";
        return `Claude ${family.charAt(0).toUpperCase()}${family.slice(1)} ${version}`.replace(/\s+/g, " ").trim();
    };
    const keyRejected = status?.configured && status.key_valid === false;

    const fetchSessions = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/sessions/`);
            if (res.ok) {
                const data = await res.json();
                setSessions(data);
            }
        } catch (error) {
            console.error("Failed to fetch sessions", error);
        }
    };

    const deleteSession = async (e: React.MouseEvent, id: number) => {
        e.preventDefault();
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this chat?")) return;

        try {
            const res = await fetch(`${API_BASE}/api/sessions/${id}`, { method: "DELETE" });
            if (res.ok) {
                setSessions(prev => prev.filter(s => s.id !== id));
                if (activeChat === String(id)) {
                    router.push("/");
                }
            }
        } catch (error) {
            console.error(error);
        }
    };

    const startEditing = (e: React.MouseEvent, session: Session) => {
        e.preventDefault();
        e.stopPropagation();
        setEditingId(session.id);
        setEditTitle(session.title);
    };

    const saveTitle = async (e: React.MouseEvent, id: number) => {
        e.preventDefault();
        e.stopPropagation();
        try {
            const res = await fetch(`${API_BASE}/api/sessions/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: editTitle })
            });
            if (res.ok) {
                setSessions(prev => prev.map(s => s.id === id ? { ...s, title: editTitle } : s));
                setEditingId(null);
            }
        } catch (error) {
            console.error(error);
        }
    };

    const cancelEdit = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setEditingId(null);
    };

    return (
        <div suppressHydrationWarning className="w-64 border-r border-border p-4 flex flex-col bg-muted/40 h-screen fixed left-0 top-0 overflow-y-auto z-50 transition-colors duration-300">
            <div className="mb-8" suppressHydrationWarning>
                <a href="/" className="flex items-center gap-2">
                    <h1 className="text-xl font-bold tracking-tight text-foreground">Mech<span className="text-blue-500">Copilot</span> <span className="text-xs text-muted-foreground font-normal">v1.0</span></h1>
                </a>
            </div>

            {/* Full navigation so the chat state always resets, even if we're already on "/". */}
            <a
                href="/"
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-all mb-2"
            >
                <PlusCircle size={16} />
                New Design Session
            </a>

            <Link
                href="/calculators"
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all mb-1 ${pathname?.startsWith("/calculators") ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
            >
                <Calculator size={16} />
                Calculator Library
            </Link>

            <Link
                href="/materials"
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all mb-1 ${pathname === "/materials" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
            >
                <Database size={16} />
                Materials Library
            </Link>

            <Link
                href="/setup"
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all mb-6 ${pathname?.startsWith("/setup") ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
            >
                <Settings size={16} />
                Settings
            </Link>

            <div className="flex-1 overflow-y-auto pr-2" suppressHydrationWarning>
                <div className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wider px-2">History</div>
                <div className="space-y-1">
                    {sessions.map((session) => (
                        <Link
                            key={session.id}
                            href={`/chat?id=${session.id}`}
                            className={`group block px-3 py-2 rounded-lg text-sm truncate transition-colors relative ${activeChat === String(session.id)
                                ? "bg-primary/10 text-primary font-medium"
                                : "text-muted-foreground hover:bg-muted hover:text-foreground"
                                }`}
                        >
                            {editingId === session.id ? (
                                <div className="flex items-center gap-1" onClick={(e) => e.preventDefault()}>
                                    <input
                                        value={editTitle}
                                        onChange={(e) => setEditTitle(e.target.value)}
                                        className="bg-muted border border-blue-500 text-xs rounded px-1 py-0.5 w-full text-foreground focus:outline-none"
                                        autoFocus
                                        onClick={(e) => e.stopPropagation()}
                                    />
                                    <button onClick={(e) => saveTitle(e, session.id)} className="text-green-400 hover:text-green-300"><Check size={14} /></button>
                                    <button onClick={cancelEdit} className="text-red-400 hover:text-red-300"><X size={14} /></button>
                                </div>
                            ) : (
                                <div className="flex items-center gap-2 justify-between">
                                    <div className="flex items-center gap-2 truncate">
                                        <MessageSquare size={14} className="opacity-50 flex-shrink-0" />
                                        <span className="truncate">{session.title}</span>
                                    </div>
                                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={(e) => startEditing(e, session)}
                                            className="p-1 hover:text-blue-500 text-muted-foreground"
                                            title="Rename"
                                        >
                                            <Pencil size={12} />
                                        </button>
                                        <button
                                            onClick={(e) => deleteSession(e, session.id)}
                                            className="p-1 hover:text-red-500 text-muted-foreground"
                                            title="Delete"
                                        >
                                            <Trash2 size={12} />
                                        </button>
                                    </div>
                                </div>
                            )}
                        </Link>
                    ))}
                    {sessions.length === 0 && (
                        <div className="text-xs text-muted-foreground px-3 italic">No history yet.</div>
                    )}
                </div>
            </div>

            <div className="mt-auto pt-4 border-t border-border" suppressHydrationWarning>
                <div className="flex items-center gap-3 px-2">
                    <Link href="/setup" className="min-w-0 flex-1" title={keyRejected
                        ? "Your API key was rejected. Open Settings to paste a valid one."
                        : status?.configured
                            ? `Language model: ${status.model} via ${status.provider}`
                            : "No API key yet. Open Settings to add your own key for the full copilot. Calculators work without it."}>
                        <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                            <span className={`w-2 h-2 rounded-full shrink-0 ${status === null || keyRejected ? "bg-rose-500" : status.configured ? "bg-emerald-500" : "bg-amber-500"}`} />
                            <span className="truncate">
                                {status === null ? "Backend offline" : keyRejected ? "API key rejected" : status.configured ? modelName(status.model) : "Offline mode"}
                            </span>
                        </div>
                        <div className="text-[10px] text-muted-foreground truncate mt-0.5">
                            {status === null ? "Backend not reachable"
                                : keyRejected ? "Fix the key in Settings"
                                : status.configured ? `via ${status.provider} · ${status.calculators} calculators`
                                : "Add your key in Settings"}
                        </div>
                    </Link>
                    <ThemeToggle />
                </div>
            </div>
        </div >
    );
}
