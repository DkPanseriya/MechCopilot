"use client";

import { useState } from "react";

interface OnboardingModalProps {
    onComplete: (profile: { careerStage: string; focusArea: string }) => void;
}

export default function OnboardingModal({ onComplete }: OnboardingModalProps) {
    const [careerStage, setCareerStage] = useState("");
    const [focusArea, setFocusArea] = useState("");

    const handleSave = () => {
        if (careerStage && focusArea) {
            onComplete({ careerStage, focusArea });
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-950/80 backdrop-blur-md">
            <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 max-w-lg w-full shadow-2xl animate-in zoom-in-95 duration-300">
                <h2 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-cyan-300 mb-2">
                    Welcome to MechPartner
                </h2>
                <p className="text-gray-400 mb-8">
                    To provide the best engineering assistance, valid for your experience level, please tell us a bit about yourself.
                </p>

                <form
                    className="space-y-6"
                    onSubmit={(e) => {
                        e.preventDefault();
                        handleSave();
                    }}
                >
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-3">
                            Career Stage
                        </label>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {[
                                { id: "student", label: "Student", desc: "Learning core concepts" },
                                { id: "junior", label: "Junior Engineer", desc: "0-3 years experience" },
                                { id: "mid", label: "Mid-Level", desc: "3-10 years experience" },
                                { id: "senior", label: "Senior/Principal", desc: "10+ years experience" },
                            ].map((option) => (
                                <button
                                    type="button"
                                    key={option.id}
                                    onClick={() => setCareerStage(option.id)}
                                    className={`p-3 rounded-xl border text-left transition-all ${careerStage === option.id
                                        ? "bg-blue-600/20 border-blue-500 text-blue-100 ring-1 ring-blue-500/50"
                                        : "bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-750 hover:border-gray-600"
                                        }`}
                                >
                                    <div className="font-semibold text-sm">{option.label}</div>
                                    <div className="text-xs opacity-70 mt-0.5">{option.desc}</div>
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-3">
                            Focus Area
                        </label>
                        <select
                            value={focusArea}
                            onChange={(e) => setFocusArea(e.target.value)}
                            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        >
                            <option value="" disabled>Select your primary focus...</option>
                            <option value="general">General Mechanical Design</option>
                            <option value="machinery">Heavy Machinery & Equipment</option>
                            <option value="consumer">Consumer Electronics / Product Design</option>
                            <option value="auto_aero">Automotive / Aerospace</option>
                            <option value="structural">Structural / Civil</option>
                            <option value="robotics">Robotics & Automation</option>
                            <option value="r_and_d">Research & Development</option>
                        </select>
                    </div>

                    <button
                        type="submit"
                        disabled={!careerStage || !focusArea}
                        className="w-full mt-4 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold py-4 rounded-xl shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-[1.02] active:scale-[0.98]"
                    >
                        Initialize My Partner Space
                    </button>
                </form>
            </div>
        </div>
    );
}
