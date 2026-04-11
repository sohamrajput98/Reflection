// Maps exactly to AnalyzeCampaignResponse from the backend schema
import { useState } from 'react'
import { Card, SectionTitle, Tag, DeltaChip, ScoreBar, ImpactBar, EmptyState } from './ui'

// ── Comparison ────────────────────────────────────────────────────────────────
function ComparisonSection({ report }) {
  const { deltas, performance_score, summary, actual_rates } = report
  return (
    <Card>
      <SectionTitle>📈 Performance Comparison</SectionTitle>
      <ScoreBar score={performance_score} />

      {/* 4 delta chips */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 8, marginTop: 16,
        background: 'var(--surface)', borderRadius: 10, border: '1px solid var(--border)',
        padding: '4px 0',
      }}>
        <DeltaChip {...deltas.ctr_diff}  label="CTR" />
        <DeltaChip {...deltas.cvr_diff}  label="CVR" />
        <DeltaChip {...deltas.cpa_diff}  label="CPA" />
        <DeltaChip {...deltas.roas_diff} label="ROAS" />
      </div>

      {/* Actual rates row */}
      {actual_rates && (
        <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
          {[
            ['CTR', actual_rates.ctr != null ? `${(actual_rates.ctr * 100).toFixed(2)}%` : '—'],
            ['CVR', actual_rates.cvr != null ? `${(actual_rates.cvr * 100).toFixed(2)}%` : '—'],
            ['CPA', actual_rates.cpa != null ? `$${actual_rates.cpa.toFixed(2)}` : '—'],
            ['ROAS', actual_rates.roas != null ? `${actual_rates.roas.toFixed(2)}x` : '—'],
          ].map(([k, v]) => (
            <div key={k} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              <span style={{ color: 'var(--text-muted)' }}>{k}: </span>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{v}</span>
            </div>
          ))}
        </div>
      )}

      {/* Summary bullets */}
      {summary?.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {summary.map((s, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
              <span style={{ color: 'var(--accent)', flexShrink: 0 }}>›</span>
              {s}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

// ── Patterns ──────────────────────────────────────────────────────────────────
function FindingRow({ finding }) {
  return (
    <div style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5, flex: 1 }}>
          {finding.description}
        </span>
        <span style={{
          fontSize: 12, fontWeight: 600, flexShrink: 0, fontVariantNumeric: 'tabular-nums',
          color: finding.impact_score >= 0 ? 'var(--green)' : 'var(--red)',
        }}>
          {finding.impact_score > 0 ? '+' : ''}{finding.impact_score.toFixed(1)}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <Tag>{finding.signal_key}</Tag>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{finding.evidence_count} campaigns</span>
      </div>
      <ImpactBar score={finding.impact_score} />
    </div>
  )
}

function PatternsSection({ pattern_report }) {
  const [open, setOpen] = useState('winning_audiences')

  const groups = [
    { key: 'winning_audiences',        label: '👥 Winning Audiences',         color: 'green' },
    { key: 'high_performing_creatives',label: '🎨 High-Performing Creatives',  color: 'blue' },
    { key: 'budget_inefficiencies',    label: '⚠ Budget Inefficiencies',       color: 'amber' },
    { key: 'platform_trends',          label: '📡 Platform Trends',            color: 'blue' },
    { key: 'clusters',                 label: '🔵 Clusters',                   color: 'default' },
  ].filter(g => pattern_report[g.key]?.length > 0)

  if (!groups.length) return (
    <Card>
      <SectionTitle>🔍 Patterns</SectionTitle>
      <EmptyState message="No patterns detected for this campaign yet." />
    </Card>
  )

  return (
    <Card>
      <SectionTitle>🔍 Patterns</SectionTitle>

      {/* Auto tags */}
      {pattern_report.auto_tags?.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          {pattern_report.auto_tags.map(t => <Tag key={t}>{t}</Tag>)}
        </div>
      )}

      {/* Tab switcher */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 12 }}>
        {groups.map(g => (
          <button
            key={g.key}
            onClick={() => setOpen(g.key)}
            style={{
              padding: '5px 10px', borderRadius: 8, fontSize: 12, fontFamily: 'inherit',
              cursor: 'pointer', border: '1px solid',
              background: open === g.key ? 'var(--accent-muted)' : 'transparent',
              borderColor: open === g.key ? 'var(--accent-border)' : 'var(--border)',
              color: open === g.key ? 'var(--accent)' : 'var(--text-secondary)',
              transition: 'all 0.15s',
            }}
          >
            {g.label}
            <span style={{ marginLeft: 5, opacity: 0.6 }}>({pattern_report[g.key].length})</span>
          </button>
        ))}
      </div>

      {/* Active group findings */}
      <div>
        {(pattern_report[open] || []).map(f => (
          <FindingRow key={f.finding_id} finding={f} />
        ))}
      </div>
    </Card>
  )
}

// ── Insights ──────────────────────────────────────────────────────────────────
function InsightsSection({ insights }) {
  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <SectionTitle>🧠 Insights</SectionTitle>
        <Tag color={insights.source === 'openai' ? 'blue' : 'default'}>
          {insights.source === 'openai' ? 'GPT-powered' : 'Deterministic'}
        </Tag>
      </div>

      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
        {insights.narrative_summary}
      </p>

      {insights.key_learnings?.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
            Key Learnings
          </div>
          {insights.key_learnings.map((l, i) => (
            <div key={i} style={{
              display: 'flex', gap: 8, padding: '8px 10px', marginBottom: 6,
              background: 'var(--accent-muted)', border: '1px solid var(--accent-border)', borderRadius: 8,
            }}>
              <span style={{ color: 'var(--accent)', flexShrink: 0 }}>✦</span>
              <span style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>{l}</span>
            </div>
          ))}
        </div>
      )}

      {insights.anomalies?.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
            Anomalies
          </div>
          {insights.anomalies.map((a, i) => (
            <div key={i} style={{
              display: 'flex', gap: 8, padding: '8px 10px', marginBottom: 6,
              background: 'var(--amber-muted)', border: '1px solid var(--amber-border)', borderRadius: 8,
            }}>
              <span style={{ color: 'var(--amber)', flexShrink: 0 }}>⚠</span>
              <span style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>{a}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

// ── Recommendations ───────────────────────────────────────────────────────────
function RecommendationsSection({ insights }) {
  if (!insights.recommendations?.length) return null
  return (
    <Card>
      <SectionTitle>💡 Recommendations</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {insights.recommendations.map((r, i) => (
          <div key={i} style={{
            display: 'flex', gap: 10, padding: '10px 12px',
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
    </Card>
  )
}

// ── Similar campaigns ─────────────────────────────────────────────────────────
function SimilarSection({ similar_campaigns }) {
  if (!similar_campaigns?.length) return null
  return (
    <Card>
      <SectionTitle>🔗 Similar Campaigns</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {similar_campaigns.map((c, i) => (
          <div key={i} style={{
            display: 'flex', gap: 10, padding: '10px 12px',
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8,
          }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)', flexShrink: 0, minWidth: 36 }}>
              {Math.round(c.score * 100)}%
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                {c.campaign_id || c.document_id}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                {c.summary}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function ResultsPanel({ result }) {
  if (!result) return null
  const { comparison_report, pattern_report, insights, similar_campaigns } = result
  return (
    <div className="fade-up" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <ComparisonSection report={comparison_report} />
      <InsightsSection insights={insights} />
      <PatternsSection pattern_report={pattern_report} />
      <RecommendationsSection insights={insights} />
      <SimilarSection similar_campaigns={similar_campaigns} />
    </div>
  )
}
