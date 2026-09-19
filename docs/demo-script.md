# Four-minute demo script

Offline judging, Sunday morning. Solo. Judges walk up, you talk, they probe.

The timings below are the target. Practise once with a stopwatch; the usual
failure is spending ninety seconds on the problem statement and rushing the
proof, which is the only part nobody else has.

---

## Before they arrive

- [ ] Backend running, frontend running, browser on the app at the $200.00 preset
- [ ] Zoom the page so the verdict sentence is readable from a step back
- [ ] A second tab on the repo, in case someone asks to see the solver
- [ ] Sliders at their defaults, no overrides left over from the last run
- [ ] If the wifi is dead, say nothing about it. The page falls back to a local
      solver and keeps working. Only mention it if the footer chip is spotted.
- [ ] Refresh the two numbers in the build section. They were 810 tests and
      under 3ms on Saturday morning and the suite is still growing; quoting a
      stale figure to someone who then runs it is worse than rounding. As of
      Sat 03:40 it is 977 backend tests plus 59 frontend tests.

---

## 0:00 to 0:25 — the gap

> "Every banking app I have will warn me that I'm about to overdraft. Not one
> of them will tell me what to do about it.
>
> This one does. Give it your transactions and it returns the smallest set of
> changes that keeps you above zero until payday, and it proves that nothing
> smaller works."

Say "smallest" deliberately. It is the whole claim and the rest of the demo is
evidence for it.

## 0:25 to 1:10 — the answer

**[Point at the verdict sentence.]**

> "Two hundred dollars, two weeks to payday. Do nothing and this account goes
> a hundred and twenty dollars under on the twenty-fourth.
>
> Three changes fix it. Skip one delivery order, cancel the gym, pay the card
> minimum instead of the full statement."

**[Point at the chart.]**

> "Dashed line is doing nothing, and the red is the overdraft. Solid line is
> the plan. The dots are the days you actually have to do something, because a
> plan you can't act on in time isn't a plan."

## 1:10 to 1:45 — the proof

This is the part that is not a wrapper around an API. Slow down.

**[Point at the box under the verdict.]**

> "Here's what I think makes this different. It doesn't just say three changes.
> It says every one of them is load-bearing. Remove any single one and you go
> under on the twenty-fourth by as much as fifty-three dollars.
>
> That's checked against a zero balance, not against the cushion, and it's
> re-verified after the plan is chosen. So it's not the solver marking its own
> homework."

## 1:45 to 2:20 — make it re-solve

Hand this one to the judge if they seem willing. It lands better when they
press the button.

> "The obvious objection is that I picked an example. So change it. Say you
> don't want to carry a balance on that card. You want to pay it in full."

**[Tick "Can't do this" on the "Pay the card minimum" row.]**

> "Same account, and now it needs seven changes instead of three, because that
> eighty dollars was doing a lot of work. Nothing here is a stored answer.
>
> Notice the proof changed too. It no longer says every change is
> load-bearing, because now some of them are only protecting the cushion. It
> tells you which."

**Verified on the live app** (Sat 03:35, against both the API and the built-in
solver). Three to seven. Do not use the gym row for this: ruling the gym out
only moves it to four, which is a weaker moment. Reset with any preset button,
which clears overrides.

Every row carries the same checkbox, in the plan and in the left-out list, and
none of them start ticked. If a judge asks what it does: it is the only thing
the app asks of you, and the solver re-runs without that change. The card row
then moves down to the left-out list and says you ruled it out.

One caveat if a judge reads the proof box closely here. It names the gas
deferral and then says "the rest hold the cushion", but three of the seven are
load-bearing, and the rows themselves say so correctly. The sentence is the
solver's, shared with the backend, and is logged for the backend lane. If it is
still there on Sunday, say "three of these are load-bearing and the rows tell
you which" and move on.

## 2:20 to 2:55 — when cutting isn't enough

**[Click the $60.00 preset.]**

> "Now the case I care most about. Sixty dollars, same bills.
>
> There is no set of changes that fixes this. Every other tool I looked at
> either keeps suggesting things or just shows you a red number. This one says:
> you need twenty-seven dollars and sixty-two cents more, by the twenty-fourth,
> and here is the best partial plan in the meantime.
>
> It never uses the word infeasible, and it never tells you you're fine when
> you aren't. If it can't solve your problem it says so and tells you the size
> of the hole."

That paragraph is the impact answer. Do not cut it for time.

## 2:55 to 3:35 — how it's built

> "Underneath it's a constraint solver. Integer cents, one covering constraint
> per day, and a lexicographic objective, so fewest changes genuinely wins
> before anything softer like how annoying each change is.
>
> The hard part was trusting it. So there are two independent implementations,
> a brute force and the constraint model, and they're checked against each
> other on generated accounts. Two hundred instances, zero disagreements.
> Eight hundred and ten tests. Solves in under three milliseconds."

If they want one more level:

> "Brute force is exact but dies at eighteen candidate changes, three seconds.
> That's why the constraint model is the default, not a flourish."

## 3:35 to 4:00 — close

> "It's stateless. No account, no database, nothing stored. Sandbox data only.
>
> What I'd do next is the part I deliberately didn't fake: error bars. Right
> now it's exact about a schedule it's told. I want it to say how late your
> paycheck can be before the plan stops working."

Stop there. Do not trail off into a feature list.

---

## Optional beat, only if the bank integration is live

Insert at 1:10, and cut fifteen seconds from the build section to pay for it.

> "This isn't a file I uploaded. It's pulling a real account from Capital One's
> sandbox over their API."

If it is not live on Sunday, say nothing about it at all. Do not apologise for
missing features; judges only know what you tell them.

---

## Two-minute version, if they cut you off

Problem, the three-change answer, the proof box, the sixty-dollar case, one
line on the constraint solver and the two implementations agreeing. Drop the
re-solve and the close.

---

## Likely questions, and short answers

**"Couldn't a greedy algorithm do this?"**
Usually, yes, and that's an honest finding. A date-aware greedy gets the same
answer most of the time. What it can't do is prove nothing smaller works, or
tell you the size of the gap when nothing works at all. The proof is the
product, not the plan.

**"How do you know the solver is right?"**
Two independent implementations checked against each other on generated
accounts, plus property tests that don't reference either one, like: total
cash freed can never exceed the transactions it came from.

**"What if the same charge could be changed two ways?"**
At most one change per transaction, enforced in the model. Without that the
solver will free more money than the charge is worth and quietly understate
what you need. That was a real bug here, caught before it shipped.

**"Is this financial advice?"**
No, and it's careful not to sound like it. It says "sufficient under the
schedule shown", never "guaranteed", because the schedule can change.

**"Why should I trust the numbers if my paycheck moves?"**
You shouldn't yet, and that's the next thing to build. Today it's exact about
the schedule it's given. What it won't do is pretend to a confidence it
doesn't have.

**"What's the disruption score?"**
An input, not a learned thing. Right now I set it per category. A real version
asks you once, and it only ever breaks ties between plans that are already the
same size.

**"Who is this for?"**
Someone a bad week away from a thirty-five dollar fee on a five dollar
shortfall. Overdraft fees are regressive; they fall hardest on the people with
the least slack. That's the whole reason it's prescriptive instead of another
dashboard.
