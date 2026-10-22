"use client";

import { useState, useRef, useEffect } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { Mic, Send, Bot } from "lucide-react";
import WidgetRenderer from "@/components/WidgetRenderer";
import { Message, SessionDetail, ToolData } from "@/types";
import { API_BASE } from "@/lib/api";

export default function ChatPage() {
    const params = useParams();
    const sessionId = params.id;

    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [tier, setTier] = useState<"efficient" | "deep">("efficient");
    const scrollRef = useRef<HTMLDivElement>(null);

    // Load Session History
    useEffect(() => {
        if (sessionId) {
            fetch(`${API_BASE}/api/sessions/${sessionId}`)
                .then((res) => res.json())
                .then((data: SessionDetail) => {
                    setMessages(data.messages || []);
                })
                .catch((err) => console.error(err));
        }
    }, [sessionId]);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [messages]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim()) return;

        const userMsg: Message = { role: "user", content: input };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        // Add placeholder for streaming
        setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

        try {
            const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: userMsg.content, tier }),
            });

            if (!res.body) throw new Error("No response body");

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let done = false;
            let assistantContent = "";
            let toolData: ToolData | undefined;

            while (!done) {
                const { value, done: doneReading } = await reader.read();
                done = doneReading;
                const chunkValue = decoder.decode(value, { stream: true });

                // Parse SSE format: data: {...}\n\n
                const lines = chunkValue.split("\n\n");
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const dataStr = line.replace("data: ", "");
                        if (!dataStr.trim()) continue;

                        try {
                            const data = JSON.parse(dataStr);

                            if (data.type === "token") {
                                assistantContent += data.content;
                                setMessages((prev) => {
                                    const newMsgs = [...prev];
                                    const lastMsg = newMsgs[newMsgs.length - 1];
                                    if (lastMsg.role === "assistant") {
                                        lastMsg.content = assistantContent;
                                    }
                                    return newMsgs;
                                });
                            } else if (data.type === "tool") {
                                toolData = data.data;
                                setMessages((prev) => {
                                    const newMsgs = [...prev];
                                    const lastMsg = newMsgs[newMsgs.length - 1];
                                    if (lastMsg.role === "assistant") {
                                        lastMsg.tool_data = data.data;
                                    }
                                    return newMsgs;
                                });
                            } else if (data.type === "replace_content") {
                                // Replace the entire content with the clean version (removes JSON)
                                assistantContent = data.content;
                                setMessages((prev) => {
                                    const newMsgs = [...prev];
                                    const lastMsg = newMsgs[newMsgs.length - 1];
                                    if (lastMsg.role === "assistant") {
                                        lastMsg.content = assistantContent;
                                    }
                                    return newMsgs;
                                });
                            } else if (data.type === "error") {
                                console.error("Stream error:", data.content);
                            }
                        } catch (e) {
                            console.error("Error parsing SSE data", e);
                        }
                    }
                }
            }

        } catch (err) {
            setMessages((prev) => {
                const newMsgs = [...prev];
                const lastMsg = newMsgs[newMsgs.length - 1];
                if (lastMsg.role === "assistant") {
                    lastMsg.content = "Error: Could not connect to the Design Partner Agent.";
                }
                return newMsgs;
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full w-full relative">
            {/* Header / Tier Selector */}
            <div className="flex-none p-4 flex justify-end">
                <div className="flex bg-muted rounded-lg p-1 border border-border shadow-sm transition-colors">
                    <button
                        onClick={() => setTier("efficient")}
                        className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-md transition-all ${tier === "efficient" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                    >
                        Efficient
                    </button>
                    <button
                        onClick={() => setTier("deep")}
                        className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-md transition-all ${tier === "deep" ? "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-200 border border-blue-200 dark:border-blue-800 shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                    >
                        Deep Think
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto px-4 md:px-8 space-y-6" ref={scrollRef}>
                <div className="max-w-4xl mx-auto space-y-6 pb-4">
                    {(!messages || messages.length === 0) && (
                        <div className="h-full flex items-center justify-center text-muted-foreground">
                            <p>Start the conversation...</p>
                        </div>
                    )}

                    {messages.map((msg, i) => {
                        const isLastMessage = i === messages.length - 1;
                        const isEmptyAssistant = msg.role === "assistant" && !msg.content;
                        const showThinking = isLastMessage && isEmptyAssistant && loading;

                        return (
                            <div key={i} className="flex flex-col gap-2">
                                <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                                    {msg.role === "assistant" && (
                                        <div className="w-8 h-8 rounded-full bg-teal-100 dark:bg-teal-900/30 flex items-center justify-center mr-3 mt-1 text-teal-700 dark:text-teal-400 border border-teal-200 dark:border-teal-800 flex-shrink-0">
                                            <Bot size={16} />
                                        </div>
                                    )}
                                    <div
                                        className={`max-w-[85%] rounded-2xl px-5 py-4 text-sm leading-relaxed shadow-sm ${msg.role === "user"
                                            ? "bg-blue-600 text-white rounded-br-none"
                                            : "bg-muted text-foreground rounded-bl-none border border-border"
                                            }`}
                                    >
                                        {showThinking ? (
                                            <div className="flex items-center gap-2 text-muted-foreground">
                                                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                            </div>
                                        ) : (
                                            <div className="prose dark:prose-invert prose-sm max-w-none">
                                                <ReactMarkdown>
                                                    {msg.content}
                                                </ReactMarkdown>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {msg.role === "assistant" && msg.tool_data && !showThinking && (
                                    <div className="md:pl-11">
                                        <WidgetRenderer toolData={msg.tool_data} />
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Input Area */}
            <div className="flex-none p-4 border-t border-border bg-background/80 backdrop-blur-md z-20">
                <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-2 items-center">

                    <button
                        type="button"
                        className="bg-muted hover:bg-secondary text-muted-foreground hover:text-foreground p-3 rounded-full transition-colors hidden md:flex"
                        title="Voice Input (Coming Soon)"
                    >
                        <Mic size={20} />
                    </button>

                    <div className="relative flex-1">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Type your engineering query..."
                            className="w-full bg-muted/50 border border-border text-foreground rounded-xl pl-4 pr-12 py-4 focus:outline-none focus:ring-2 focus:ring-blue-500/50 shadow-sm text-sm transition-all placeholder:text-muted-foreground"
                        />
                        <button
                            type="submit"
                            disabled={!input.trim() || loading}
                            className="absolute right-2 top-2 bg-blue-600 hover:bg-blue-500 text-white p-2 rounded-lg w-10 h-10 flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <Send size={18} />
                        </button>
                    </div>
                </form>
                <div className="text-center text-[10px] text-muted-foreground mt-2">
                    AI can make mistakes. Design Engineer verification required.
                </div>
            </div>

        </div>
    );
}
