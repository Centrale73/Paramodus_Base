"use client"

import { cn } from "@/lib/utils"
import type { UIMessage } from "ai"
import type { TypingMood } from "@/hooks/use-typing-speed"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

function getMessageText(message: UIMessage): string {
  if (!message.parts || !Array.isArray(message.parts)) return ""
  return message.parts
    .filter((p): p is { type: "text"; text: string } => p.type === "text")
    .map((p) => p.text)
    .join("")
}

const userBubbleMoodMap: Record<TypingMood, string> = {
  slow: "bg-gradient-to-br from-indigo-500 to-indigo-400 shadow-indigo-500/25",
  neutral: "bg-primary shadow-primary/25",
  fast: "bg-gradient-to-br from-pink-500 to-rose-400 shadow-pink-500/25",
}

interface ChatMessageProps {
  message: UIMessage
  isStreaming?: boolean
  mood?: TypingMood
}

export function ChatMessage({ message, isStreaming, mood = "neutral" }: ChatMessageProps) {
  const text = getMessageText(message)
  const isUser = message.role === "user"

  return (
    <div
      className={cn(
        "flex flex-col max-w-[80%] animate-message-in",
        isUser ? "items-end" : "items-start"
      )}
    >
      <div
        className={cn(
          "px-5 py-3.5 rounded-2xl text-[0.95rem] leading-relaxed break-words",
          isUser
            ? cn("text-primary-foreground rounded-br-sm shadow-lg", userBubbleMoodMap[mood])
            : "bg-card/50 text-foreground rounded-bl-sm border border-border/50 backdrop-blur-xl"
        )}
      >
        {isUser ? (
          <span>{text}</span>
        ) : text ? (
          <div className="prose-chat">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
          </div>
        ) : isStreaming ? (
          <span className="text-muted-foreground">
            {"Thinking"}
            <span className="loading-dots" />
          </span>
        ) : null}
      </div>
    </div>
  )
}
