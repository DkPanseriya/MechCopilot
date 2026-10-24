"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ChatThread from "@/components/chat/ChatThread";

// /chat?id=N — a query string rather than /chat/N so the desktop app can ship pre-built pages.
function Chat() {
    const id = useSearchParams().get("id");
    const n = Number(id);
    return <ChatThread key={id ?? "new"} sessionId={id && Number.isFinite(n) ? n : null} />;
}

export default function ChatPage() {
    return <Suspense fallback={null}><Chat /></Suspense>;
}
