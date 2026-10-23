"use client";

import { useState } from "react";

export type Profile = { careerStage: string; focusArea: string };

const STAGES = [
    { id: "student", label: "Student", desc: "Learning core concepts" },
    { id: "junior", label: "Junior engineer", desc: "0–3 years" },
    { id: "mid", label: "Mid-level", desc: "3–10 years" },
    { id: "senior", label: "Senior / principal", desc: "10+ years" },
];

const AREAS = [
    { id: "general", label: "General mechanical design" },
    { id: "machinery", label: "Heavy machinery & equipment" },
    { id: "consumer", label: "Consumer products" },
    { id: "auto_aero", label: "Automotive / aerospace" },
    { id: "structural", label: "Structural / civil" },
    { id: "robotics", label: "Robotics & automation" },
    { id: "r_and_d", label: "Research & development" },
];

export default function OnboardingModal({ onComplete }: { onComplete: (profile: Profile) => void }) {
    const [careerStage, setCareerStage] = useState("mid");
    const [focusArea, setFocusArea] = useState("general");

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
            <div className="bg-card border border-border rounded-2xl p-7 max-w-lg w-full shadow-2xl">
                <h2 className="text-xl font-semibold text-foreground">Welcome to MechPartner</h2>
                <p className="text-sm text-muted-foreground mt-1.5 mb-6">
                    Tell me your experience level so I can pitch explanations right. You can change this anytime.
                </p>
                <form className="space-y-5" onSubmit={(e) => { e.preventDefault(); onComplete({ careerStage, focusArea }); }}>
                    <div>
                        <div className="text-xs font-medium text-muted-foreground mb-2">Experience</div>
                        <div className="grid grid-cols-2 gap-2">
                            {STAGES.map((s) => (
                                <button type="button" key={s.id} onClick={() => setCareerStage(s.id)}
                                    className={`p-3 rounded-xl border text-left transition-colors ${careerStage === s.id
                                        ? "border-blue-500 bg-blue-500/10 text-foreground"
                                        : "border-border text-muted-foreground hover:border-blue-500/40"}`}>
                                    <div className="text-sm font-medium">{s.label}</div>
                                    <div className="text-xs opacity-70 mt-0.5">{s.desc}</div>
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <div className="text-xs font-medium text-muted-foreground mb-2">Focus area</div>
                        <select value={focusArea} onChange={(e) => setFocusArea(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40">
                            {AREAS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
                        </select>
                    </div>
                    <div className="flex items-center gap-3 pt-1">
                        <button type="submit" className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium py-2.5 rounded-xl transition-colors">
                            Start designing
                        </button>
                        <button type="button" onClick={() => onComplete({ careerStage: "mid", focusArea: "general" })}
                            className="text-sm text-muted-foreground hover:text-foreground px-3 py-2.5">
                            Skip
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
