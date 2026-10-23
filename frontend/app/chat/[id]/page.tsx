"use client";

import { useParams } from "next/navigation";
import ChatThread from "@/components/chat/ChatThread";

export default function ChatPage() {
    const { id } = useParams<{ id: string }>();
    const n = Number(id);
    return <ChatThread key={id} sessionId={Number.isFinite(n) ? n : null} />;
}
