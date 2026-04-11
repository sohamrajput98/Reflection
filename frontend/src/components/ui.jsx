// Shared UI primitives — all styles via CSS vars defined in index.css

export function Card({ children, style = {} }) {
  return (
    <div className="card" style={style}>
      {children}
    </div>
  )
}

export function SectionTitle({ icon: Icon, children, count }) {
  return (
    <div className="section-title">
      {Icon && <Icon size={13} color="var(--accent)" />}
      <span>{children}</span>
      {count != null && (
        <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontWeight: 400 }}>
          {count}
        </span>
      )}
    </div>
  )
}

export function Tag({ children, color = 'default' }) {
  const colors = {
    default: { background: 'var(--surface)', color: 'var(--text-secondary)', border: '1px solid var(--border)' },
    green:   { background: 'var(--green-muted)', color: 'var(--green)', border: '1px solid var(--green-border)' },
    red:     { background: 'var(--red-muted)', color: 'var(--red)', border: '1px solid var(--red-border)' },
    amber:   { background: 'var(--amber-muted)', color: 'var(--amber)', border: '1px solid var(--amber-border)' },
    blue:    { background: 'var(--accent-muted)', color: 'var(--accent)', border: '1px solid var(--accent-border)' },
  }
  return (
    <span className="tag" style={colors[color] || colors.default}>
      {children}
    </span>
  )
}

export function DeltaChip({ pct_diff, favorable, label }) {
  const na = pct_diff == null
  const positive = !na && favorable
  return (
    <div style={{ textAlign: 'center', padding: '8px 4px' }}>
      <div style={{
        fontSize: 15,
        fontWeight: 600,
        fontVariantNumeric: 'tabular-nums',
        color: na ? 'var(--text-muted)' : positive ? 'var(--green)' : 'var(--red)',
      }}>
        {na ? '—' : `${positive ? '+' : ''}${pct_diff.toFixed(1)}%`}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
    </div>
  )
}

export function ScoreBar({ score }) {
  const clamped = Math.min(Math.max(score, -500), 500)
  const pct = ((clamped + 500) / 1000) * 100
  const color = score >= 100 ? 'var(--green)' : score >= 0 ? 'var(--accent)' : 'var(--red)'
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Performance Score</span>
        <span style={{ fontSize: 13, fontWeight: 600, color, fontVariantNumeric: 'tabular-nums' }}>
          {score > 0 ? '+' : ''}{Math.round(score)}
        </span>
      </div>
      <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  )
}

export function ImpactBar({ score }) {
  const abs = Math.min(Math.abs(score), 100)
  const color = score >= 0 ? 'var(--green)' : 'var(--red)'
  return (
    <div style={{ height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', marginTop: 6 }}>
      <div style={{ height: '100%', width: `${abs}%`, background: color, borderRadius: 2 }} />
    </div>
  )
}

export function Spinner({ size = 16 }) {
  return (
    <div
      className="animate-spin"
      style={{
        width: size, height: size,
        border: `2px solid rgba(255,255,255,0.15)`,
        borderTopColor: '#fff',
        borderRadius: '50%',
        display: 'inline-block',
      }}
    />
  )
}

export function SkeletonBlock({ height = 80 }) {
  return <div className="shimmer-box" style={{ height, marginBottom: 12 }} />
}

export function EmptyState({ icon: Icon, message }) {
  return (
    <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-muted)' }}>
      {Icon && <Icon size={28} style={{ opacity: 0.3, margin: '0 auto 10px', display: 'block' }} />}
      <p style={{ fontSize: 13, margin: 0 }}>{message}</p>
    </div>
  )
}

export function ErrorBox({ message, onDismiss }) {
  return (
    <div style={{
      background: 'var(--red-muted)',
      border: '1px solid var(--red-border)',
      borderRadius: 10,
      padding: '12px 14px',
      display: 'flex',
      gap: 10,
      alignItems: 'flex-start',
      marginBottom: 16,
    }}>
      <span style={{ color: 'var(--red)', fontSize: 16, lineHeight: 1 }}>⚠</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--red)', marginBottom: 2 }}>Error</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', wordBreak: 'break-word' }}>{message}</div>
      </div>
      {onDismiss && (
        <button onClick={onDismiss} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 18, lineHeight: 1, padding: 0 }}>×</button>
      )}
    </div>
  )
}
