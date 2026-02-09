import { convertToModelMessages, streamText, type UIMessage } from "ai"
import { createGroq } from "@ai-sdk/groq"

export const maxDuration = 60

const groq = createGroq({
  apiKey: process.env.GROQ_API_KEY,
})

export async function POST(req: Request) {
  const body = await req.json()

  // Messages come from AI SDK's DefaultChatTransport
  const messages: UIMessage[] = body.messages ?? []
  const model: string = body.model ?? "llama-3.3-70b-versatile"

  console.log("[v0] API /chat called. Model:", model, "Messages:", messages.length)

  const modelMessages = await convertToModelMessages(messages)

  console.log("[v0] Converted to model messages:", modelMessages.length)

  const result = streamText({
    model: groq(model),
    system:
      "You are a professional workspace assistant. You help users with coding, analysis, writing, and general knowledge tasks. You provide clear, well-structured responses with markdown formatting when appropriate.",
    messages: modelMessages,
  })

  return result.toUIMessageStreamResponse()
}
