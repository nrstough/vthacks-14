# 4-minute demo script — the scope contract

This is the contract, not a summary. **If the script does not need it, it does not get built
this weekend.** The feature list in "What must exist" is complete; anything absent from it is
out of scope until the Sat 18:30 gate passes.

Written for a recorded Devpost video. Live-pitch variant noted at the end.

Spoken text is ~550 words, which lands near 3:40 at a natural pace and leaves room to breathe.
Read it out loud with a timer before recording. If a section runs long, cut from the close,
never from the proof.

---

## The one sentence everything serves

> Every other tool tells you that you're going to overdraft.
> This one tells you the fewest things to change so you don't — and proves there's no
> smaller answer.

If a feature does not make that sentence more convincing in four minutes, it is not on the
critical path.

---

## 0:00 – 0:25 · The problem

**Screen:** the app, already open, one account loaded. Nothing clicked yet.

> Two weeks ago my checking account was going to go negative on a Tuesday, and I knew it. What
> I didn't know was what to do about it. Budgeting apps showed me a forecast dipping below
> zero and left the rest to me. Which bill do I move? How many? Is there a smaller answer than
> the one I guessed?
>
> So I built the tool that answers that question.

*Why this opening: it names a person with a problem before it names a technology. It also sets
up the differentiator — forecast versus prescription — in the first fifteen seconds, which is
all the attention a four-minute video reliably gets.*

## 0:25 – 0:50 · Connect the account

**Screen:** click **Connect account**. Transactions populate. Then click **Use sample account**
to show both paths exist.

> This is a real transaction history — pulled live from Capital One's Nessie API, a sandbox
> bank. Weekly payroll, rent, a phone bill, car insurance, and the usual mess of card charges
> with names like "SQ *COFFEE 4471."
>
> It finds the recurring charges on its own, and everything it finds, you can correct.

*The sample-account button exists because judges will not upload a file and may not wait for a
network call. Click Connect first, sample second.*

## 0:50 – 1:35 · The answer

**Screen:** the verdict sentence lands first, large. Then the chart draws.

> Here's the answer. **Move two charges, and you stay above zero through October 3rd** — your
> next payday.
>
> The red line is what happens if you change nothing. It crosses zero on the 24th, three days
> before you get paid. The blue line is the same account with two changes applied. It never
> crosses.
>
> Two changes. Not a budget, not a category breakdown, not thirty percent less on dining out.
> Two dated actions: move the phone bill from the 14th to the 28th, and move the car insurance
> payment back four days.

*Chart spec: red fill only below zero, paydays as axis ticks, a visible step on the with-plan
line at each change date so the cause of the change is legible without a legend.*

## 1:35 – 2:30 · The proof — this is the demo

**Screen:** the certificate line, directly under the prescription list.

> Now, the part I actually care about.
>
> Lots of tools could suggest two changes. The question is whether two is the *smallest*
> answer — or whether it just happens to be what a greedy rule spat out.
>
> **Remove either one of these, and you're forty-one dollars short on the 24th.**
>
> That's not a claim, it's a certificate. The solver checks every smaller combination and
> reports back that none of them clear zero. When it says two, there is no one.

*This is the punchline of the entire submission. Slow down. Let the certificate sit on screen
for a beat before moving on. If anything runs long, it is cut from somewhere else.*

## 2:30 – 3:05 · Make it yours

**Screen:** toggle the lock on the phone bill. The plan re-solves live.

> The plan is yours to argue with. Say the phone bill genuinely can't move.
>
> Lock it, and it re-solves — now it's three changes instead of two, because it lost the most
> efficient one. And it tells you that: locking this cost you one extra change.

*This is what proves the thing is live rather than a slide deck, and it is the second-best
moment in the demo. Protect it above everything except the certificate.*

## 3:05 – 3:30 · When the answer is no

**Screen:** switch to the tier-3 scenario.

> And sometimes there is no answer, which most tools won't tell you.
>
> On this account, no combination of available changes is enough. So it says so: **you need
> one hundred twenty dollars by September 24th.** A number and a date, instead of a
> rearrangement that was never going to work.

*Tier 3 is the honesty beat. It is also the one judges remember, because almost no hackathon
demo shows its own failure case on purpose.*

## 3:30 – 4:00 · Close

> Under the hood it's a constraint solver — integer optimization over dated cash-flow
> constraints — not a language model guessing at your budget. It's stateless: it reads your
> transactions, solves, renders, and forgets. No account, no database, nothing stored.
>
> It won't tell you you're guaranteed to be fine. It tells you this plan is sufficient under
> the schedule it just showed you, and it shows its work.

---

## What must exist for this script to run

This list is the whole build. Nothing else ships before the Sat 18:30 gate.

1. **Two data entry points** — a Nessie "Connect account" path and a one-click sample account.
   The sample must work with the network unplugged.
2. **`/solve` returning:** verdict sentence, tier (1/2/3), daily balance series before and
   after, the change list, and the certificate string.
3. **Three bands** — verdict sentence (~40px), before/after chart, prescription list.
4. **Lock toggle → re-solve**, including the "locking this cost you one extra change" line.
5. **Tier 3 output** — "$X by date Y."
6. **Recurring detection** with a manual override, or hard-coded fixture streams if the 1-hour
   timebox blows.

Explicitly **not** built: auth, multi-account, mobile layout, dark mode, a general constraint
editor, any database, category analytics, and any LLM inside the feasibility decision.

## Cut list, in order, if behind

1. **Live Nessie connect** → pre-seeded sample only. Say "seeded from Nessie" instead of
   clicking it. Costs the least; the Capital One integration still exists in the code and the
   submission.
2. **Lock / re-solve** → static prescription list. Cut 2:30–3:05 entirely.
3. **Tier 3 screen** → describe it in one spoken line over the tier-1 screen.

Never cut the certificate. It is the only thing here nobody else will have.

## Things to never say

- **"Guaranteed."** Always "sufficient under the schedule shown." The moment a judge finds one
  jitter case that breaks a guarantee, the whole proof story dies.
- **"Predicts"** or **"forecasts."** It prescribes. That is the entire differentiator.
- **"AI-powered."** It's a solver, and saying so is *stronger* in a room full of LLM wrappers.
  Say "constraint solver" and let it land.
- Anything implying real bank data. Sandbox and synthetic only.
- **Do not demo a live-updating Nessie balance.** Nessie never moves an account's balance and
  truncates cents; the local ledger is the system of record. See `docs/nessie-notes.md`.

## Live-pitch variant

If judging is in person rather than recorded, cut the 0:00–0:25 opening to one sentence — they
can see the screen and will interrupt — and move the certificate to roughly 1:30. Expect the
first question to be "how do you know it's minimal?" That is the certificate, so have the
tier-3 screen already open in a second tab to answer the follow-up, which is always "what if
it can't be fixed?"
