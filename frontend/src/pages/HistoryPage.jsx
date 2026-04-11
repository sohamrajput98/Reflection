// TODO: add date range / platform filtering when filter UI is built
// TODO: add charts/graphs for trend visualization
// TODO: add natural language search over stored insights

import { useState, useEffect } from 'react'
import { Card, SectionTitle, Tag, ImpactBar, SkeletonBlock, EmptyState, ErrorBox } from '../components/ui'
import { getInsights, getPatterns, getRecommendations } from '../api/api'

const TABS = [
  { id: 'insights',        label: '🧠 Insights' },
  { id: 'patterns',        label: '🔍 Patterns' },
  { id: 'recommendations', label: '💡 Recommendations' },
]

function InsightRow({ record }) {
  const kindColor = { key_learning: 'blue', recommendation: 'green', anomaly: 'amber' }
  return (
    <div style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <span style={{ fontSize: 14, flexShrink: 0 }}>
          {record.kind === 'key_learning' ? '✦' : record.kind === 'anomaly' ? '⚠' : '→'}
        </span>
        <div style={{ flex: 1 }}>
          <p style={{ margin: '0 0 6px', fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>
            {record.content}
          </p>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            <Tag color={kindColor[record.kind] || 'default'}>{record.kind.replace('_', ' ')}</Tag>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{record.campaign_id}</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
              priority {record.priority.toFixed(2)}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function PatternRow({ record }) {
  return (
    <div style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5, flex: 1 }}>
          {record.summary}
        </p>
        <span style={{
          fontSize: 12, fontWeight: 600, flexShrink: 0, fontVariantNumeric: 'tabular-nums',
          color: record.impact_score >= 0 ? 'var(--green)' : 'var(--red)',
        }}>
          {record.impact_score > 0 ? '+' : ''}{record.impact_score.toFixed(1)}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <Tag>{record.category}</Tag>
        <Tag>{record.signal_key}</Tag>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
          {record.campaign_id}
        </span>
      </div>
      <ImpactBar score={record.impact_score} />
    </div>
  )
}

function RecsContent({ recs }) {
  if (!recs) return null
  return (
    <div>
      {recs.recommendations?.length > 0 ? (
        <div style={{ marginBottom: 20 }}>
          {recs.recommendations.map((r, i) => (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '10px 12px', marginBottom: 8,
              background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8,
            }}>
              <div style={{
                width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                background: 'var(--accent-muted)', border: '1px solid var(--accent-border)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700, color: 'var(--accent)',
              }}>{i + 1}</div>
              <span style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>{r}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message="No recommendations yet. Analyze a campaign first." />
      )}

      {recs.top_signals?.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
            Top Signals
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {recs.top_signals.map(s => <Tag key={s} color="blue">{s}</Tag>)}
          </div>
        </div>
      )}
    </div>
  )
}

export default function HistoryPage() {
  const [tab, setTab]         = useState('insights')
  const [insights, setInsights] = useState([])
  const [patterns, setPatterns] = useState([])
  const [recs, setRecs]         = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [i, p, r] = await Promise.allSettled([
        getInsights(30),
        getPatterns(30),
        getRecommendations(),
      ])
      if (i.status === 'fulfilled') setInsights(i.value)
      if (p.status === 'fulfilled') setPatterns(p.value)
      if (r.status === 'fulfilled') setRecs(r.value)
      // surface first error if all failed
      if (i.status === 'rejected' && p.status === 'rejected' && r.status === 'rejected') {
        setError(i.reason?.message || 'Failed to load data')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const counts = { insights: insights.length, patterns: patterns.length, recommendations: recs?.recommendations?.length ?? 0 }

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
      {/* Header */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>
            History &amp; Memory
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>
            Stored insights, patterns, and signals from all analyzed campaigns
          </p>
        </div>
        <button className="btn-ghost" onClick={load} disabled={loading}>
          {loading ? '...' : '↻ Refresh'}
        </button>
      </div>

      {error && <ErrorBox message={error} onDismiss={() => setError(null)} />}

      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: 4, background: 'var(--surface)',
        border: '1px solid var(--border)', borderRadius: 10, padding: 4, marginBottom: 16,
      }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              flex: 1, padding: '7px 12px', borderRadius: 8,
              fontSize: 13, fontWeight: 500, fontFamily: 'inherit',
              cursor: 'pointer', border: 'none', transition: 'all 0.15s',
              background: tab === t.id ? 'var(--card)' : 'transparent',
              color: tab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}
          >
            {t.label}
            {!loading && counts[t.id] > 0 && (
              <span style={{
                fontSize: 11, padding: '1px 6px', borderRadius: 6,
                background: tab === t.id ? 'var(--accent-muted)' : 'var(--border)',
                color: tab === t.id ? 'var(--accent)' : 'var(--text-muted)',
              }}>{counts[t.id]}</span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <Card>
        {loading ? (
          <>
            <SkeletonBlock height={60} />
            <SkeletonBlock height={60} />
            <SkeletonBlock height={60} />
            <SkeletonBlock height={60} />
          </>
        ) : (
          <>
            {tab === 'insights' && (
              insights.length === 0
                ? <EmptyState message="No insights yet. Analyze a campaign to generate insights." />
                : insights.map(r => <InsightRow key={r.id} record={r} />)
            )}
            {tab === 'patterns' && (
              patterns.length === 0
                ? <EmptyState message="No patterns yet. Analyze a campaign to detect patterns." />
                : patterns.map(r => <PatternRow key={r.id} record={r} />)
            )}
            {tab === 'recommendations' && <RecsContent recs={recs} />}
          </>
        )}
      </Card>
    </div>
  )
}
