"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, ExternalLink, KeyRound, Loader2, Lock } from "lucide-react";
import { API_BASE } from "@/lib/api";

type Provider = "replicate" | "openai" | "none";
type Settings = {
    provider: "replicate" | "openai" | "offline"; configured: boolean; key_hint: string | null;
    models: Record<string, string>; model_defaults: Record<string, string>; settings_file: string;
};

const PROVIDERS: { id: Provider; label: string; desc: string }[] = [
    { id: "replicate", label: "Replicate (recommended)", desc: "Runs Claude models. Pay per question, about 3–5 US cents each." },
    { id: "openai", label: "OpenAI", desc: "Use an OpenAI API key instead." },
    { id: "none", label: "Calculators only", desc: "No AI. Every calculator, diagram and report still works." },
];

const KEY_INFO: Record<"replicate" | "openai", { placeholder: string; url: string; where: string }> = {
    replicate: { placeholder: "r8_…", url: "https://replicate.com/account/api-tokens", where: "replicate.com → Account → API tokens" },
    openai: { placeholder: "sk-…", url: "https://platform.openai.com/api-keys", where: "platform.openai.com → API keys" },
};

const MODEL_ROLES: { id: string; label: string }[] = [
    { id: "plan", label: "Plans the calculation (Fast)" },
    { id: "review", label: "Writes the answer (Fast)" },
    { id: "deep", label: "Every step in Deep review" },
];

const markDone = () => { try { localStorage.setItem("mech_setup_done", "1"); } catch { /* private mode */ } };

export default function SetupPage() {
    const [settings, setSettings] = useState<Settings | null>(null);
    const [loadError, setLoadError] = useState(false);
    const [provider, setProvider] = useState<Provider>("replicate");
    const [key, setKey] = useState("");
    const [models, setModels] = useState<Record<string, string>>({});
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [saved, setSaved] = useState<string | null>(null);

    useEffect(() => {
        fetch(`${API_BASE}/api/settings`)
            .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
            .then((s: Settings) => {
                setSettings(s);
                setProvider(s.provider === "offline" ? "replicate" : s.provider);
                setModels(s.models);
            })
            .catch(() => setLoadError(true));
    }, []);

    const keepsSavedKey = settings?.key_hint && settings.provider === provider;

    const save = async () => {
        setSaving(true); setError(null); setSaved(null);
        try {
            const res = await fetch(`${API_BASE}/api/settings`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ provider, api_key: key || null, models: provider === "replicate" ? models : null }),
            });
            const data = await res.json();
            if (!res.ok) { setError(data.detail || "Could not save the settings."); return; }
            setSettings(data);
            setKey("");
            markDone();
            window.dispatchEvent(new Event("mech:status-changed"));
            setSaved(provider === "none" ? "Saved. MechCopilot runs without AI; add a key here any time."
                : data.verified === null ? "Saved. The key could not be checked right now (no internet?); it will be used as soon as the provider is reachable."
                : "Key checked and saved.");
        } catch {
            setError("The MechCopilot backend is not reachable.");
        } finally {
            setSaving(false);
        }
    };

    if (loadError) {
        return <div className="max-w-2xl mx-auto px-6 py-10 text-sm text-rose-500">The MechCopilot backend is not reachable. Restart the app.</div>;
    }
    if (!settings) {
        return <div className="max-w-2xl mx-auto px-6 py-10 text-sm text-muted-foreground flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Loading settings…</div>;
    }

    const info = provider === "none" ? null : KEY_INFO[provider];

    return (
        <div className="max-w-2xl mx-auto px-6 py-10 space-y-8">
            <div>
                <h1 className="text-2xl font-semibold text-foreground">{settings.configured ? "Settings" : "Set up MechCopilot"}</h1>
                <p className="text-sm text-muted-foreground mt-2">
                    The copilot uses your own AI account, so you control the cost and nobody else&apos;s key is involved.
                    The calculators, diagrams and reports work without one.
                </p>
            </div>

            <section className="space-y-3">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">AI provider</h2>
                <div className="grid gap-2">
                    {PROVIDERS.map((p) => (
                        <button key={p.id} type="button" onClick={() => { setProvider(p.id); setError(null); setSaved(null); }}
                            className={`text-left rounded-xl border px-4 py-3 transition-colors ${provider === p.id ? "border-blue-500 bg-blue-500/5" : "border-border hover:bg-muted"}`}>
                            <div className="text-sm font-medium text-foreground">{p.label}</div>
                            <div className="text-xs text-muted-foreground mt-0.5">{p.desc}</div>
                        </button>
                    ))}
                </div>
            </section>

            {info && (
                <section className="space-y-3">
                    <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Your API key</h2>
                    <label className="block">
                        <div className="flex items-center rounded-lg border border-border bg-background focus-within:ring-2 focus-within:ring-blue-500/40">
                            <KeyRound size={14} className="ml-3 text-muted-foreground shrink-0" />
                            <input type="password" autoComplete="off" spellCheck={false} value={key}
                                onChange={(e) => setKey(e.target.value)}
                                placeholder={keepsSavedKey ? `Saved key ${settings.key_hint} — leave empty to keep it` : info.placeholder}
                                className="w-full bg-transparent px-3 py-2 text-sm focus:outline-none" />
                        </div>
                    </label>
                    <p className="text-xs text-muted-foreground">
                        Get one at <a href={info.url} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline inline-flex items-center gap-0.5">{info.where}<ExternalLink size={11} /></a>.
                    </p>
                    {provider === "replicate" && (
                        <details className="rounded-lg border border-border px-4 py-3">
                            <summary className="text-xs font-medium text-muted-foreground cursor-pointer">Models (advanced)</summary>
                            <div className="space-y-3 mt-3">
                                {MODEL_ROLES.map((r) => (
                                    <label key={r.id} className="block">
                                        <span className="block text-[11px] font-medium text-muted-foreground mb-1">{r.label}</span>
                                        <input value={models[r.id] ?? ""} placeholder={settings.model_defaults[r.id]}
                                            onChange={(e) => setModels((m) => ({ ...m, [r.id]: e.target.value }))}
                                            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/40" />
                                    </label>
                                ))}
                                <p className="text-[11px] text-muted-foreground">Any Replicate text model that accepts prompt, system_prompt and max_tokens works. Leave a field empty for the default.</p>
                            </div>
                        </details>
                    )}
                </section>
            )}

            <p className="flex items-start gap-2 text-xs text-muted-foreground">
                <Lock size={13} className="mt-px shrink-0" />
                <span>Your key is stored only on this computer, in <code className="text-[11px]">{settings.settings_file}</code>, and is sent only to the provider you chose when you ask a question.</span>
            </p>

            {error && <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-sm text-rose-600 dark:text-rose-400">{error}</div>}
            {saved && (
                <div className="flex items-center justify-between gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
                    <span className="flex items-center gap-2"><CheckCircle2 size={14} />{saved}</span>
                    <Link href="/" className="font-medium whitespace-nowrap hover:underline">Start designing →</Link>
                </div>
            )}

            <div className="flex items-center gap-3">
                <button onClick={save} disabled={saving || (provider !== "none" && !key && !keepsSavedKey)}
                    className="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 text-white text-sm font-medium px-4 py-2">
                    {saving && <Loader2 size={14} className="animate-spin" />}
                    {provider === "none" ? "Use calculators only" : "Check and save key"}
                </button>
                {!settings.configured && provider !== "none" && (
                    <Link href="/" onClick={markDone} className="text-sm text-muted-foreground hover:text-foreground">Skip for now</Link>
                )}
            </div>
        </div>
    );
}
