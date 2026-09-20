import type { SolveResponse } from '../types'

type Tab = 'plan' | 'wallet'

interface Props {
  tab: Tab
  onTab: (tab: Tab) => void
  res: SolveResponse
  source: 'local' | 'server'
  notice: string | null
}

/**
 * The bar on the gradient. It carries the view pills and the solver
 * disclosure, which has to be visible on every tab: CLAUDE.md is explicit that
 * the product never shows solver output without saying where it came from, and
 * the wallet tab is a place a person can be standing when the wifi dies.
 */
export default function TopNav({ tab, onTab, res, source, notice }: Props) {
  return (
    <header className="navbar">
      <div className="brand">
        <span className="mark" aria-hidden="true">
          S
        </span>
        Safe to Spend
      </div>

      <nav className="pillnav" aria-label="Views">
        <button
          type="button"
          className={tab === 'plan' ? 'on' : ''}
          aria-current={tab === 'plan' ? 'page' : undefined}
          onClick={() => onTab('plan')}
        >
          Checking account
          {/* One dot, spent on the one state that is an alarm: a gap no
              combination of changes closes. */}
          {res.tier === 3 && <span className="dot" title="Outside cash is needed" />}
        </button>
        <button
          type="button"
          className={tab === 'wallet' ? 'on' : ''}
          aria-current={tab === 'wallet' ? 'page' : undefined}
          onClick={() => onTab('wallet')}
        >
          Demo wallet
        </button>
      </nav>

      <div className="nav-right">
        <span className="nav-chip" title={source === 'local' ? (notice ?? undefined) : undefined}>
          {source === 'local' ? 'Running on the built-in solver' : `${res.meta.solver} · ${res.meta.wall_ms} ms`}
        </span>
        <span className="nav-avatar" aria-hidden="true">
          SA
        </span>
      </div>
    </header>
  )
}
