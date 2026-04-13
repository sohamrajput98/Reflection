// TODO: add Authorization header here when auth is implemented
// TODO: add campaign history filtering params when filter UI is added
// TODO: add export/report endpoint when export feature is built

const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let msg = `Server error (${res.status})`
    try {
      const body = await res.json()
      msg = body?.detail || body?.message || JSON.stringify(body) || msg
    } catch {
      try { msg = (await res.text()) || msg } catch { /* keep default */ }
    }
    throw new Error(msg)
  }
  return res.json()
}

export function analyzeCampaign(payload) {
  return request('/analyze-campaign', { method: 'POST', body: JSON.stringify(payload) })
}

// GET /insights?limit=N → InsightRecord[]
export function getInsights(limit = 30) {
  return request(`/insights?limit=${limit}`)
}

// GET /patterns?limit=N → PatternRecord[]
export function getPatterns(limit = 30) {
  return request(`/patterns?limit=${limit}`)
}

// GET /recommendations → RecommendationResponse
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
