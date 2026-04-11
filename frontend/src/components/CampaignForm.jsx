import { useState } from 'react'
import { Spinner } from './ui'

const PLATFORMS = ['Meta', 'Google', 'TikTok', 'LinkedIn', 'Snapchat', 'Twitter/X', 'YouTube']
const OBJECTIVES = ['Lead Generation', 'Conversions', 'Brand Awareness', 'Traffic', 'App Installs', 'Video Views', 'Engagement']

// Realistic sample data matching the exact CampaignPerformanceInput schema
const SAMPLE_DATA = {
  campaign_id: 'cmp_meta_genz_q2',
  platform: 'Meta',
  objective: 'Lead Generation',
  expected_metrics: { impressions: 100000, clicks: 2500, conversions: 150, spend: 2000, revenue: 7500 },
  actual_metrics:   { impressions: 134000, clicks: 4200, conversions: 210, spend: 2150, revenue: 10500 },
  audiences: [{ name: 'Gen Z Students', attributes: { age_range: '18-24', segment: 'students', city_tier: 'Tier-1' } }],
  creatives: [{ id: 'crt_001', type: 'video', headline: 'Learn faster, earn sooner', primary_text: 'Short-form video showing student success story.' }],
}

const inputStyle = {
  width: '100%', background: 'var(--surface)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '7px 10px', color: 'var(--text-primary)',
  fontSize: 13, fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box',
}
const selectStyle = { ...inputStyle, cursor: 'pointer', appearance: 'none' }

function Field({ label, hint, children }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label className="label">{label}</label>
      {hint && <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 5px' }}>{hint}</p>}
      {children}
    </div>
  )
}

function MetricsGrid({ label, hint, value, onChange }) {
  const fields = [
    { key: 'impressions', label: 'Impressions', placeholder: '100000' },
    { key: 'clicks',      label: 'Clicks',      placeholder: '2500' },
    { key: 'conversions', label: 'Conversions', placeholder: '150' },
    { key: 'spend',       label: 'Spend ($)',   placeholder: '500' },
    { key: 'revenue',     label: 'Revenue ($) — optional', placeholder: '1200', optional: true },
  ]
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>{label}</div>
      {hint && <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>{hint}</p>}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {fields.map(f => (
          <div key={f.key} style={f.key === 'revenue' ? { gridColumn: '1 / -1' } : {}}>
            <label className="label">{f.label}</label>
            <input
              type="number" min="0" step={f.key === 'spend' || f.key === 'revenue' ? '0.01' : '1'}
              placeholder={f.placeholder}
              value={value[f.key] ?? ''}
              onChange={e => onChange({ ...value, [f.key]: e.target.value === '' ? '' : Number(e.target.value) })}
              style={inputStyle}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

const emptyMetrics = () => ({ impressions: '', clicks: '', conversions: '', spend: '', revenue: '' })

export default function CampaignForm({ onSubmit, loading }) {
  const [campaignId, setCampaignId] = useState('')
  const [platform, setPlatform]     = useState('')
  const [objective, setObjective]   = useState('')
  const [expected, setExpected]     = useState(emptyMetrics())
  const [actual, setActual]         = useState(emptyMetrics())

  function fillSample() {
    setCampaignId(SAMPLE_DATA.campaign_id)
    setPlatform(SAMPLE_DATA.platform)
    setObjective(SAMPLE_DATA.objective)
    setExpected(SAMPLE_DATA.expected_metrics)
    setActual(SAMPLE_DATA.actual_metrics)
  }

  function handleSubmit() {
    const cleanMetrics = m => ({
      impressions: Number(m.impressions) || 0,
      clicks:      Number(m.clicks) || 0,
      conversions: Number(m.conversions) || 0,
      spend:       Number(m.spend) || 0,
      ...(m.revenue !== '' && m.revenue != null ? { revenue: Number(m.revenue) } : {}),
    })

    onSubmit({
      campaign_id:      campaignId.trim(),
      platform,
      objective,
      expected_metrics: cleanMetrics(expected),
      actual_metrics:   cleanMetrics(actual),
      audiences: SAMPLE_DATA.audiences,   // kept simple — not exposed in form for now
      creatives: SAMPLE_DATA.creatives,   // kept simple — not exposed in form for now
      timestamp: new Date().toISOString(),
    })
  }

  const isValid = campaignId.trim() && platform && objective

  return (
    <div>
      {/* Fill sample button */}
      <button
        className="btn-ghost"
        onClick={fillSample}
        style={{ width: '100%', justifyContent: 'center', marginBottom: 16 }}
      >
        ✦ Fill Sample Data
      </button>

      <div style={{ height: 1, background: 'var(--border)', marginBottom: 16 }} />

      {/* Campaign identity */}
      <Field label="Campaign ID *">
        <input
          value={campaignId}
          onChange={e => setCampaignId(e.target.value)}
          placeholder="e.g. cmp_meta_q2_launch"
          style={inputStyle}
        />
      </Field>

      <Field label="Platform *">
        <div style={{ position: 'relative' }}>
          <select value={platform} onChange={e => setPlatform(e.target.value)} style={selectStyle}>
            <option value="">Select platform</option>
            {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--text-muted)', fontSize: 10 }}>▼</span>
        </div>
      </Field>

      <Field label="Objective *">
        <div style={{ position: 'relative' }}>
          <select value={objective} onChange={e => setObjective(e.target.value)} style={selectStyle}>
            <option value="">Select objective</option>
            {OBJECTIVES.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
          <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--text-muted)', fontSize: 10 }}>▼</span>
        </div>
      </Field>

      <div style={{ height: 1, background: 'var(--border)', margin: '16px 0' }} />

      <MetricsGrid
        label="Expected Metrics"
        hint="Planned values before campaign launch"
        value={expected}
        onChange={setExpected}
      />

      <MetricsGrid
        label="Actual Metrics"
        hint="Real performance after campaign ran"
        value={actual}
        onChange={setActual}
      />

      <button
        className="btn-primary"
        onClick={handleSubmit}
        disabled={!isValid || loading}
        style={{ marginTop: 4 }}
      >
        {loading ? <><Spinner size={14} /> Analyzing...</> : '⚡ Analyze Campaign'}
      </button>
    </div>
  )
}
