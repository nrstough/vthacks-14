// Where an imported plan's numbers came from, said plainly.
//
// Deliberately thin: every decision lives in `lib/history.ts` as a pure
// function, because nothing in tests/ mounts a component. This file arranges
// what those functions returned.

import type { ImportAccountResponse } from '../types'
import { panelModel, streamLine } from '../lib/history'

export default function ProvenancePanel({
  account,
  excluded,
  onToggle,
}: {
  account: ImportAccountResponse
  excluded: ReadonlySet<string>
  onToggle: (streamId: string) => void
}) {
  const model = panelModel(account, excluded)
  const income = model.streams.filter((s) => s.kind === 'income')
  const outgoing = model.streams.filter((s) => s.kind !== 'income')

  return (
    <section className="band provenance">
      <div className="band-head">
        <h2>What this plan is built from</h2>
      </div>

      <p className="narration">{model.historyLine}</p>
      {model.staleLine && (
        <p className="ctl-note" role="status">
          {model.staleLine}
        </p>
      )}

      <div className="prov-grid">
        <div className="prov-col">
          <h3>Money in</h3>
          {income.length === 0 && <p className="ctl-note">No regular income found in this export.</p>}
          <ul className="prov-rows">
            {income.map((s) => (
              <li key={s.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={!excluded.has(s.id)}
                    onChange={() => onToggle(s.id)}
                    aria-label={`Count ${s.label} in the plan`}
                  />
                  <span>{streamLine(s)}</span>
                </label>
              </li>
            ))}
          </ul>
          {model.paydayLine && <p className="prov-payday num">{model.paydayLine}</p>}
          {model.todayLine && <p className="ctl-note">{model.todayLine}</p>}
          {model.inflowLine && <p className="ctl-note">{model.inflowLine}</p>}
        </div>

        <div className="prov-col">
          <h3>Regular money out</h3>
          {outgoing.length === 0 && <p className="ctl-note">No recurring charges found in this export.</p>}
          <ul className="prov-rows">
            {outgoing.map((s) => (
              <li key={s.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={!excluded.has(s.id)}
                    onChange={() => onToggle(s.id)}
                    aria-label={`Count ${s.label} in the plan`}
                  />
                  <span>{streamLine(s)}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="prov-assumed">{model.assumedLine}</p>
      {model.truncatedLine && <p className="ctl-note">{model.truncatedLine}</p>}
      <p className="ctl-note">
        Merchant names are used on the server to group these rows and are not stored, not logged and
        not sent back — the labels above are all that leaves. Unticking a row removes it from the plan
        and clears any “Can’t do this” choices.
      </p>
    </section>
  )
}
