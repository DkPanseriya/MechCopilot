"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import CalculatorView from "@/components/calc/CalculatorView";

export default function CalculatorPage() {
    const { id } = useParams<{ id: string }>();
    return (
        <div className="max-w-7xl mx-auto px-6 py-8">
            <Link href="/calculators" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-5">
                <ArrowLeft size={13} />All calculators
            </Link>
            <CalculatorView calculatorId={id} />
        </div>
    );
}
