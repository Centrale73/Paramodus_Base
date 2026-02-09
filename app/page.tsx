"use client"

import { useState, useRef, useCallback, useEffect, useMemo } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import type { UIMessage } from "ai"
import { ChatMessage } from "@/components/chat-message"
import { ChatSidebar, type ChatSession } from "@/components/chat-sidebar"
import { SettingsPanel } from "@/components/settings-panel"
import { CheckpointSidebar } from "@/components/checkpoint-sidebar"
import { ChatInput } from "@/components/chat-input"
import { cn } from "@/lib/utils"
import { useTypingSpeed } from "@/hooks/use-typing-speed"
import { Plus } from "lucide-react"

// Stable transport instance -- created once outside the component
const chatTransport = new DefaultChatTransport({
  api: "/api/chat",
})

export default function Home() {
  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarView, setSidebarView] = useState<"chats" | "settings">("chats")

  // Session management (client-side only for this frontend)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState(() =>
    crypto.randomUUID()
  )

  // Model settings
  const [currentModel, setCurrentModel] = useState("llama-3.3-70b-versatile")
  const modelRef = useRef(currentModel)
  useEffect(() => { modelRef.current = currentModel }, [currentModel])

  // GenUI: Track the mood that was active when each user message was sent
  const [messageMoods, setMessageMoods] = useState<Record<string, "slow" | "neutral" | "fast">>({})

  // Checkpoint state
  const [checkpointedIds, setCheckpointedIds] = useState<Set<string>>(
    new Set()
  )
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null)

  // GenUI: Typing speed tracking
  const { mood: typingMood, handleKeystroke, reset: resetTypingSpeed } = useTypingSpeed()

  // Chat ref for scrolling
  const chatContainerRef = useRef<HTMLDivElement>(null)

  // Input state
  const [input, setInput] = useState("")

  // AI SDK useChat -- stable transport, dynamic body via sendMessage
  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport: chatTransport,
  })

  const isLoading = status === "streaming" || status === "submitted"
  console.log("[v0] Chat status:", status, "Messages count:", messages.length)

  // Tag new user messages with the mood that was active when they were sent
  useEffect(() => {
    const userMessages = messages.filter((m) => m.role === "user")
    if (userMessages.length === 0) return
    const lastUser = userMessages[userMessages.length - 1]
    if (!messageMoods[lastUser.id]) {
      setMessageMoods((prev) => ({
        ...prev,
        [lastUser.id]: pendingMoodRef.current,
      }))
    }
  }, [messages, messageMoods])

  // Auto-scroll to bottom
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight
    }
  }, [messages])

  // Track scroll to highlight active message in checkpoint sidebar
  const handleScroll = useCallback(() => {
    if (!chatContainerRef.current) return
    const container = chatContainerRef.current
    const containerRect = container.getBoundingClientRect()
    const centerY = containerRect.top + containerRect.height / 2

    const messageElements = container.querySelectorAll("[data-message-id]")
    let closestId: string | null = null
    let closestDist = Infinity

    messageElements.forEach((el) => {
      const rect = el.getBoundingClientRect()
      const dist = Math.abs(rect.top + rect.height / 2 - centerY)
      if (dist < closestDist) {
        closestDist = dist
        closestId = el.getAttribute("data-message-id")
      }
    })

    setActiveMessageId(closestId)
  }, [])

  // Session management functions
  const handleNewChat = useCallback(() => {
    // Save current session if it has messages
    if (messages.length > 0) {
      const firstUserMsg = messages.find((m) => m.role === "user")
      const title = firstUserMsg
        ? getMessageText(firstUserMsg).substring(0, 30) +
          (getMessageText(firstUserMsg).length > 30 ? "..." : "")
        : "New Chat"

      setSessions((prev) => {
        const exists = prev.find((s) => s.id === currentSessionId)
        if (exists) return prev
        return [
          {
            id: currentSessionId,
            title,
            timestamp: new Date().toISOString(),
          },
          ...prev,
        ]
      })
    }

    const newId = crypto.randomUUID()
    setCurrentSessionId(newId)
    setMessages([])
    setCheckpointedIds(new Set())
    setMessageMoods({})
    setInput("")
    resetTypingSpeed()
  }, [messages, currentSessionId, setMessages, resetTypingSpeed])

  // Ref to snapshot the mood right before sending
  const pendingMoodRef = useRef<"slow" | "neutral" | "fast">("neutral")

  const handleSend = useCallback(() => {
    if (!input.trim() || isLoading) return
    pendingMoodRef.current = typingMood
    sendMessage({ text: input }, { body: { model: modelRef.current } })
    setInput("")
    resetTypingSpeed()
  }, [input, isLoading, sendMessage, resetTypingSpeed, typingMood])

  const handleSwitchView = useCallback(
    (view: "chats" | "settings") => {
      if (sidebarOpen && sidebarView === view) {
        setSidebarOpen(false)
      } else {
        setSidebarView(view)
        setSidebarOpen(true)
      }
    },
    [sidebarOpen, sidebarView]
  )

  const handleToggleCheckpoint = useCallback((id: string) => {
    setCheckpointedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const handleNavigateToMessage = useCallback((id: string) => {
    const el = document.querySelector(`[data-message-id="${id}"]`)
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" })
    }
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Background gradient -- shifts hue with typing mood */}
      <div className="fixed inset-0 pointer-events-none transition-all duration-700 ease-out">
        <div
          className={`absolute top-0 left-[20%] w-[500px] h-[500px] rounded-full blur-[120px] transition-colors duration-700 ease-out ${
            typingMood === "slow"
              ? "bg-indigo-500/15"
              : typingMood === "fast"
                ? "bg-pink-500/15"
                : "bg-primary/10"
          }`}
        />
        <div
          className={`absolute bottom-0 right-[20%] w-[400px] h-[400px] rounded-full blur-[100px] transition-colors duration-700 ease-out ${
            typingMood === "slow"
              ? "bg-indigo-400/8"
              : typingMood === "fast"
                ? "bg-pink-400/8"
                : "bg-primary/5"
          }`}
        />
      </div>

      {/* Sidebar */}
      <ChatSidebar
        isOpen={sidebarOpen}
        activeView={sidebarView}
        sessions={sessions}
        currentSessionId={currentSessionId}
        onClose={() => setSidebarOpen(false)}
        onSwitchView={handleSwitchView}
        onNewChat={handleNewChat}
        onSwitchSession={(id) => {
          setCurrentSessionId(id)
          setSidebarOpen(false)
        }}
        onDeleteSession={(id) => {
          setSessions((prev) => prev.filter((s) => s.id !== id))
        }}
        settingsContent={
          <SettingsPanel
            currentModel={currentModel}
            onModelChange={setCurrentModel}
          />
        }
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col h-screen relative z-10 pr-5">
        {/* Header */}
        <header className={cn(
          "flex items-center justify-between px-6 py-4 border-b bg-card/30 backdrop-blur-xl transition-colors duration-700 ease-out",
          typingMood === "slow"
            ? "border-indigo-500/30"
            : typingMood === "fast"
              ? "border-pink-500/30"
              : "border-border/50"
        )}>
          <h1 className="text-base font-bold tracking-tight text-foreground">
            Agentic Workspace
          </h1>
          <div className="flex items-center gap-3">
            <button
              onClick={handleNewChat}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold text-primary-foreground hover:-translate-y-px hover:shadow-lg active:translate-y-0 transition-all duration-500 ease-out",
                typingMood === "slow"
                  ? "bg-indigo-500 hover:shadow-indigo-500/40"
                  : typingMood === "fast"
                    ? "bg-pink-500 hover:shadow-pink-500/40"
                    : "bg-primary hover:shadow-primary/40"
              )}
            >
              <Plus className="h-4 w-4" />
              New Chat
            </button>
            <span className="text-xs text-muted-foreground hidden sm:inline">
              {
                (
                  [
                    { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B" },
                    { id: "llama-3.1-8b-instant", label: "Llama 3.1 8B" },
                    { id: "mixtral-8x7b-32768", label: "Mixtral 8x7B" },
                    { id: "gemma2-9b-it", label: "Gemma 2 9B" },
                  ] as const
                ).find((m) => m.id === currentModel)?.label
              }
            </span>
          </div>
        </header>

        {/* Chat area */}
        <div
          ref={chatContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-4"
        >
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            messages.map((message, i) => {
              const isUser = message.role === "user"
              const isLastAssistant =
                message.role === "assistant" &&
                i === messages.length - 1 &&
                isLoading
              return (
                <div
                  key={message.id}
                  data-message-id={message.id}
                  className={cn(
                    "flex gap-2",
                    isUser ? "justify-end" : "justify-start"
                  )}
                >
                  <ChatMessage
                    message={message}
                    isStreaming={isLastAssistant}
                    mood={isUser ? messageMoods[message.id] || "neutral" : "neutral"}
                  />
                  {message.role === "assistant" && (
                    <button
                      onClick={() => handleToggleCheckpoint(message.id)}
                      className={cn(
                        "shrink-0 mt-3 w-6 h-6 rounded flex items-center justify-center text-xs transition-all duration-200 border",
                        checkpointedIds.has(message.id)
                          ? "bg-emerald-500/20 border-emerald-500 text-emerald-500 opacity-100"
                          : "bg-muted/30 border-border/50 text-muted-foreground opacity-0 hover:opacity-100"
                      )}
                      title="Checkpoint this answer"
                      style={{
                        opacity: checkpointedIds.has(message.id)
                          ? 1
                          : undefined,
                      }}
                    >
                      {"✓"}
                    </button>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* Input */}
        <ChatInput
          input={input}
          onInputChange={setInput}
          onSend={handleSend}
          onStop={stop}
          isLoading={isLoading}
          typingMood={typingMood}
          onKeystroke={handleKeystroke}
        />
      </div>

      {/* Checkpoint sidebar (right) */}
      <CheckpointSidebar
        messages={messages}
        checkpointedIds={checkpointedIds}
        onToggleCheckpoint={handleToggleCheckpoint}
        onNavigate={handleNavigateToMessage}
        activeMessageId={activeMessageId}
      />
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center max-w-md">
        <h2 className="text-xl font-semibold text-foreground mb-2 text-balance">
          Agentic Workspace
        </h2>
        <p className="text-sm text-muted-foreground leading-relaxed text-pretty">
          Your professional AI assistant powered by Groq. Ask anything about
          coding, analysis, writing, or general knowledge.
        </p>
      </div>
    </div>
  )
}

function getMessageText(message: UIMessage): string {
  if (!message.parts || !Array.isArray(message.parts)) return ""
  return message.parts
    .filter((p): p is { type: "text"; text: string } => p.type === "text")
    .map((p) => p.text)
    .join("")
}
