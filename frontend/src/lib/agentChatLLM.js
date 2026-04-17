export const OPENROUTER_MODELS = [
  "qwen/qwen3.6-plus:free",
  "nvidia/nemotron-3-super-120b-a12b:free",
  "qwen/qwen3-235b-a22b:free",
  "qwen/qwen3-coder-480b-a35b:free",
  "stepfun/step-3.5-flash:free",
  "nvidia/nemotron-3-nano-30b-a3b:free",
  "minimax/minimax-m2.5:free",
  "arcee-ai/trinity-large-preview:free",
  "openai/gpt-oss-120b:free",
  "z-ai/glm-4.5-air:free",
  "google/gemma-3-27b-it:free",
  "nousresearch/hermes-3-llama-3.1-405b:free",
  "openrouter/free",
]

export const REFLECTION_AGENT_SYSTEM_PROMPT = `You are Marko AI, a Campaign Intelligence / Reflection Agent.
You help with campaign analysis, diagnosing performance shifts, extracting patterns, recalling related campaign memory, and turning results into practical next steps.
Stay concise, specific, and grounded in the current campaign context when available.
If campaign data is missing, ask focused questions about platform, objective, performance, patterns, insights, or recommendations.`

function buildContextBlock(context) {
  if (!context) return 'No campaign context available.'

  const parts = []
  if (context.agentTitle) parts.push(`Active agent: ${context.agentTitle}`)
  if (context.narrative) parts.push(`Narrative summary: ${context.narrative}`)
  if (context.keyLearnings?.length) parts.push(`Key learnings: ${context.keyLearnings.join(' | ')}`)
  if (context.recommendations?.length) parts.push(`Recommendations: ${context.recommendations.join(' | ')}`)
  if (context.patterns?.length) parts.push(`Patterns: ${context.patterns.join(' | ')}`)
  if (context.comparison?.length) parts.push(`Performance deltas: ${context.comparison.join(' | ')}`)
  return parts.join('\n') || 'No campaign context available.'
}

function localFallbackReply(message, context) {
  const prompt = message.toLowerCase()
  if (prompt.includes('biggest') || prompt.includes('issue') || prompt.includes('problem')) {
    return context?.recommendations?.[0]
      ? `Biggest issue in focus: ${context.recommendations[0]}`
      : 'I need an analyzed campaign to isolate the biggest issue clearly.'
  }
  if (prompt.includes('pattern')) {
    return context?.patterns?.length
      ? `Top pattern signals: ${context.patterns.slice(0, 3).join(', ')}.`
      : 'No strong pattern signals are available yet.'
  }
  if (prompt.includes('recommend')) {
    return context?.recommendations?.length
      ? `Recommended next move: ${context.recommendations[0]}`
      : 'No recommendation is available yet. Run an analysis first.'
  }
  if (prompt.includes('memory') || prompt.includes('similar')) {
    return context?.memory?.length
      ? `Closest recalled campaigns: ${context.memory.slice(0, 2).join(', ')}.`
      : 'No similar campaign memory is available yet.'
  }
  return context?.narrative || 'Share a campaign result or ask about analysis, patterns, insights, memory, or next actions.'
}

export async function sendAgentChatMessage(message, context) {
  const apiKey = import.meta.env.VITE_OPENROUTER_API_KEY
  const contextBlock = buildContextBlock(context)

  if (!apiKey) {
    return { reply: localFallbackReply(message, context), model: 'local-fallback' }
  }

  for (const model of OPENROUTER_MODELS) {
    try {
      const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model,
          messages: [
            { role: 'system', content: REFLECTION_AGENT_SYSTEM_PROMPT },
            { role: 'system', content: `Campaign context:\n${contextBlock}` },
            { role: 'user', content: message },
          ],
        }),
      })

      if (!response.ok) continue
      const data = await response.json()
      const reply = data?.choices?.[0]?.message?.content?.trim()
      if (reply) return { reply, model }
    } catch {
      continue
    }
  }

  return { reply: localFallbackReply(message, context), model: 'local-fallback' }
}
