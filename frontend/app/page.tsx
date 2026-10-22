"use client";

import { useState, useRef, useEffect } from "react";
import WidgetRenderer from "@/components/WidgetRenderer";
import OnboardingModal from "@/components/OnboardingModal";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css"; // Import Katex CSS
import { Mic, Send, Bot, User, History, FileText } from "lucide-react";
import { API_BASE } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  tool?: ToolData;
}

interface ToolData {
  tool_name: string;
  description: string;
  formula_latex?: string;
  inputs: any[];
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hello! I am your Mechanical Design Partner. Ask me to calculate stress, verify a beam, or check material properties." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [tier, setTier] = useState<"efficient" | "deep">("efficient");
  const [sessionId, setSessionId] = useState<number | null>(null);

  // User Profile State
  const [userProfile, setUserProfile] = useState<{ careerStage: string; focusArea: string } | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Check for saved profile on mount
    const savedProfile = localStorage.getItem("mech_copilot_profile");
    if (savedProfile) {
      try {
        setUserProfile(JSON.parse(savedProfile));
      } catch (e) {
        setShowOnboarding(true);
      }
    } else {
      setShowOnboarding(true);
    }

    // Check for saved session
    const savedSessionId = localStorage.getItem("mech_copilot_session_id");
    if (savedSessionId) {
      fetchSession(parseInt(savedSessionId));
    } else {
      createSession();
    }
  }, []);

  const createSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New Chat", context_type: "general" })
      });
      const data = await res.json();
      setSessionId(data.id);
      localStorage.setItem("mech_copilot_session_id", data.id.toString());
    } catch (e) {
      console.error("Failed to create session", e);
    }
  };

  const fetchSession = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${id}`);
      if (!res.ok) {
        // Session might be deleted or invalid, create new
        localStorage.removeItem("mech_copilot_session_id");
        createSession();
        return;
      }
      const data = await res.json();
      setSessionId(data.id);

      // Load messages
      if (data.messages) {
        // Transform backend messages to frontend format if needed
        // Backend: { role, content, tool_data }
        // Frontend: { role, content, tool }
        const formattedMessages = data.messages.map((m: any) => ({
          role: m.role,
          content: m.content || "",
          tool: m.tool_data ? m.tool_data : undefined
        }));
        setMessages(formattedMessages);
      }
    } catch (e) {
      console.error("Failed to fetch session", e);
      createSession();
    }
  };

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const handleOnboardingComplete = (profile: { careerStage: string; focusArea: string }) => {
    localStorage.setItem("mech_copilot_profile", JSON.stringify(profile));
    setUserProfile(profile);
    setShowOnboarding(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    if (!userProfile && showOnboarding) return;

    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // Create a placeholder assistant message
    const assistantMsgId = Date.now();
    setMessages((prev) => [...prev, { role: "assistant", content: "", tool: undefined }]);

    try {
      if (!sessionId) {
        // Should not happen if createSession works, but safe guard
        console.error("No session ID found");
        return;
      }

      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg.content,
          tier,
          user_profile: userProfile
        }),
      });

      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let assistantContent = "";

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
                  // Update the last message (the placeholder)
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  if (lastMsg.role === "assistant") {
                    lastMsg.content = assistantContent;
                  }
                  return newMsgs;
                });
              } else if (data.type === "tool") {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  if (lastMsg.role === "assistant") {
                    lastMsg.tool = data.data;
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
      setMessages((prev) => [...prev, { role: "assistant", content: "Error: Could not connect to the Design Partner Agent." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    if (!sessionId) return;
    try {
      const res = await fetch(`${API_BASE}/api/reports/${sessionId}`);
      const data = await res.json();

      // Trigger Download
      const blob = new Blob([data.markdown], { type: 'text/markdown' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = data.filename || 'report.md';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (e) {
      console.error("Export failed", e);
    }
  };

  return (
    <main className="flex min-h-screen bg-background text-foreground font-sans selection:bg-primary selection:text-primary-foreground transition-colors duration-300">
      {/* Sidebar is handled in layout */}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col max-w-5xl mx-auto w-full relative">
        {/* Header */}
        <div className="p-4 border-b border-border bg-background/50 backdrop-blur-sm sticky top-0 z-10 flex justify-between items-center">
          <span className="text-sm font-semibold text-muted-foreground">Session #{sessionId || "..."}</span>
          <button
            onClick={handleExport}
            className="text-xs flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary hover:bg-muted transition-colors text-foreground"
          >
            <History size={14} />
            Export Report
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6" ref={scrollRef}>
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
                        <ReactMarkdown
                          remarkPlugins={[remarkMath]}
                          rehypePlugins={[rehypeKatex]}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>

                {msg.role === "assistant" && msg.tool && !showThinking && (
                  <div className="md:pl-11">
                    <WidgetRenderer toolData={msg.tool} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-border bg-background/80 backdrop-blur-md sticky bottom-0 z-10">

          {/* Tier Selector - Moved here for better UX */}
          <div className="absolute -top-12 left-1/2 -translate-x-1/2 flex bg-muted rounded-full p-1 border border-border shadow-sm transition-colors">
            <button
              type="button"
              onClick={() => setTier("efficient")}
              className={`px-4 py-1 text-xs font-medium rounded-full transition-all ${tier === "efficient" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                }`}
            >
              Efficient
            </button>
            <button
              type="button"
              onClick={() => setTier("deep")}
              className={`px-4 py-1 text-xs font-medium rounded-full transition-all ${tier === "deep" ? "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 shadow-sm" : "text-muted-foreground hover:text-foreground"
                }`}
            >
              Deep Think
            </button>
          </div>

          <form onSubmit={handleSubmit} className="relative max-w-3xl mx-auto flex gap-2 items-center">

            <button
              type="button"
              className="bg-muted hover:bg-secondary text-muted-foreground hover:text-foreground p-3 rounded-full transition-colors"
              title="Voice Input (Coming Soon)"
            >
              <Mic size={20} />
            </button>

            <div className="relative flex-1">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question (e.g., 'Calculate axial stress for a 10mm rod')"
                className="w-full bg-muted/50 border border-border text-foreground rounded-xl pl-4 pr-12 py-4 focus:outline-none focus:ring-2 focus:ring-blue-500/50 shadow-sm transition-all placeholder:text-muted-foreground"
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
          <div className="text-center text-[10px] text-gray-400 dark:text-gray-600 mt-3">
            AI can make mistakes. Design Engineer verification required.
          </div>
        </div>
      </div>

      {showOnboarding && <OnboardingModal onComplete={handleOnboardingComplete} />}
    </main>
  );
}
