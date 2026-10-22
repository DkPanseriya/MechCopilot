"use client";

import { useEffect, useState } from "react";
import { Search, Filter, ArrowUpDown } from "lucide-react";
import { API_BASE } from "@/lib/api";

interface Material {
    id: string;
    name: string;
    category: string;
    sub_category: string;
    density: number;
    yield_strength: number;
    ultimate_strength: number;
    elastic_modulus: number;
    thermal_conductivity: number;
    cost_approx_usd_per_kg: number;
    description: string;
    source_citation?: string;
}

export default function MaterialsPage() {
    const [materials, setMaterials] = useState<Material[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [minYield, setMinYield] = useState<number>(0);
    const [categoryFilter, setCategoryFilter] = useState<string>("All");

    useEffect(() => {
        fetchMaterials();
    }, []);

    const fetchMaterials = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/materials/`);
            const data = await res.json();
            setMaterials(data);
        } catch (error) {
            console.error("Failed to load materials", error);
        } finally {
            setLoading(false);
        }
    };

    const filteredMaterials = materials.filter(m => {
        const matchesSearch = m.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            m.sub_category.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesCategory = categoryFilter === "All" || m.category === categoryFilter;
        // Convert Pa to MPa for easier filtering inputs if typically MPa, relying on raw logic for now
        // Yield is in Pa. Let's assume user slider is in MPa?
        // Let's make the slider MPa.
        const matchesYield = (m.yield_strength / 1e6) >= minYield;

        return matchesSearch && matchesCategory && matchesYield;
    });

    const formatNumber = (num: number) => new Intl.NumberFormat().format(num);

    return (
        <main className="flex min-h-screen bg-background text-foreground font-sans p-8 ml-64">
            <div className="max-w-6xl mx-auto w-full">
                <header className="mb-8">
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-cyan-400 mb-2">
                        Materials Library
                    </h1>
                    <p className="text-muted-foreground">
                        Curated database of standard engineering materials.
                    </p>
                </header>

                {/* Filters */}
                <div className="bg-card border border-border rounded-xl p-4 mb-8 shadow-sm flex flex-wrap gap-4 items-end">
                    <div className="flex-1 min-w-[200px]">
                        <label className="text-xs font-semibold text-muted-foreground mb-1 block">Search</label>
                        <div className="relative">
                            <Search className="absolute left-3 top-2.5 text-muted-foreground" size={16} />
                            <input
                                type="text"
                                placeholder="Search materials..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full bg-muted border border-border rounded-lg pl-9 pr-4 py-2 text-sm focus:ring-2 focus:ring-blue-500/50 outline-none"
                            />
                        </div>
                    </div>

                    <div className="w-[150px]">
                        <label className="text-xs font-semibold text-muted-foreground mb-1 block">Category</label>
                        <select
                            value={categoryFilter}
                            onChange={(e) => setCategoryFilter(e.target.value)}
                            className="w-full bg-muted border border-border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/50 outline-none"
                        >
                            <option value="All">All Categories</option>
                            <option value="Metal">Metal</option>
                            <option value="Plastic">Plastic</option>
                        </select>
                    </div>

                    <div className="w-[200px]">
                        <div className="flex justify-between mb-1">
                            <label className="text-xs font-semibold text-muted-foreground">Min Yield Strength</label>
                            <span className="text-xs font-mono text-blue-500">{minYield} MPa</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="1000"
                            step="50"
                            value={minYield}
                            onChange={(e) => setMinYield(Number(e.target.value))}
                            className="w-full accent-blue-500 h-2 bg-muted rounded-lg appearance-none cursor-pointer"
                        />
                    </div>
                </div>

                {/* Grid */}
                {loading ? (
                    <div className="text-center py-20 text-muted-foreground">Loading library...</div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {filteredMaterials.map(m => (
                            <div key={m.id} className="bg-card border border-border rounded-xl p-5 hover:border-blue-500/50 transition-colors shadow-sm cursor-default group relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                                    <ArrowUpDown size={64} />
                                </div>

                                <div className="flex justify-between items-start mb-2">
                                    <span className="inline-block px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-[10px] font-bold uppercase tracking-wider rounded">
                                        {m.sub_category}
                                    </span>
                                    <span className="text-xs text-muted-foreground font-mono">
                                        ~${m.cost_approx_usd_per_kg.toFixed(2)}/kg
                                    </span>
                                </div>

                                <h3 className="text-lg font-bold mb-1 group-hover:text-blue-500 transition-colors">{m.name}</h3>
                                <div className="mb-4">
                                    <p className="text-xs text-muted-foreground line-clamp-2">{m.description}</p>
                                    {m.source_citation && (
                                        <p className="text-[10px] text-blue-500/80 mt-1 font-medium bg-blue-50 dark:bg-blue-900/10 inline-block px-1.5 py-0.5 rounded border border-blue-100 dark:border-blue-900/30">
                                            Source: {m.source_citation}
                                        </p>
                                    )}
                                </div>

                                <div className="grid grid-cols-2 gap-y-3 gap-x-2 text-sm">
                                    <div>
                                        <div className="text-[10px] text-muted-foreground uppercase">Yield Strength</div>
                                        <div className="font-mono font-semibold">{(m.yield_strength / 1e6).toFixed(0)} <span className="text-xs text-muted-foreground font-normal">MPa</span></div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-muted-foreground uppercase">Ultimate Strength</div>
                                        <div className="font-mono font-semibold">{(m.ultimate_strength / 1e6).toFixed(0)} <span className="text-xs text-muted-foreground font-normal">MPa</span></div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-muted-foreground uppercase">Elastic Modulus</div>
                                        <div className="font-mono font-semibold">{(m.elastic_modulus / 1e9).toFixed(0)} <span className="text-xs text-muted-foreground font-normal">GPa</span></div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-muted-foreground uppercase">Density</div>
                                        <div className="font-mono font-semibold">{formatNumber(m.density)} <span className="text-xs text-muted-foreground font-normal">kg/m³</span></div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {!loading && filteredMaterials.length === 0 && (
                    <div className="text-center py-20 bg-muted/20 rounded-xl border border-dashed border-border text-muted-foreground">
                        No materials found matching your filters.
                    </div>
                )}
            </div>
        </main>
    );
}
