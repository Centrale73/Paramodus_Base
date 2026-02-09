import { convertToModelMessages, streamText, type UIMessage } from "ai"
import { createGroq } from "@ai-sdk/groq"

export const maxDuration = 60

const groq = createGroq({
  apiKey: process.env.GROQ_API_KEY,
})

export async function POST(req: Request) {
  const {
    messages,
    model = "llama-3.3-70b-versatile",
  }: {
    messages: UIMessage[]
    model?: string
  } = await req.json()

  const result = streamText({
    model: groq(model),
    system:
      "You are a professional workspace assistant. You help users with coding, analysis, writing, and general knowledge tasks. You provide clear, well-structured responses with markdown formatting when appropriate.",
    messages: await convertToModelMessages(messages),
  })

  return result.toUIMessageStreamResponse()
}
