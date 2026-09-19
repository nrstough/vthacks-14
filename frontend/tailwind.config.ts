import type { Config } from 'tailwindcss'

// src/index.css is the source of truth. This file mirrors it so that anything
// generated from the Tailwind theme lands on the same values the hand-written
// sheet already uses.
//
// An earlier generation of this config carried a different design system
// entirely — a warm red-to-peach brand ramp, an 18/24/32px radius scale, and
// font stacks keyed to families that were never defined anywhere. Two
// disagreeing palettes in one app is how a demo ends up with two shades of
// "the accent". These are the real ones.
//
// Note there are no `@tailwind` directives in index.css, so nothing is emitted
// today; the config is kept in step for whenever that changes.
const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        panel: 'var(--panel)',
        'panel-2': 'var(--panel-2)',
        line: 'var(--line)',
        'line-strong': 'var(--line-strong)',
        ink: {
          DEFAULT: 'var(--ink)',
          2: 'var(--ink-2)',
          3: 'var(--ink-3)',
          dim: 'var(--ink-dim)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          ink: 'var(--accent-ink)',
          press: 'var(--accent-press)',
          wash: 'var(--accent-wash)',
          soft: 'var(--accent-soft)',
        },
        neg: { DEFAULT: 'var(--neg)', wash: 'var(--neg-wash)' },
        warn: { DEFAULT: 'var(--warn)', wash: 'var(--warn-wash)' },
        good: { DEFAULT: 'var(--good)', wash: 'var(--good-wash)' },
        canvas: 'var(--canvas)',
      },
      spacing: {
        s1: 'var(--s1)',
        s2: 'var(--s2)',
        s3: 'var(--s3)',
        s4: 'var(--s4)',
        s5: 'var(--s5)',
        s6: 'var(--s6)',
      },
      borderRadius: {
        // 4xl / 3xl / 2xl from the original config, which is where this scale
        // came from in the first place.
        '4xl': 'var(--radius-lg)',
        '3xl': 'var(--radius)',
        '2xl': 'var(--radius-sm)',
        DEFAULT: 'var(--radius)',
        xs: 'var(--radius-xs)',
        pill: 'var(--radius-pill)',
      },
      // The three families self-hosted under public/fonts, in the same order
      // the stylesheet's --sans / --display / --mono declare them.
      fontFamily: {
        // Body copy: every sentence a person reads.
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Helvetica', 'Arial', 'sans-serif'],
        // Headings and the wordmark. Georgia is the fallback because it is the
        // nearest Baskerville every machine already has.
        display: ['Libre Baskerville', 'Georgia', 'Times New Roman', 'serif'],
        // Eyebrows, labels, chips and every figure.
        numbers: ['JetBrains Mono', 'ui-monospace', 'SF Mono', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        'card-hover': 'var(--shadow-card-hover)',
        glass: 'var(--shadow-glass)',
        popover: 'var(--shadow-popover)',
      },
      transitionTimingFunction: {
        ease: 'var(--ease)',
      },
    },
  },
  plugins: [],
}
export default config
