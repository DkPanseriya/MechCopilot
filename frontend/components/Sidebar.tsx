"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { PlusCircle, MessageSquare, History, Trash2, Pencil, Check, X, Database } from "lucide-react";
import { Session } from "@/types";
import { ThemeToggle } from "@/components/ThemeToggle";
import { API_BASE } from "@/lib/api";

export default function Sidebar() {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editTitle, setEditTitle] = useState("");
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        fetchSessions();
    }, [pathname]); // Refresh when path changes (e.g. after creating new session)

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
                if (pathname === `/chat/${id}`) {
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
                <Link href="/" className="flex items-center gap-2">
                    <h1 className="text-xl font-bold tracking-tight text-blue-500">MechPartner <span className="text-xs text-gray-500 font-normal">v0.2</span></h1>
                </Link>
            </div>

            <Link
                href="/"
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-all mb-2"
            >
                <PlusCircle size={16} />
                New Design Session
            </Link>

            <Link
                href="/materials"
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all mb-6 ${pathname === "/materials" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
            >
                <Database size={16} />
                Materials Library
            </Link>

            <div className="flex-1 overflow-y-auto pr-2" suppressHydrationWarning>
                <div className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wider px-2">History</div>
                <div className="space-y-1">
                    {sessions.map((session) => (
                        <Link
                            key={session.id}
                            href={`/chat/${session.id}`}
                            className={`group block px-3 py-2 rounded-lg text-sm truncate transition-colors relative ${pathname === `/chat/${session.id}`
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
                    <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">JD</div>
                    <div className="text-sm">
                        <div className="font-medium text-foreground">John Doe</div>
                        <div className="text-[10px] text-muted-foreground uppercase">Pro Plan</div>
                    </div>
                    <div className="ml-auto">
                        <ThemeToggle />
                    </div>
                </div>
            </div>
        </div >
    );
}
