import type { SolveResponse } from '../types'
import type { Tab } from '../lib/tabs.ts'
import { TABS, label, showsAlarmDot } from '../lib/tabs.ts'

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
 * the Ask tab is a place a person can be standing when the wifi dies — the
 * explainer will say it is unreachable at the same moment, and the two must
 * not contradict each other.
 *
 * Which pills exist, what they are called and which one carries the alarm dot
 * all come from `lib/tabs.ts`, so the rules are testable without a DOM. This
 * renders whatever it returns.
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
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={tab === t ? 'on' : ''}
            aria-current={tab === t ? 'page' : undefined}
            onClick={() => onTab(t)}
          >
            {label(t)}
            {/* One dot, spent on the one state that is an alarm: a gap no
                combination of changes closes. It sits on the plan pill,
                because that is the tab whose verdict is off screen when the
                reader is somewhere else. */}
            {showsAlarmDot(t, res.tier) && (
              <span className="dot" title="Outside cash is needed" />
            )}
          </button>
        ))}
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
