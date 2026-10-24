"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import CalculatorView from "@/components/calc/CalculatorView";

// /calculators/view?id=… — a query string so the desktop app can ship pre-built pages.
function Calculator() {
    const id = useSearchParams().get("id") ?? "";
    return (
        <div className="max-w-7xl mx-auto px-6 py-8">
            <Link href="/calculators" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-5">
                <ArrowLeft size={13} />All calculators
            </Link>
            <CalculatorView key={id} calculatorId={id} />
        </div>
    );
}

export default function CalculatorPage() {
    return <Suspense fallback={null}><Calculator /></Suspense>;
}
