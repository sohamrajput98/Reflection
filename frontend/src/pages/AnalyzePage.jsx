import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
import AgentWorkspaceLayout from '../components/AgentWorkspaceLayout'
import CampaignForm from '../components/CampaignForm'
import ResultsPanel from '../components/ResultsPanel'
import { ErrorBox } from '../components/ui'
import AgentChatPanel from '../components/AgentChatPanel'
import StepLoader from '../components/StepLoader'
import { clearViewState, loadViewState, persistViewState } from '../lib/viewState'
import {
  analyzeCampaign,
  getRecentAgentOutputs,
  ingestAgentOutputs,
  markRecommendationShown,
  runAgentOutputReflection,
  submitRecommendationFeedback,
} from '../api/api'

function Placeholder() {
  return (
    <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--text-muted)' }}>
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
        <span className="placeholder-icon-box">
          <Sparkles size={20} color="#111111" />
        </span>
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
        Ready
      </div>
      <p style={{ fontSize: 13, lineHeight: 1.6, maxWidth: 280, margin: '0 auto 24px' }}>
        Add campaign inputs, run analysis, and review results here.
      </p>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
        {['Comparison', 'Patterns', 'Insights', 'Recommendations'].map((step, i) => (
          <span key={step} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{
              padding: '3px 10px', borderRadius: 6, fontSize: 12,
              background: 'var(--surface)', border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
            }}>{step}</span>
            {i < 3 && <span style={{ color: 'var(--border-light)', fontSize: 12 }}>·</span>}
          </span>
        ))}
      </div>
    </div>
  )
}

const ANALYZE_STATE_KEY = 'marko-analyze-page-state'
const initialViewState = loadViewState(ANALYZE_STATE_KEY, {}) || {}

function buildAgentHealth(result) {
  if (!result) return []

  const comparisonFallback = result.comparison_report?.summary?.includes('Analysis temporarily unavailable.')
  const patternFallback = result.pattern_report?.pattern_report?.includes('Pattern detection temporarily unavailable.')
  const insightFallback = result.insights?.source === 'deterministic'
  const reflectionFallback = result.reflection?.evaluation_score === 0.5 && result.reflection?.reason === 'evaluation unavailable'

  return [
    {
      agent_name: 'analysis_agent',
      status: comparisonFallback ? 'fallback' : 'success',
      schema_valid: Boolean(result.comparison_report),
      cleanliness_score: comparisonFallback ? 1 : 3,
      missing_fields: comparisonFallback ? ['comparison_report.summary'] : [],
      fallback_used: comparisonFallback,
      latency_ms: null,
    },
    {
      agent_name: 'pattern_agent',
      status: patternFallback ? 'fallback' : 'success',
      schema_valid: Boolean(result.pattern_report),
      cleanliness_score: patternFallback ? 1 : 3,
      missing_fields: patternFallback ? ['pattern_report.findings'] : [],
      fallback_used: patternFallback,
      latency_ms: null,
    },
    {
      agent_name: 'insight_agent',
      status: insightFallback ? 'fallback' : 'success',
      schema_valid: Boolean(result.insights),
      cleanliness_score: result.insights?.recommendations?.length ? 3 : 1,
      missing_fields: result.insights?.recommendations?.length ? [] : ['insights.recommendations'],
      fallback_used: insightFallback,
      latency_ms: null,
    },
    {
      agent_name: 'memory_agent',
      status: result.stored_memory?.vector_saved ? 'success' : 'fallback',
      schema_valid: Boolean(result.stored_memory),
      cleanliness_score: result.stored_memory?.vector_saved ? 3 : 1,
      missing_fields: result.stored_memory?.vector_saved ? [] : ['stored_memory.vector_saved'],
      fallback_used: !result.stored_memory?.vector_saved,
      latency_ms: null,
    },
    {
      agent_name: 'reflection',
      status: reflectionFallback ? 'fallback' : 'success',
      schema_valid: Boolean(result.reflection),
      cleanliness_score: reflectionFallback ? 1 : 3,
      missing_fields: reflectionFallback ? ['reflection.reason'] : [],
      fallback_used: reflectionFallback,
      latency_ms: null,
    },
  ]
}

function DebugBlock({ title, children }) {
  return (
    <div className="workspace-main-card" style={{ padding: 16 }}>
      <div className="workspace-section-label" style={{ marginBottom: 10 }}>{title}</div>
      {children}
    </div>
  )
}

function DebugPre({ value }) {
  return (
    <pre className="debug-pre">
      {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
    </pre>
  )
}

function DebugSection({
  debugState,
  debugTab,
  onDebugTabChange,
  ingestionJson,
  onIngestionJsonChange,
  onValidateIngestion,
  onLoadStoredOutputs,
  onRunPipelineTest,
}) {
  const { ingestion } = debugState

  return (
    <section className="workspace-main-card" style={{ padding: 16, marginTop: 16 }}>
      <div className="workspace-section-label" style={{ marginBottom: 12 }}>Debug Mode</div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {[
          ['input', 'Agent Input Tester'],
          ['stored', 'Stored Data Viewer'],
          ['runner', 'Pipeline Test Runner'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={debugTab === key ? 'workspace-right-tab workspace-right-tab-active' : 'workspace-right-tab'}
            onClick={() => onDebugTabChange(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {debugTab === 'input' && (
          <DebugBlock title="Agent Input Tester">
            <textarea
              value={ingestionJson}
              onChange={e => onIngestionJsonChange(e.target.value)}
              className="input"
              rows={12}
              style={{ resize: 'vertical', marginBottom: 10 }}
            />
            <button type="button" className="btn-ghost" onClick={onValidateIngestion}>Validate</button>
            <div style={{ marginTop: 10 }}>
              <DebugPre value={ingestion.validation_response} />
            </div>
          </DebugBlock>
        )}

        {debugTab === 'stored' && (
          <DebugBlock title="Stored Data Viewer">
            <button type="button" className="btn-ghost" onClick={onLoadStoredOutputs}>Load Last 20</button>
            <div style={{ marginTop: 10 }}>
              <DebugPre value={ingestion.stored_outputs} />
            </div>
          </DebugBlock>
        )}

        {debugTab === 'runner' && (
          <DebugBlock title="Pipeline Test Runner">
            <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
              {['analysis_agent', 'pattern_agent', 'insight_agent', 'memory_agent'].map(name => (
                <button key={name} type="button" className="btn-ghost" onClick={() => onRunPipelineTest(name)}>
                  {name}
                </button>
              ))}
            </div>
            <DebugPre value={ingestion.runner_response} />
          </DebugBlock>
        )}
      </div>
    </section>
  )
}

export default function AnalyzePage({ debugMode = false }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [formCollapsed, setFormCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(initialViewState.rightCollapsed ?? false)
  const [rightTab, setRightTab] = useState(initialViewState.rightTab ?? 'chat')
  const [activeAgent, setActiveAgent] = useState(initialViewState.activeAgent ?? 'supervisor')
  const [formDraft, setFormDraft] = useState(null)
  const [debugTab, setDebugTab] = useState('input')
  const [ingestionJson, setIngestionJson] = useState(
    JSON.stringify(
      {
        agent_outputs: [
          {
            agent_name: 'insight_agent',
            recommendation_id: 'debug-rec-1',
            recommendation_type: 'recommendation',
            platform: 'meta',
            action: 'Increase budget for high-performing audience segment.',
            confidence: 0.82,
            priority: 'high',
            raw_payload: {},
          },
        ],
      },
      null,
      2,
    ),
  )
  const [debugState, setDebugState] = useState({
    trace: {
      request_id: null,
      request_json: null,
      response_json: null,
      latency_ms: null,
      status: 'idle',
      agent_health: [],
      raw_recommendations: [],
      validated_recommendations: [],
      dropped_recommendations: [],
    },
    database: {
      shown_response: null,
      feedback_response: null,
      stats_update_snapshot: null,
    },
    ingestion: {
      validation_response: null,
      stored_outputs: null,
      runner_response: null,
    },
    pipelineSummary: {
      caps_applied: { per_agent: 20, total: 100 },
      reflection_score: null,
      fallback_reason: null,
    },
  })

  async function handleSubmit(payload) {
    setLoading(true)
    setError(null)
    setResult(null)
    setFormCollapsed(true)
    setFormDraft(payload)
    const requestId = crypto?.randomUUID?.() || `debug-${Date.now()}`
    try {
      const debugResponse = await analyzeCampaign(payload, { debug: debugMode })
      if (debugMode) {
        if (!debugResponse.ok) {
          throw new Error(debugResponse.error || 'Unexpected error. Please try again.')
        }
        const data = debugResponse.body
        setResult(data)
        const rawRecommendations = data?.insights?.recommendations || []
        const validatedRecommendations = rawRecommendations.filter(item => {
          const value = String(item || '').trim().toLowerCase()
          return value && !['string', 'unknown', 'none'].includes(value)
        }).slice(0, 20)
        setDebugState({
          trace: {
            request_id: requestId,
            request_json: payload,
            response_json: data,
            latency_ms: debugResponse.latency_ms,
            status: debugResponse.status,
            agent_health: buildAgentHealth(data),
            raw_recommendations: rawRecommendations,
            validated_recommendations: validatedRecommendations,
            dropped_recommendations: rawRecommendations
              .filter(item => !validatedRecommendations.includes(item))
              .map(item => ({ value: item, reason: 'invalid_or_filtered_runtime_recommendation' })),
          },
          database: {
            shown_response: null,
            feedback_response: null,
            stats_update_snapshot: null,
          },
          ingestion: {
            validation_response: null,
            stored_outputs: null,
            runner_response: null,
          },
          pipelineSummary: {
            caps_applied: {
              per_agent: Math.min(validatedRecommendations.length, 20),
              total: Math.min(validatedRecommendations.length, 100),
            },
            reflection_score: data?.reflection?.evaluation_score ?? null,
            fallback_reason: data?.reflection?.reason || null,
          },
        })
        return
      }
      const data = await analyzeCampaign(payload)
      setResult(data)
    } catch (e) {
      setError(e.message || 'Unexpected error. Please try again.')
      setFormCollapsed(false)
    } finally {
      setLoading(false)
    }
  }

  const suggestions = useMemo(() => {
    if (!result?.insights?.recommendations?.length) return []
    return result.insights.recommendations.slice(0, 3)
  }, [result])

  const agentMeta = {
    supervisor: {
      section: 'Orchestrator',
      title: 'Supervisor Agent',
      description: 'Coordinates the workflow and keeps the strongest results in focus.',
      tab: null,
    },
    analysis: {
      section: 'Specialist Agent',
      title: 'Analysis Agent',
      description: 'Tracks score movement and core efficiency metrics.',
      tab: 'performance',
    },
    pattern: {
      section: 'Specialist Agent',
      title: 'Pattern Agent',
      description: 'Surfaces recurring signals, wins, and inefficiencies.',
      tab: 'patterns',
    },
    insight: {
      section: 'Specialist Agent',
      title: 'Insight Agent',
      description: 'Turns output into narrative insight and takeaways.',
      tab: 'insights',
    },
    memory: {
      section: 'Specialist Agent',
      title: 'Memory Agent',
      description: 'Recalls similar campaigns and retained actions.',
      tab: null,
    },
  }

  const currentAgent = agentMeta[activeAgent] || agentMeta.supervisor

  useEffect(() => {
    clearViewState(ANALYZE_STATE_KEY)
    persistViewState(ANALYZE_STATE_KEY, {
      rightCollapsed,
      rightTab,
      activeAgent,
      formDraft,
    })
  }, [rightCollapsed, rightTab, activeAgent, formDraft])

  const chatContext = useMemo(() => ({
    agentTitle: currentAgent.title,
    narrative: result?.insights?.narrative_summary || '',
    keyLearnings: result?.insights?.key_learnings || [],
    recommendations: result?.insights?.recommendations || [],
    patterns: result?.pattern_report?.auto_tags || [],
    comparison: result?.comparison_report?.summary || [],
    memory: (result?.similar_campaigns || []).map(item => item.campaign_id || item.document_id),
  }), [currentAgent.title, result])

  async function handleDebugShown() {
    if (!debugMode || !result?.comparison_report?.campaign_id) return
    const recommendation = (debugState.trace.validated_recommendations[0] || debugState.trace.raw_recommendations[0] || 'debug-recommendation')
    const shownPayload = {
      recommendation_id: `${result.comparison_report.campaign_id}-debug-rec-1`,
      campaign_id: result.comparison_report.campaign_id,
      recommendation_type: 'recommendation',
      platform: formDraft?.platform || 'unknown',
    }
    try {
      const response = await markRecommendationShown(shownPayload, { debug: true })
      setDebugState(prev => ({
        ...prev,
        database: {
          ...prev.database,
          shown_response: response,
          stats_update_snapshot: {
            recommendation_id: shownPayload.recommendation_id,
            last_action: 'shown',
            recommendation_preview: recommendation,
          },
        },
      }))
    } catch (e) {
      setDebugState(prev => ({
        ...prev,
        database: { ...prev.database, shown_response: { error: e.message || 'Shown request failed' } },
      }))
    }
  }

  async function handleDebugFeedback(accepted) {
    if (!debugMode || !result?.comparison_report?.campaign_id) return
    const payload = {
      recommendation_id: `${result.comparison_report.campaign_id}-debug-rec-1`,
      accepted,
    }
    try {
      const response = await submitRecommendationFeedback(payload, { debug: true })
      setDebugState(prev => ({
        ...prev,
        database: {
          ...prev.database,
          feedback_response: response,
          stats_update_snapshot: {
            recommendation_id: payload.recommendation_id,
            last_action: accepted ? 'accepted' : 'rejected',
            accepted,
          },
        },
      }))
    } catch (e) {
      setDebugState(prev => ({
        ...prev,
        database: { ...prev.database, feedback_response: { error: e.message || 'Feedback request failed' } },
      }))
    }
  }

  async function handleValidateIngestion() {
    try {
      const payload = JSON.parse(ingestionJson)
      const response = await ingestAgentOutputs(payload, { debug: true })
      setDebugState(prev => ({
        ...prev,
        ingestion: { ...prev.ingestion, validation_response: response },
      }))
    } catch (e) {
      setDebugState(prev => ({
        ...prev,
        ingestion: { ...prev.ingestion, validation_response: { error: e.message || 'Invalid JSON' } },
      }))
    }
  }

  async function handleLoadStoredOutputs() {
    const response = await getRecentAgentOutputs(20, { debug: true })
    setDebugState(prev => ({
      ...prev,
      ingestion: { ...prev.ingestion, stored_outputs: response },
    }))
  }

  async function handleRunPipelineTest(agentName) {
    const response = await runAgentOutputReflection({ agent_name: agentName }, { debug: true })
    setDebugState(prev => ({
      ...prev,
      ingestion: { ...prev.ingestion, runner_response: response },
    }))
  }

  function renderAgentResultView() {
    if (loading) return <StepLoader />
    if (!result && !error) return <Placeholder />
    if (!result) return null

    if (activeAgent === 'memory') {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="workspace-main-card">
            <div className="workspace-section-label">Campaign Memory</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: '6px 0 12px' }}>
              Similar Campaign Recall
            </div>
            {result.similar_campaigns?.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {result.similar_campaigns.map((item, index) => (
                  <div key={index} className="workspace-suggestion-item">
                    <span className="workspace-suggestion-index">{Math.round(item.score * 100)}</span>
                    <span>
                      <strong style={{ color: 'var(--text-primary)' }}>{item.campaign_id || item.document_id}</strong>{' '}
                      <span style={{ color: 'var(--text-muted)' }}>{item.summary}</span>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="workspace-side-muted">No similar campaign memory available yet.</div>
            )}
          </div>

          <div className="workspace-main-card">
            <div className="workspace-section-label">Retained Actions</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: '6px 0 12px' }}>
              Stored Recommendations
            </div>
            {result.insights?.recommendations?.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {result.insights.recommendations.map((item, index) => (
                  <div key={index} className="workspace-suggestion-item">
                    <span className="workspace-suggestion-index">{index + 1}</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="workspace-side-muted">No retained recommendations yet.</div>
            )}
          </div>
        </div>
      )
    }

    return (
      <ResultsPanel
        result={result}
        forcedTab={currentAgent.tab || undefined}
        showOverview={activeAgent === 'supervisor'}
      />
    )
  }

  return (
    <AgentWorkspaceLayout
      activeAgent={activeAgent}
      rightCollapsed={rightCollapsed}
      onToggleRight={() => setRightCollapsed(value => !value)}
      onAgentSelect={setActiveAgent}
      leftContent={
        <div className="workspace-side-card workspace-sidebar-footer-card" style={{ marginTop: 24 }}>
          <div className="workspace-section-label">{currentAgent.title}</div>
          <p style={{ margin: '8px 0 0', fontSize: 12, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            {currentAgent.description}
          </p>
        </div>
      }
      mainContent={
        <div className="workspace-main-inner">
          <div className="workspace-main-header workspace-main-hero-card">
            <div>
              <div className="workspace-section-label">{currentAgent.section}</div>
              <h1 style={{ margin: '4px 0 6px', fontSize: 24, fontWeight: 700, color: 'var(--text-primary)' }}>
                {currentAgent.title}
              </h1>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, maxWidth: 560 }}>
                {currentAgent.description}
              </p>
            </div>
            {result && (
              <button type="button" className="btn-ghost" onClick={() => setFormCollapsed(value => !value)}>
                {formCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                {formCollapsed ? 'Expand Setup' : 'Collapse Setup'}
              </button>
            )}
          </div>

          {error && <ErrorBox message={error} onDismiss={() => setError(null)} />}

          {result && !loading && (
            <div className="workspace-results-first">
              <div className="workspace-section-label">Priority Results</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {activeAgent === 'supervisor'
                  ? 'Results stay in focus. Setup stays available below when needed.'
                  : `${currentAgent.title} is focused on its assigned view.`}
              </div>
            </div>
          )}

          {!loading && (!formCollapsed || !result) && (
            <section className="workspace-main-card workspace-main-form-card">
              <div style={{ marginBottom: 16 }}>
                <div className="workspace-section-label">Campaign Analysis</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                  Setup
                </div>
                <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, maxWidth: 520 }}>
                  Enter campaign inputs and benchmark metrics. Analysis routes automatically after submission.
                </p>
              </div>
              <CampaignForm
                onSubmit={handleSubmit}
                loading={loading}
                onDraftChange={setFormDraft}
              />
            </section>
          )}

          <section className="workspace-results-area">{renderAgentResultView()}</section>
          {debugMode && (
            <DebugSection
              debugState={debugState}
              debugTab={debugTab}
              onDebugTabChange={setDebugTab}
              ingestionJson={ingestionJson}
              onIngestionJsonChange={setIngestionJson}
              onValidateIngestion={handleValidateIngestion}
              onLoadStoredOutputs={handleLoadStoredOutputs}
              onRunPipelineTest={handleRunPipelineTest}
            />
          )}
        </div>
      }
      rightTab={rightTab}
      onRightTabChange={setRightTab}
      chatContent={<AgentChatPanel context={chatContext} />}
      suggestionContent={
        result ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(activeAgent === 'analysis'
              ? (result.comparison_report?.summary || []).slice(0, 3)
              : activeAgent === 'pattern'
                ? result.pattern_report?.auto_tags || []
                : activeAgent === 'memory'
                  ? (result.similar_campaigns || []).slice(0, 3).map(item => item.campaign_id || item.document_id)
                  : suggestions
            ).length > 0 ? (
              (activeAgent === 'analysis'
                ? (result.comparison_report?.summary || []).slice(0, 3)
                : activeAgent === 'pattern'
                  ? result.pattern_report?.auto_tags || []
                  : activeAgent === 'memory'
                    ? (result.similar_campaigns || []).slice(0, 3).map(item => item.campaign_id || item.document_id)
                    : suggestions
              ).map((item, index) => (
                <div key={index} className="workspace-suggestion-item">
                  <span className="workspace-suggestion-index">{index + 1}</span>
                  <span>{item}</span>
                </div>
              ))
            ) : (
              <div className="workspace-side-muted">No active suggestions</div>
            )}
          </div>
        ) : (
          <div className="workspace-side-muted">No active suggestions</div>
        )
      }
      systemStatus={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="workspace-status-row">
            <span>Supervisor</span>
            <span>{loading ? 'Running' : result ? 'Ready' : 'Idle'}</span>
          </div>
          <div className="workspace-status-row">
            <span>Analysis Agent</span>
            <span>{loading ? 'Processing' : result ? 'Completed' : 'Waiting'}</span>
          </div>
          <div className="workspace-status-row">
            <span>Insight Agent</span>
            <span>{result ? 'Synced' : 'Standby'}</span>
          </div>
        </div>
      }
    />
  )
}
