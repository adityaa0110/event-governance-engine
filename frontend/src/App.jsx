import { useEffect, useState } from 'react'
import { api } from './api'
import { beginLogin, can, completeLogin, logout } from './auth'
import { ContractEditor, DiffView } from './contractUi'
import './index.css'

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'analyze', label: 'Analyze PRD' },
  { id: 'catalogue', label: 'Catalogue' },
  { id: 'validate', label: 'Validate' },
]

const INVALID_SAMPLE = `trackEvent("buy_now", {
  productId: 123,
  price: "499"
});`

const VALID_SAMPLE = `trackEvent("purchase_button_clicked", {
  product_id: "123",
  product_category: "broadband",
  price: 499,
  customer_type: "existing"
});`

function Badge({ children, kind }) {
  return <span className={`badge ${kind || ''}`}>{children}</span>
}

function Dashboard({ stats, onGo }) {
  return (
    <div>
      <section className="panel">
        <h2>Event Governance Engine</h2>
        <p className="sub">
          AI proposes standards. Deterministic rules enforce them before merge.
        </p>
        {stats?.alert && <div className="error-box">{stats.alert}</div>}
        <div className="grid-stats">
          <div className="stat">
            <div className="label">Events</div>
            <div className="value">{stats?.total_events ?? '—'}</div>
          </div>
          <div className="stat">
            <div className="label">Approved</div>
            <div className="value">{stats?.active ?? '—'}</div>
          </div>
          <div className="stat">
            <div className="label">In review</div>
            <div className="value">{stats?.in_review ?? '—'}</div>
          </div>
          <div className="stat">
            <div className="label">Pass rate</div>
            <div className="value">
              {stats?.pass_rate != null ? `${stats.pass_rate}%` : '—'}
            </div>
          </div>
        </div>

        <div className="flow">
          <div className="flow-step">
            <strong>1. PRD</strong>
            <span>Understand the user journey</span>
          </div>
          <div className="flow-step">
            <strong>2. AI</strong>
            <span>Discover & standardize events</span>
          </div>
          <div className="flow-step">
            <strong>3. Contract</strong>
            <span>Name, params, types, platforms</span>
          </div>
          <div className="flow-step">
            <strong>4. Validate</strong>
            <span>Scan trackEvent in code</span>
          </div>
          <div className="flow-step">
            <strong>5. CI</strong>
            <span>PASS / FAIL before merge</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>The drift problem</h2>
        <p className="sub">Same business action, five incompatible implementations.</p>
        <div className="platforms-drift">
          <div>
            <strong>App</strong>
            <code>buy_now</code>
          </div>
          <div>
            <strong>Shop</strong>
            <code>purchase_click</code>
          </div>
          <div>
            <strong>Bot</strong>
            <code>buyNowClicked</code>
          </div>
          <div>
            <strong>TV</strong>
            <code>purchaseButton</code>
          </div>
          <div>
            <strong>Broadband</strong>
            <code>buy_now_clicked</code>
          </div>
        </div>
        <div className="toolbar" style={{ marginTop: 18 }}>
          <button className="btn btn-primary" onClick={() => onGo('analyze')}>
            Start demo: Analyze PRD
          </button>
          <button className="btn btn-secondary" onClick={() => onGo('validate')}>
            Jump to validation
          </button>
        </div>
      </section>
    </div>
  )
}

function Analyze({ onOpenEvent }) {
  const [requirement, setRequirement] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [decisions, setDecisions] = useState({})

  async function recordDecision(ev, decision) {
    setError('')
    try {
      await api.decide({ requirement, decision, event: ev })
      setDecisions((current) => ({ ...current, [ev.event_name]: decision }))
    } catch (err) {
      setError(err.message)
    }
  }

  async function loadDemo() {
    setError('')
    const data = await api.demoPrd()
    setRequirement(data.requirement)
  }

  useEffect(() => {
    loadDemo().catch((e) => setError(e.message))
  }, [])

  async function runGenerate() {
    setLoading(true)
    setError('')
    try {
      const data = await api.generate(requirement, 'BROADBAND')
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="split">
      <section className="panel">
        <h2>Analyze requirement</h2>
        <p className="sub">Paste a Jira / PRD story. AI recommends standardized events.</p>
        {error && <div className="error-box">{error}</div>}
        <div className="toolbar">
          <button className="btn btn-secondary" onClick={loadDemo}>
            Load Buy Now PRD
          </button>
          <button className="btn btn-primary" onClick={runGenerate} disabled={loading || !requirement}>
            {loading ? 'Analyzing…' : 'Generate events'}
          </button>
        </div>
        <textarea
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
          placeholder="Describe the feature and user journey…"
        />
      </section>

      <section className="panel">
        <h2>Recommended events</h2>
        <p className="sub">
          {result
            ? `${result.source === 'llm' ? 'LLM' : 'Demo analyzer'} · ${result.message}`
            : 'Results appear here after generation.'}
        </p>
        {result?.llm_error && <div className="error-box">LLM failed: {result.llm_error}</div>}
        <div className="event-list">
          {(result?.events || []).map((ev) => (
            <div key={ev.event_name} className="event-card">
              <div className="name">{ev.event_name}</div>
              <div className="muted">{ev.description}</div>
              <div className="meta">
                {ev.reuse_existing && <Badge kind="reuse">Reuse existing</Badge>}
                {ev.similarity != null && (
                  <Badge>Similarity {Math.round(ev.similarity * 100)}%</Badge>
                )}
                {(ev.platforms || []).slice(0, 3).map((p) => (
                  <Badge key={p}>{p}</Badge>
                ))}
              </div>
              {ev.recommendation && <div className="muted">{ev.recommendation}</div>}
              <div className="toolbar">
                {!ev.reuse_existing && (
                  <button className="btn btn-primary" onClick={() => recordDecision(ev, 'accepted')}>
                    Create draft
                  </button>
                )}
                <button className="btn btn-secondary" onClick={() => recordDecision(ev, 'rejected')}>
                  Reject
                </button>
                <button className="btn btn-secondary" onClick={() => onOpenEvent(ev.event_name)}>
                  Open
                </button>
              </div>
              {decisions[ev.event_name] && (
                <div className="muted">Recorded as {decisions[ev.event_name]}.</div>
              )}
            </div>
          ))}
          {!result && <p className="muted">No events generated yet.</p>}
        </div>
      </section>
    </div>
  )
}

function Catalogue({ selectedName, setSelectedName, principal }) {
  const [q, setQ] = useState('')
  const [events, setEvents] = useState([])
  const [detail, setDetail] = useState(null)
  const [diff, setDiff] = useState(null)
  const [error, setError] = useState('')
  async function createDraft(payload) {
    setError('')
    try {
      const created = await api.createEvent({
        event_name: payload.event_name,
        description: payload.description,
        platforms: ['BROADBAND'],
        parameters: payload.parameters,
      })
      setSelectedName(created.event_name)
      await refresh(q, created.event_name)
    } catch (err) {
      setError(err.message)
    }
  }

  async function saveDraft(payload) {
    setError('')
    try {
      const saved = await api.updateEvent(detail.event_name, {
        description: payload.description,
        parameters: payload.parameters,
        expected_revision: detail.revision,
      })
      setDetail(saved)
      setDiff(await api.diff(saved.event_name))
    } catch (err) {
      setError(err.message)
    }
  }

  async function refresh(query = q, name = selectedName) {
    setError('')
    try {
      const page = await api.listEvents(query)
      const list = page.items || []
      setEvents(list)
      const next = name || list[0]?.event_name
      if (next) {
        setSelectedName(next)
        setDetail(await api.getEvent(next))
        setDiff(await api.diff(next))
      }
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    refresh().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!selectedName) return
    api
      .getEvent(selectedName)
      .then(setDetail)
      .catch((e) => setError(e.message))
    api
      .diff(selectedName)
      .then(setDiff)
      .catch(() => setDiff(null))
  }, [selectedName])

  return (
    <div className="split">
      <section className="panel">
        <h2>Event catalogue</h2>
        <p className="sub">Central source of truth for approved analytics contracts.</p>
        {error && <div className="error-box">{error}</div>}
        <div className="toolbar">
          <input
            type="search"
            placeholder="Search purchase, buy, checkout…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && refresh(q)}
          />
          <button className="btn btn-secondary" onClick={() => refresh(q)}>
            Search
          </button>
        </div>
        {can(principal, 'editor') && <ContractEditor onSubmit={createDraft} />}
        <div className="event-list">
          {events.map((ev) => (
            <button
              key={ev.event_name}
              className={`event-card ${selectedName === ev.event_name ? 'active' : ''}`}
              onClick={() => setSelectedName(ev.event_name)}
            >
              <div className="name">{ev.event_name}</div>
              <div className="meta">
                <Badge kind={ev.status === 'APPROVED' || ev.status === 'ACTIVE' ? 'active' : ev.status === 'DEPRECATED' ? 'deprecated' : 'review'}>
                  {ev.status}
                </Badge>
                {(ev.platforms || []).map((p) => (
                  <Badge key={p}>{p}</Badge>
                ))}
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Contract detail</h2>
        {!detail ? (
          <p className="muted">Select an event</p>
        ) : (
          <>
            <h3 style={{ marginTop: 0, fontFamily: 'var(--font-display)' }}>
              {detail.event_name}
            </h3>
            <div className="meta" style={{ marginBottom: 12 }}>
              <Badge kind={detail.status === 'APPROVED' || detail.status === 'ACTIVE' ? 'active' : detail.status === 'DEPRECATED' ? 'deprecated' : 'review'}>
                {detail.status}
              </Badge>
              <Badge>v{detail.version}</Badge>
              {(detail.platforms || []).map((p) => (
                <Badge key={p}>{p}</Badge>
              ))}
            </div>
            <p className="muted">{detail.description}</p>
            <DiffView diff={diff} />
            {(detail.status === 'DRAFT' || detail.status === 'REVIEW') && can(principal, 'editor') && (
              <ContractEditor key={`${detail.event_name}-${detail.revision}`} initial={detail} onSubmit={saveDraft} />
            )}
            <WorkflowActions
              event={detail}
              principal={principal}
              onChanged={async (next) => {
                setDetail(next)
                setDiff(await api.diff(next.event_name).catch(() => null))
              }}
            />
            {detail.replacement && (
              <p>
                Replacement: <strong>{detail.replacement}</strong>
              </p>
            )}
            <table className="table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Type</th>
                  <th>Required</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(detail.parameters || {}).map(([name, spec]) => (
                  <tr key={name}>
                    <td>
                      <code>{name}</code>
                    </td>
                    <td>{spec.type}</td>
                    <td>{spec.required ? 'REQUIRED' : 'optional'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    </div>
  )
}

function Validate() {
  const [code, setCode] = useState(INVALID_SAMPLE)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  async function run(payload) {
    setLoading(true)
    setError('')
    try {
      const data = await api.validate(payload)
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="split">
      <section className="panel">
        <h2>Code validation</h2>
        <p className="sub">
          Compare <code>trackEvent(...)</code> against the event contract. This is the CI gate.
        </p>
        {error && <div className="error-box">{error}</div>}
        <div className="toolbar">
          <button
            className="btn btn-danger"
            onClick={() => {
              setCode(INVALID_SAMPLE)
              run({ sample: 'invalid' })
            }}
            disabled={loading}
          >
            Run invalid sample
          </button>
          <button
            className="btn btn-ok"
            onClick={() => {
              setCode(VALID_SAMPLE)
              run({ sample: 'valid' })
            }}
            disabled={loading}
          >
            Run valid sample
          </button>
          <button
            className="btn btn-primary"
            onClick={() => run({ code })}
            disabled={loading}
          >
            {loading ? 'Validating…' : 'Validate pasted code'}
          </button>
        </div>
        <textarea value={code} onChange={(e) => setCode(e.target.value)} />
      </section>

      <section className="panel">
        <h2>Governance report</h2>
        {!result ? (
          <p className="muted">Run a sample to see PASS / FAIL.</p>
        ) : (
          <>
            <div
              className={`status-banner ${
                result.status === 'PASSED' ? 'passed' : 'failed'
              }`}
            >
              <strong>
                {result.status === 'PASSED'
                  ? 'EVENT GOVERNANCE: PASSED ✅'
                  : 'EVENT GOVERNANCE: FAILED ❌'}
              </strong>
              <span>
                {result.events_found} event(s) · {result.issues.length} issue(s)
              </span>
            </div>

            {result.issues.map((issue, idx) => (
              <div className="issue" key={`${issue.code}-${idx}`}>
                <div className="code-tag">{issue.code}</div>
                <div>{issue.message}</div>
              </div>
            ))}

            {result.status === 'PASSED' && (
              <div className="code">{`✓ Event exists
✓ Contract valid
✓ Parameters valid
✓ Types valid
STATUS: PASS ✅`}</div>
            )}

            {result.suggested_implementation && result.status === 'FAILED' && (
              <>
                <h3 style={{ fontFamily: 'var(--font-display)' }}>Suggested fix</h3>
                <div className="code">{result.suggested_implementation}</div>
              </>
            )}
          </>
        )}
      </section>
    </div>
  )
}

function WorkflowActions({ event, principal, onChanged }) {
  const [error, setError] = useState('')
  const [replacement, setReplacement] = useState('purchase_button_clicked')
  const [comment, setComment] = useState('')

  async function run(action) {
    setError('')
    try {
      onChanged(
        await api.transition(
          event.event_name,
          action,
          action === 'deprecate' ? replacement : undefined,
          action === 'reject' ? comment.trim() : undefined,
          event.revision,
        ),
      )
      if (action === 'reject') setComment('')
    } catch (err) {
      setError(err.message)
    }
  }

  if (!event) return null
  return (
    <div className="workflow">
      {error && <div className="error-box">{error}</div>}
      <div className="toolbar">
        {event.status === 'DRAFT' && can(principal, 'editor') && (
          <button className="btn btn-primary" onClick={() => run('submit')}>Submit for review</button>
        )}
        {event.status === 'REVIEW' && can(principal, 'approver') && (
          <>
            <button className="btn btn-ok" onClick={() => run('approve')}>Approve</button>
            <input className="replacement" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Rejection comment" />
            <button className="btn btn-secondary" onClick={() => run('reject')} disabled={!comment.trim()}>Reject</button>
          </>
        )}
        {event.status === 'APPROVED' && can(principal, 'editor') && (
          <button className="btn btn-secondary" onClick={() => run('revise')}>Revise</button>
        )}
        {event.status === 'APPROVED' && can(principal, 'approver') && (
          <>
            <input className="replacement" value={replacement} onChange={(e) => setReplacement(e.target.value)} placeholder="Replacement event" />
            <button className="btn btn-danger" onClick={() => run('deprecate')}>Deprecate</button>
          </>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [stats, setStats] = useState(null)
  const [selectedName, setSelectedName] = useState('purchase_button_clicked')
  const [apiOk, setApiOk] = useState(null)
  const [principal, setPrincipal] = useState(null)
  const [config, setConfig] = useState(null)
  const [history, setHistory] = useState([])
  const [audit, setAudit] = useState([])
  const [decisions, setDecisions] = useState([])
  const [authError, setAuthError] = useState('')

  useEffect(() => {
    completeLogin()
      .catch((error) => setAuthError(error.message))
      .finally(() => {
        api.config().then(setConfig).catch(() => {})
        api.me().then(setPrincipal).catch(() => setPrincipal(null))
      })
  }, [])

  useEffect(() => {
    api
      .health()
      .then(() => setApiOk(true))
      .catch(() => setApiOk(false))
    api.stats().then(setStats).catch(() => {})
    api.listValidations().then(setHistory).catch(() => {})
    api.audit().then((page) => setAudit(page.items || [])).catch(() => {})
    api.recommendations().then((page) => setDecisions(page.items || [])).catch(() => {})
  }, [tab])

  function openEvent(name) {
    setSelectedName(name)
    setTab('catalogue')
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <span />
            Event Governance
          </div>
          <h1>Define once. Validate everywhere.</h1>
          <p className="tagline">Trust your analytics — before production.</p>
          <p>
            API:{' '}
            {apiOk === null ? 'checking…' : apiOk ? 'connected' : 'offline — start backend on :8001'}
            {principal ? ` · ${principal.name}` : ''}
          </p>
          {authError && <div className="error-box">{authError}</div>}
          {config?.auth_required && (
            <div className="toolbar">
              {principal ? (
                <button className="btn btn-secondary" onClick={() => { logout(); setPrincipal(null) }}>Sign out</button>
              ) : (
                <button className="btn btn-primary" onClick={() => beginLogin(config).catch((error) => setAuthError(error.message))}>
                  Sign in
                </button>
              )}
            </div>
          )}
        </div>
        <nav className="nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? 'active' : ''}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {tab === 'dashboard' && (
        <>
          <Dashboard stats={stats} onGo={setTab} />
          <section className="panel">
            <h2>Recent governance activity</h2>
            <div className="split">
              <div>
                <h3>Validations</h3>
                {history.map((item) => (
                  <p key={item.id}>{item.status} · {item.events_found} event(s) · {item.issues_count} issue(s)</p>
                ))}
                {!history.length && <p className="muted">No validations yet.</p>}
              </div>
              <div>
                <h3>Audit</h3>
                {audit.map((item) => (
                  <p key={item.id}>{item.action} · {item.entity_id} · {item.actor}{item.comment ? ` · ${item.comment}` : ''}</p>
                ))}
                {!audit.length && <p className="muted">No catalogue changes yet.</p>}
              </div>
              <div>
                <h3>Recommendation decisions</h3>
                {decisions.map((item) => (
                  <p key={item.id}>{item.decision} · {item.event_name || 'unnamed'} · {item.actor}</p>
                ))}
                {!decisions.length && <p className="muted">No recommendation decisions yet.</p>}
              </div>
            </div>
          </section>
        </>
      )}
      {tab === 'analyze' && <Analyze onOpenEvent={openEvent} />}
      {tab === 'catalogue' && (
        <Catalogue selectedName={selectedName} setSelectedName={setSelectedName} principal={principal} />
      )}
      {tab === 'validate' && <Validate />}
    </div>
  )
}
