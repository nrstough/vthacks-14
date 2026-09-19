import { SCENARIOS } from '../fixtures/scenarios'
import { shortDate } from '../lib/format'
import type { SolveRequest } from '../types'

type Tab = 'plan' | 'wallet'

interface Props {
  tab: Tab
  onTab: (tab: Tab) => void
  req: SolveRequest
  opening: number
  buffer: number
  onScenario: (openingCents: number, bufferCents: number) => void
  source: 'local' | 'server'
  notice: string | null
}

/**
 * The bar the eye starts on. It carries the scenario switch, because that is
 * the control a judge reaches for first, and the offline chip, because the
 * chip has to be visible on every tab — CLAUDE.md is explicit that the product
 * never shows solver results without disclosing where they came from, and the
 * wallet tab is a place a person can be standing when the wifi dies.
 */
export default function Topbar({
  tab,
  onTab,
  req,
  opening,
  buffer,
  onScenario,
  source,
  notice,
}: Props) {
  return (
    <header className="topbar">
      <h1>{tab === 'plan' ? 'Checking account' : 'Demo wallet'}</h1>

      <p className="topbar-horizon num">
        {shortDate(req.as_of)} – {shortDate(req.horizon_end)}, 2026
      </p>

      {tab === 'plan' && (
        <div className="switcher" role="group" aria-label="Starting position">
          {SCENARIOS.map((s) => (
            <button
              key={s.key}
              type="button"
              aria-pressed={
                s.request.opening_balance_cents === opening && s.request.buffer_cents === buffer
              }
              title={s.blurb}
              onClick={() => onScenario(s.request.opening_balance_cents, s.request.buffer_cents)}
            >
              {s.name.replace('Checking, ', '')}
            </button>
          ))}
        </div>
      )}

      <div className="topbar-actions">
        {source === 'local' && (
          <span className="meta-local" title={notice ?? undefined}>
            Running on the built-in solver
          </span>
        )}

        {/* The sidebar is hidden below 900px, so the view switch has to exist
            somewhere else at that width. This is that somewhere. */}
        <nav className="tabs only-narrow" aria-label="Views">
          <button
            type="button"
            className={tab === 'plan' ? 'on' : ''}
            aria-pressed={tab === 'plan'}
            onClick={() => onTab('plan')}
          >
            Checking
          </button>
          <button
            type="button"
            className={tab === 'wallet' ? 'on' : ''}
            aria-pressed={tab === 'wallet'}
            onClick={() => onTab('wallet')}
          >
            Wallet
          </button>
        </nav>

        <div className="topbar-user">
          <span className="avatar" aria-hidden="true">
            SA
          </span>
          <span className="name">Sample account</span>
        </div>
      </div>
    </header>
  )
}
