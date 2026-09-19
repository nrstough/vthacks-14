import { money } from '../lib/format'
import { SCENARIOS } from '../fixtures/scenarios'
import type { SolveResponse } from '../types'

type Tab = 'plan' | 'wallet'

interface Props {
  tab: Tab
  onTab: (tab: Tab) => void
  opening: number
  buffer: number
  onScenario: (openingCents: number, bufferCents: number) => void
  res: SolveResponse
  locked: number
  onClearOverrides: () => void
}

/**
 * The left rail: what you are looking at, and which account you are looking at
 * it for. It is hidden below 900px, so nothing lives here that cannot also be
 * reached from the topbar.
 */
export default function Sidebar({
  tab,
  onTab,
  opening,
  buffer,
  onScenario,
  res,
  locked,
  onClearOverrides,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="mark" aria-hidden="true">
          OG
        </span>
        Overdraft Guard
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title" id="nav-views">
          Views
        </div>
        <nav aria-labelledby="nav-views">
          <button
            type="button"
            className={`sidebar-item${tab === 'plan' ? ' on' : ''}`}
            aria-current={tab === 'plan' ? 'page' : undefined}
            onClick={() => onTab('plan')}
          >
            Checking account
            {/* Red is an alarm, so it is spent only on the one state that is
                one: a gap no combination of changes closes. */}
            {res.tier === 3 && (
              <span className="badge" title="Outside cash is needed">
                !
              </span>
            )}
          </button>
          <button
            type="button"
            className={`sidebar-item${tab === 'wallet' ? ' on' : ''}`}
            aria-current={tab === 'wallet' ? 'page' : undefined}
            onClick={() => onTab('wallet')}
          >
            Demo wallet
          </button>
        </nav>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title" id="nav-scenarios">
          Starting position
        </div>
        <nav aria-labelledby="nav-scenarios">
          {SCENARIOS.map((s) => {
            const on =
              s.request.opening_balance_cents === opening && s.request.buffer_cents === buffer
            return (
              <button
                key={s.key}
                type="button"
                className={`sidebar-item${on ? ' on' : ''}`}
                aria-pressed={on}
                title={s.blurb}
                onClick={() => onScenario(s.request.opening_balance_cents, s.request.buffer_cents)}
              >
                {s.name}
              </button>
            )
          })}
        </nav>
      </div>

      <div className="sidebar-footer">
        {locked > 0 ? (
          <div className="sidebar-promo">
            <p className="p-title">Ruled out</p>
            <p className="p-body">
              {locked} change{locked === 1 ? '' : 's'} the solver was not allowed to use.
            </p>
            <button type="button" onClick={onClearOverrides}>
              Put {locked === 1 ? 'it' : 'them'} back
            </button>
          </div>
        ) : (
          <div className="sidebar-promo">
            <p className="p-title">This solve</p>
            <p className="p-body num">
              {res.meta.solver} · {res.meta.wall_ms} ms · {res.meta.candidates_considered} change
              {res.meta.candidates_considered === 1 ? '' : 's'} considered, against a{' '}
              {money(buffer)} cushion.
            </p>
          </div>
        )}
      </div>
    </aside>
  )
}
