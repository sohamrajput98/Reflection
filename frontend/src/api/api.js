const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const API_AUTH_KEY = import.meta.env.VITE_API_AUTH_KEY

async function request(path, options = {}, debug = false) {
  const headers = {
    'Content-Type': 'application/json',
    ...(API_AUTH_KEY ? { 'X-API-Key': API_AUTH_KEY } : {}),
    ...(options.headers || {}),
  }

  const startedAt = performance.now()
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  })
  const latency_ms = Math.round(performance.now() - startedAt)
  if (!res.ok) {
    let msg = `Server error (${res.status})`
    let rawBody = null
    try {
      const body = await res.json()
      rawBody = body
      msg = body?.detail || body?.message || JSON.stringify(body) || msg
    } catch {
      try {
        rawBody = await res.text()
        msg = rawBody || msg
      } catch { /* keep default */ }
    }
    if (debug) {
      return {
        ok: false,
        status: res.status,
        latency_ms,
        error: msg,
        body: rawBody,
      }
    }
    throw new Error(msg)
  }
  const body = await res.json()
  if (debug) {
    return {
      ok: true,
      status: res.status,
      latency_ms,
      body,
    }
  }
  return body
}

export function analyzeCampaign(payload, options = {}) {
  return request('/analyze-campaign', { method: 'POST', body: JSON.stringify(payload) }, options.debug === true)
}

export function sendAgentChat(message, context = {}) {
  return request('/agent-chat', {
    method: 'POST',
    body: JSON.stringify({ message, context }),
  })
}

export function getInsights(limit = 30) {
  return request(`/insights?limit=${limit}`)
}

export function getPatterns(limit = 30) {
  return request(`/patterns?limit=${limit}`)
}

export function getRecommendations(platform, objective) {
  const params = new URLSearchParams()
  if (platform) params.set('platform', platform)
  if (objective) params.set('objective', objective)
  const qs = params.toString()
  return request(`/recommendations${qs ? '?' + qs : ''}`)
}

export function getHealth() {
  return request('/health')
}

export function markRecommendationShown(payload, options = {}) {
  return request('/shown', { method: 'POST', body: JSON.stringify(payload) }, options.debug === true)
}

export function submitRecommendationFeedback(payload, options = {}) {
  return request('/feedback', { method: 'POST', body: JSON.stringify(payload) }, options.debug === true)
}

export function ingestAgentOutputs(payload, options = {}) {
  return request('/debug/agent-outputs/ingest', { method: 'POST', body: JSON.stringify(payload) }, options.debug === true)
}

export function getRecentAgentOutputs(limit = 20, options = {}) {
  return request(`/debug/agent-outputs?limit=${limit}`, {}, options.debug === true)
}

export function runAgentOutputReflection(payload, options = {}) {
  return request('/debug/agent-outputs/run-reflection', { method: 'POST', body: JSON.stringify(payload) }, options.debug === true)
}
