import { useState } from 'react'
import CampaignForm from '../components/CampaignForm'
import ResultsPanel from '../components/ResultsPanel'
import { SkeletonBlock, ErrorBox } from '../components/ui'
import { analyzeCampaign } from '../api/api'

function LoadingSkeleton() {
  return (
    <div>
      <SkeletonBlock height={110} />
      <SkeletonBlock height={200} />
      <SkeletonBlock height={160} />
      <SkeletonBlock height={130} />
    </div>
  )
}

function Placeholder() {
  return (
    <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: 40, marginBottom: 16 }}>📊</div>
      <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
        Ready to analyze
      </div>
      <p style={{ fontSize: 13, lineHeight: 1.6, maxWidth: 280, margin: '0 auto 24px' }}>
        Fill in your campaign data on the left, then click <strong style={{ color: 'var(--text-primary)' }}>Analyze Campaign</strong> to see AI-powered insights.
      </p>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
        {['Comparison', 'Patterns', 'Insights', 'Recommendations'].map((step, i) => (
          <span key={step} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{
              padding: '3px 10px', borderRadius: 6, fontSize: 12,
              background: 'var(--surface)', border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
            }}>{step}</span>
            {i < 3 && <span style={{ color: 'var(--border-light)', fontSize: 12 }}>→</span>}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function AnalyzePage() {
  const [loading, setLoading] = useState(false)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)

  async function handleSubmit(payload) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await analyzeCampaign(payload)
      setResult(data)
    } catch (e) {
      setError(e.message || 'Unexpected error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 52px)' }}>

      {/* Left panel — form */}
      <div style={{
        width: 320, flexShrink: 0,
        borderRight: '1px solid var(--border)',
        overflowY: 'auto', padding: 20,
      }}>
        <div style={{ marginBottom: 16 }}>
          <h1 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>
            Analyze Campaign
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
            Analyze campaign performance, detect patterns, and get actionable recommendations.
          </p>
        </div>
        <CampaignForm onSubmit={handleSubmit} loading={loading} />
      </div>

      {/* Right panel — results */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          {error && <ErrorBox message={error} onDismiss={() => setError(null)} />}
          {loading && <LoadingSkeleton />}
          {!loading && !result && !error && <Placeholder />}
          {!loading && result && <ResultsPanel result={result} />}
        </div>
      </div>

    </div>
  )
}
