import { Component, type ErrorInfo, type ReactNode } from 'react'
import { crashDetail } from '../lib/crash'

// The one thing standing between a render throw and a white screen. There is
// no router and no other boundary in this app, so an exception anywhere in the
// tree unmounts everything and leaves an empty <div id="root">, with nothing on
// screen to say why. That is the worst possible failure in front of a judge:
// indistinguishable from the app simply not working.
//
// Deliberately not a retry. Whatever state produced the throw is still in
// memory, so re-rendering the same tree usually throws again; a reload is the
// honest offer.

interface Props {
  children: ReactNode
  /**
   * An inline fallback, for a boundary wrapping part of the page rather than
   * all of it.
   *
   * A root-only boundary turns any failure anywhere into a blank page with a
   * crash card — including a failure in a lazily-loaded corner the user was not
   * even looking at. Wrapping that corner in its own boundary with a small
   * fallback keeps the rest of the screen working, which matters most for the
   * planning demo: a wallet chunk that fails to load must not take it down.
   *
   * Omitted, the boundary behaves exactly as before: full-page crash card.
   */
  inline?: (detail: string) => ReactNode
}

interface State {
  detail: string | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { detail: null }

  static getDerivedStateFromError(error: unknown): State {
    return { detail: crashDetail(error) }
  }

  componentDidCatch(error: unknown, info: ErrorInfo): void {
    // Kept, because the console is the only record — nothing here reports home.
    console.error('A render failed and was caught by the boundary.', error, info.componentStack)
  }

  render(): ReactNode {
    const { detail } = this.state
    if (detail === null) return this.props.children
    if (this.props.inline !== undefined) return this.props.inline(detail)

    return (
      <main className="shell">
        <section className="crash" role="alert">
          <h1>This page stopped working</h1>
          <p>
            Something in the interface failed to draw. Nothing is stored between sessions, so
            reloading starts it over from the beginning.
          </p>
          <button type="button" onClick={() => window.location.reload()}>
            Reload the page
          </button>
          <details>
            <summary>What went wrong</summary>
            <p className="crash-detail">{detail}</p>
          </details>
        </section>
      </main>
    )
  }
}
