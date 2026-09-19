![VeriLM]([IMG])

September 18, 2026

> I am competing solo in a 36-hour hackathon (VTHacks 14, Sept 18-20, 2026).
> Build window is Friday 8:00 PM to Sunday 8:00 AM, with the last two hours
> reserved for submission. I want deep research and a strong opinionated
> recommendation.
> ABOUT ME
> 19, first-year engineering student. I direct AI coding agents (Claude Code,
> Codex) rather than writing most code by hand, so implementation throughput is
> high, but my personal fluency in Python tooling is limited and I will struggle
> with deep undocumented debugging. I have shipped one iOS computer-vision app.
> No prior experience with Solana, Presage, TigerData, MongoDB Atlas or Vultr.
> Judging criteria, in the organizers' words: technical execution including
> "difficulty of the implementation and the team's original contribution,"
> innovation and creativity, impact and usefulness, presentation and
> completeness. Four minutes to present, offline judging Sunday morning. I am
> also targeting Best UI/UX.
> Confirmed sponsors with prize tracks: Capital One, Deloitte, Databricks,
> Peraton, Galois, CoStar Group, GoDaddy, nebulaONE by Cloudforce, Impiricus,
> Procedura AI. Every challenge statement except GoDaddy's is unpublished until
> the opening ceremony Friday 7:00 PM. MLH tracks that ARE published include
> TigerData (TimescaleDB) and Vultr (cloud hosting).
> THE PROBLEM I HAVE BEEN PLANNING
> Given a person's bank transaction history, tell them the smallest set of
> spending changes that keeps their balance above zero every day until their
> next payday.
> Not a forecast. A prescription, with some claim to being the right one:
> cancel these, cut that, and here is why this set is sufficient.
> One wrinkle I think matters, though challenge it: timing. Cancelling something
> that bills on the 28th does not help if you go negative on the 20th. So money
> freed has a date attached, not just an amount.
> Rough scale: 30 to 60 day horizon, on the order of 20 to 40 things a person
> could plausibly change.
> QUESTION ZERO, AND IT MAY BE THE MOST IMPORTANT
> I am no longer sure this problem is ambitious enough. "Do not overdraft before
> Friday" is a hundred-dollar problem and it feels small. Tell me honestly
> whether you agree, and if so, what a better problem is that keeps the same
> technical core (optimization over personal financial data) but raises the
> stakes. Candidates I have considered: optimal debt payoff allocation across
> multiple debts with different rates and due dates; credit building for a thin
> file; handling genuinely uncertain income rather than assuming it is known.
> Rank these and propose your own. Also tell me if you think I am wrong and the
> original problem is fine.
> Related: who exactly is the user? I have been assuming someone like me,
> irregular income, thin margin, no savings buffer. Is that the right user, is
> it a real need, and what would a skeptical judge say about it?
> WHAT I WANT YOU TO FIGURE OUT
> 1. WHAT IS THE RIGHT APPROACH AT ALL? I have been assuming exact optimization
> (mixed integer programming or constraint programming). Seriously evaluate the
> alternatives: learned models, transformers, sequence models, RL, LLM-driven
> reasoning, greedy heuristics, hybrids. If a neural approach is viable here,
> say so and tell me how you would do it. If it is not, explain precisely why,
> in terms of what the model could and could not guarantee. Do not assume I have
> decided. I want the honest technical argument whichever way it goes.
> 2. Whatever you recommend, give me the actual formulation or architecture.
> Concrete enough to implement. Variables, constraints, objective, or layers and
> training approach. Show the traps and the off-by-one errors.
> 3. What happens when there is no solution? I want the best partial answer
> rather than an error. How is that handled properly?
> 4. How do I get an answer that is stable and explainable? If a tiny change to
> the input flips the entire recommendation, that is bad for a user and bad for a
> demo. What causes that and how is it addressed?
> 5. RECURRING CHARGE DETECTION. Finding recurring transactions and normalizing
> messy merchant strings. What are the real approaches, what libraries exist,
> what is the cheap version that gets most of the value, and what does it miss?
> 6. DATA. I have already found the following and confirmed they exist. Start
> from these, verify them, and go further.
> - Kaggle "Financial Transactions Dataset: Analytics" (computingvictor),
> built by CaixaBank Tech for their 2024 AI Hackathon, Apache 2.0. Contains
> transactions_data.csv (amounts, timestamps, merchant details, transaction
> types, 2010s), users_data (demographics, account details), cards_data.csv
> (card type, credit limit, activation date), mcc_codes.json.
> - Capital One Nessie sandbox API (api.nessieisreal.com), confirmed live as
> of Sept 2026. A sandbox you populate, not a dataset.
> - Plaid sandbox.
> - Berka / PKDD 1999 Czech bank dataset, real anonymized transactions with
> account balances. Not verified as still hosted.
> a. Is the CaixaBank set usable for MY problem? It is card transaction data,
> not a checking account with a running balance. How hard is it to derive a
> usable daily balance series, and what must I assume or fabricate?
> b. Does users_data contain income, pay frequency or paydays? My model
> depends on knowing when money arrives. If not, what do I do?
> c. Is there anything BETTER that I have missed? I want dated transactions,
> per person, with merchant identity, ideally a balance or income stream.
> Search academic repositories, open banking initiatives, government
> releases and competition archives, not just Kaggle.
> d. Do any public datasets label recurring charges or subscriptions? If none
> do, say so plainly.
> e. If I generate synthetic data instead, what makes it convincing rather
> than obviously fake, and is there an existing generator worth using?
> 7. STORAGE. Is a database needed here at all, or can this run stateless from an
> uploaded file? Separately, TigerData / TimescaleDB is a sponsor prize track.
> Realistically, what would it take to use it meaningfully, and is there a
> version where it genuinely improves the product rather than being decoration?
> 8. UI AND UX.
> - Strongest single-screen design for showing a before state, an after state,
> and a short list of prescribed changes?
> - How do you visually communicate that an answer is guaranteed or proven
> rather than a guess? Is that even possible to convey visually?
> - What charting approach and library for a daily balance line over 30 to 60
> days, that reads as polished and builds fast?
> - What actually wins Best UI/UX at hackathons? What do judges respond to in
> four minutes, and what reads as unfinished?
> - Cheapest things that make an interface look considered. Be specific: type,
> spacing, motion, color, empty states, loading states.
> - Should the user manipulate constraints live, for example saying groceries
> matter more than streaming? Worth the build time or a distraction?
> 9. STACK AND DEPLOY. Fastest reliable path from nothing to a deployed working
> app on a single Linux VM (Vultr, also a prize track). Backend, frontend,
> deployment. Optimize for "works on the first attempt" over elegance.
> 10. PRIOR ART. What has been built here, on Devpost and elsewhere?
> Prescriptive personal finance rather than forecasting or subscription listing.
> What won, what failed, where is the unoccupied ground? How is this different
> from Rocket Money, Copilot, Monarch, YNAB, and what would a judge who knows
> those products ask me?
> THE PRIZE LIST, AND WHAT I SHOULD ENTER
> 29 non-cash prizes. Devpost's requirements say "Select every prize category you
> want to enter," so entering is a checkbox at submission and multiple entries
> from one project are free. Full list as published:
> VTHacks' own tracks
> - 1st Place: MacBook Pro 14-inch, per team member
> - 2nd Place: PlayStation 5 Digital Edition
> - 3rd Place: keyboard, mouse and monitor setup
> - Best First-Time Hack: AirPods 4
> - Best UI/UX Hack: Kodak Polaroid camera
> - Best Ut Prosim Hack: North Face Borealis backpack ("Ut Prosim" is Virginia
> Tech's motto, "That I May Serve")
> - Best DEI Hack: LED Smart Fire TV
> - Best Hack That Didn't Work: Amazon Echo Spot
> - Raffle, 2 winners: AirPods 4 and a 13-inch MacBook Air
> Sponsor tracks, all "Details TBD" until the Friday opening ceremony except
> GoDaddy: Impiricus, Peraton, Capital One, CoStar Group, Galois, Deloitte,
> Databricks, nebulaONE by Cloudforce, Procedura AI.
> - GoDaddy Sponsor Track 1st: Meta smart glasses. 2nd: headphones.
> 3rd: attachable monitors.
> MLH tracks, requirements published
> - Best Use of Gemini API: Google swag kits
> - Best Use of ElevenLabs: wireless earbuds
> - Best Use of Solana: Ledger Nano S Plus
> - Best Use of Tiger Data: Stream Deck Mini
> - Best Use of Presage: Fitbit Inspire plus Presage credits
> - Best Use of Vultr: portable screens
> - Best Use of MongoDB Atlas: M5Stack IoT Kit
> - Best Domain Name from GoDaddy Registry: digital gift card
> What I want from you:
> a. Explain what each track is actually looking for, especially the ones whose
> names do not make it obvious (Ut Prosim, DEI, Best Hack That Didn't Work,
> Best Domain Name).
> b. Which should I enter, given my project? Rank by realistic probability of
> winning, and be honest about the ones I have no shot at.
> c. Which are worth CHANGING THE BUILD for, and how much build time is each
> worth? Distinguish tracks I qualify for anyway from tracks that require real
> extra work, and tell me which of the latter actually pay off.
> d. Going solo against teams of up to four, which tracks does being solo help
> in and which does it hurt in?
> e. For the nine sponsor tracks still unannounced, what are these companies
> likely to ask for, based on what each does and what they have sponsored at
> past hackathons? Capital One ran a "Consumer Financial Autonomy and Credit
> Building" track at HackMTY 2026, which is the kind of concrete signal I
> want. I need a decision rule for the ceremony, not just a ranking.
> MY POSITION ON TRADEOFFS
> - The core is decided and I will not destabilize it. I will add scoped
> integrations at the edges (hosting on Vultr, a domain, possibly TigerData as
> the datastore) because I need hosting and storage anyway. I will not bolt on
> Solana or a voice API to chase a track. Low risk tolerance on anything
> touching the solver, high willingness on infrastructure choices.
> - I am a genuine first-time hacker, so Best First-Time Hack is my best odds and
> I want it prioritized. Best UI/UX is second. Beyond that I want the cheap
> entries identified. Rank by expected value, but tell me separately which
> single track I should optimize hardest for.
> - No institutional connection to Virginia Tech. The project's user is people
> living on a thin margin with no savings buffer, which includes me. If that
> counts as a service framing it is a genuine one. I will not manufacture a
> DEI angle.
> CONSTRAINTS
> - 36 hours, solo, confirmed and fixed. Minus two hours for submission and about
> six for sleep, so roughly 28 working hours. Nothing that assumes a team or a
> week.
> - No pre-existing code. Libraries and open source fine with disclosure.
> - Research and planning before the event are allowed.
> OUTPUT
> 1. Your answer to Question Zero first, before anything else.
> 2. Your recommendation for each numbered question, with reasoning, and say
> plainly where you are uncertain.
> 3. The formulation or architecture written out concretely.
> 4. An hour-by-hour build order with explicit kill criteria: what gets cut, and
> at what time, if I fall behind.
> 5. The three highest-risk assumptions in the whole plan.
> 6. A ranked list of exactly which prize categories I should tick on the
> submission form, and which two or three are worth altering the build for.
> 7. FINALLY: what interesting layers of complexity or depth would YOU add to
> this project? Not what I have described. Things I have not thought of that
> would make it more technically impressive, more genuinely useful, or more
> memorable in a four-minute demo. Rank them by value per hour of work.

## Executive summary

## Scope

Solo 36-hour hackathon (VTHacks 14) strategy and technical design for a prescriptive personal-finance tool that computes the minimal, date-aware set of spending changes keeping daily balance above zero until next payday. Covers problem framing (Question Zero), solver-vs-ML approach, concrete formulation, infeasibility and stability handling, recurring-charge detection, data sourcing, storage/TigerData, UI/UX, stack/deploy, prior art, prize-track strategy, hour-by-hour plan, and risk. Excludes production code.

## Conclusion

Keep the timed overdraft-prevention core — all three experts reject all three pivots (debt payoff reduces to a sort; thin-file credit optimizes an uncomputable score; full uncertain-income optimization destroys the deterministic proof). The stakes are already real: median 3-day overdraft episodes imply an 8,273% APR and \$5.83B in 2023 bank revenue. Change the objective, not the problem: minimize priced consequences (fees, shortfall) lexicographically before cardinality, so infeasibility becomes an expensive answer rather than an error. Use an exact solver over integer cents with slack variables; synthetic data as primary; stateless FastAPI + Recharts on one Vultr VM. Optimize hardest for Best First-Time Hack.

<span class="confidence-label">Confidence:</span>
<span class="confidence-value">Medium</span>

All three experts independently converged on keeping the core problem, rejecting the three pivots, using exact optimization over learned models, absorbing infeasibility with slack variables, favoring synthetic demo data, and prioritizing Best First-Time Hack. Claude substantiated the formulation with executed dual-solver verification and measured instability (21% plan-flip rate naive vs 1% mitigated). Gemini's formulation diverged — it omits cardinality minimization and therefore cannot support the "smallest set" claim; this is an identified modeling gap, not an unresolved dispute. Confidence is capped because nine sponsor tracks are genuinely unknown and several dataset-schema findings remain uncorroborated.

### Sensitivities

- <span class="markdown-body md-compact"></span>

  Capital One's revealed challenge theme swings the primary track choice; if consumer-finance themed it becomes worth up to 4 hours, and if unrelated it is a free checkbox with zero build.

- <span class="markdown-body md-compact"></span>

  The pay schedule will be partly fabricated in every data scenario examined, and a judge inspecting the repository could undercut the "provably sufficient" claim unless synthetic elements are labeled on screen.

- <span class="markdown-body md-compact"></span>

  TigerData's 3-hour investment only pays off if ingestion is live by Saturday 14:00; past that it competes directly with the polish pass that wins First-Time and UI/UX.

- <span class="markdown-body md-compact"></span>

  The recurring detector's occurrence threshold has no good setting, so demo quality depends on the manual override toggle and one curated account rather than on detector accuracy.

Final Verified Code
<span class="artifact-lines">(272 lines)</span>

<span class="markdown-body md-compact"></span>

Claude's analysis code builds a 30-day demo ledger, solves the minimal-prescription problem two independent exact ways — brute-force lexicographic enumeration over all subsets and a dependency-free pseudo-polynomial DP over cumulative-freed-cash state — and confirms they agree, which validates the DP as a solver-install fallback. It then quantifies date-blind versus date-aware greedy suboptimality over 398 random solvable instances, measures plan instability across an 81-point <span class="math inline">$`B_0`$</span> sweep under naive versus mitigated configurations, emits the irredundancy certificate, and produces the before/after balance figure usable directly as the UI reference.

Show code

``` artifact-content

import numpy as np, itertools, math, json, random
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------
# 1. DEMO SCENARIO  (T=30 days, day 0 = "today")
# ---------------------------------------------------------------
T = 30
income   = {12: 1120.00, 26: 1120.00}
fixed    = {8:140.00, 14:900.00, 20:65.00, 22:95.00, 5:40.00, 19:40.00}
for d in range(2, 30, 4):            # groceries every 4 days
    fixed[d] = fixed.get(d,0)+34.00

# candidate changeable items: (name, amount, day, pain 1-3)
items = [
 ("Cloud storage",     9.99,  3, 1),
 ("Coffee habit",     28.00,  4, 2),
 ("Streaming B",      22.99,  6, 1),
 ("Dining out #1",    62.00,  7, 2),
 ("Music sub",        11.99,  9, 1),
 ("Meal kit",         78.50, 10, 2),
 ("Rideshare budget", 35.00, 11, 2),
 ("News sub",          8.00, 16, 1),
 ("Dining out #2",    48.00, 17, 2),
 ("Software sub",     20.00, 19, 1),
 ("Streaming A",      15.99, 21, 1),
 ("Gaming sub",       17.99, 24, 1),
 ("Annual sub",       99.00, 25, 1),
 ("Gym",              49.00, 27, 3),
]
n = len(items)

def do_nothing_balance(B0):
    B, out = B0, []
    for t in range(T+1):
        B += income.get(t,0.0) - fixed.get(t,0.0)
        B -= sum(a for _,a,d,_ in items if d==t)
        out.append(round(B,2))
    return np.array(out)

# tune B0 so the trough is ~ -130 and it happens BEFORE first payday
B0 = 0.0
base = do_nothing_balance(B0)
B0 = round(-130.0 - base.min(), 2)
base = do_nothing_balance(B0)
trough_day = int(np.argmin(base))
print("B0 =", B0, "| trough", base.min(), "on day", trough_day)
print("min balance before first payday (day 12):", base[:12].min(), "at day", int(np.argmin(base[:12])))

# deficit profile D_t (cents), beta = safety buffer
def deficits(B0, beta=0.0, round_to=0.0):
    b = do_nothing_balance(B0)
    D = np.maximum(0.0, beta - b)
    if round_to>0: D = np.ceil(D/round_to)*round_to
    return (D*100).round().astype(int)

D0 = deficits(B0)
print("days with deficit:", [(t,D0[t]/100) for t in range(T+1) if D0[t]>0][:8], "...")
print("max deficit $", D0.max()/100)

# ---------------------------------------------------------------
# 2. EXACT SOLVERS: brute force (lexicographic) and pseudo-poly DP
# ---------------------------------------------------------------
cents = [int(round(a*100)) for _,a,_,_ in items]
days  = [d for _,_,d,_ in items]

def feasible(S, D):
    for t in range(T+1):
        if D[t] > 0:
            if sum(cents[i] for i in S if days[i] <= t) < D[t]: return False
    return True

def solve_bruteforce(D, prev=frozenset(), hysteresis=False):
    best, bestkey = None, None
    for r in range(0, n+1):
        found = False
        for S in itertools.combinations(range(n), r):
            Sf = frozenset(S)
            if not feasible(Sf, D): continue
            found = True
            ov = len(Sf & prev) if hysteresis else 0
            key = (r, -ov, sum(cents[i] for i in S), S)
            if bestkey is None or key < bestkey: bestkey, best = key, Sf
        if found: break          # minimal cardinality found -> stop
    return best

BIG = 10**7
def solve_dp(D):
    """exact min (count, dollars) via pseudo-poly DP over freed-amount state"""
    cap = int(D.max())
    if cap == 0: return frozenset()
    INF = float('inf')
    dp = [INF]*(cap+1); dp[0]=0.0; par=[None]*(cap+1)
    by_day = {}
    for i in range(n): by_day.setdefault(days[i],[]).append(i)
    for t in range(T+1):
        for i in by_day.get(t,[]):
            nd = dp[:]; npar = par[:]
            for f in range(cap+1):
                if dp[f]==INF: continue
                nf = min(cap, f+cents[i]); c = dp[f]+BIG+cents[i]
                if c < nd[nf]: nd[nf]=c; npar[nf]=(f,i)
            dp, par = nd, npar
        if D[t]>0:
            for f in range(int(D[t])): dp[f]=INF
    bf = min(range(cap+1), key=lambda f: dp[f])
    if dp[bf]==INF: return None
    S=set(); f=bf
    while par[f] is not None:
        pf,i = par[f]; S.add(i); f=pf
    return frozenset(S)

sol_bf = solve_bruteforce(D0); sol_dp = solve_dp(D0)
print("\nEXACT (brute force):", sorted(items[i][0] for i in sol_bf),
      "| n=",len(sol_bf), "$", sum(items[i][1] for i in sol_bf))
print("EXACT (DP fallback) :", sorted(items[i][0] for i in sol_dp),
      "| n=",len(sol_dp), "$", sum(items[i][1] for i in sol_dp))
print("DP matches brute force cardinality:", len(sol_bf)==len(sol_dp), "| DP feasible:", feasible(sol_dp,D0))

# irredundancy certificate
def certificate(S, D):
    out=[]
    for i in sorted(S):
        S2 = set(S)-{i}
        worst=None
        for t in range(T+1):
            if D[t]>0:
                slack = sum(cents[j] for j in S2 if days[j]<=t) - D[t]
                if slack<0 and (worst is None or slack<worst[1]): worst=(t,slack)
        out.append((items[i][0], worst))
    return out
print("\nIRREDUNDANCY CERTIFICATE (remove one -> you break on day t by $x):")
for nm,w in certificate(sol_bf,D0): print("   ", nm, "->", None if w is None else f"day {w[0]}, short ${-w[1]/100:.2f}")

# ---------------------------------------------------------------
# 3. GREEDY BASELINES  (the timing thesis, quantified)
# ---------------------------------------------------------------
def greedy_amount_blind(D):
    """user's strawman: cancel biggest things first, ignore dates"""
    order = sorted(range(n), key=lambda i:-cents[i]); S=set()
    for i in order:
        S.add(i)
        if feasible(frozenset(S), D): return frozenset(S)
    return None
def greedy_date_aware(D):
    """sensible heuristic: fix earliest violation with largest eligible item"""
    S=set()
    for _ in range(n):
        viol=None
        for t in range(T+1):
            if D[t]>0 and sum(cents[j] for j in S if days[j]<=t) < D[t]: viol=t; break
        if viol is None: return frozenset(S)
        cand=[i for i in range(n) if i not in S and days[i]<=viol]
        if not cand: return None
        S.add(max(cand, key=lambda i:cents[i]))
    return None

gb, gd = greedy_amount_blind(D0), greedy_date_aware(D0)
print("\nGREEDY (amount, date-blind):", None if gb is None else sorted(items[i][0] for i in gb), "| n=", None if gb is None else len(gb))
print("GREEDY (date-aware)       :", None if gd is None else sorted(items[i][0] for i in gd), "| n=", None if gd is None else len(gd))

# random-instance study
rng = random.Random(7)
res={"blind_fail":0,"blind_extra":[], "da_extra":[], "da_extra_dollars":[], "N":0}
for trial in range(600):
    m = rng.randint(10,14); Tt=30
    A=[rng.choice([8,10,12,15,18,20,25,30,35,45,50,60,75,99]) for _ in range(m)]
    Dd=[rng.randint(1,Tt) for _ in range(m)]
    Dv=np.zeros(Tt+1,dtype=int)
    k=rng.randint(1,3)
    for _ in range(k):
        t=rng.randint(3,Tt); Dv[t:]=np.maximum(Dv[t:], rng.randint(20,160))
    for t in range(1,Tt+1): Dv[t]=max(Dv[t],Dv[t-1])
    globals().update(dict(cents=A,days=Dd,n=m,T=Tt))
    if not feasible(frozenset(range(m)),Dv): continue
    ex=solve_dp(Dv)
    if ex is None: continue
    res["N"]+=1
    b=greedy_amount_blind(Dv); d_=greedy_date_aware(Dv)
    if b is None: res["blind_fail"]+=1
    else: res["blind_extra"].append(len(b)-len(ex))
    if d_ is not None:
        res["da_extra"].append(len(d_)-len(ex))
        res["da_extra_dollars"].append(sum(A[i] for i in d_)-sum(A[i] for i in ex))
globals().update(dict(cents=[int(round(a*100)) for _,a,_,_ in items],
                      days=[d for _,_,d,_ in items], n=len(items), T=30))
print(f"\nRANDOM STUDY over {res['N']} solvable instances:")
print("  date-blind greedy needed MORE items than optimal in "
      f"{100*np.mean(np.array(res['blind_extra'])>0):.1f}% of cases; mean extra items {np.mean(res['blind_extra']):.2f}")
print("  date-aware greedy suboptimal in "
      f"{100*np.mean(np.array(res['da_extra'])>0):.1f}% of cases; mean extra items {np.mean(res['da_extra']):.2f}; mean extra $ cut {np.mean(res['da_extra_dollars']):.1f}")

# ---------------------------------------------------------------
# 4. STABILITY SWEEP: naive vs mitigated
# ---------------------------------------------------------------
sweep = np.arange(B0-40, B0+40.01, 1.0)
def churn(beta, round_to, hyst):
    prev=frozenset(); sols=[]
    for b0 in sweep:
        D = deficits(b0, beta=beta, round_to=round_to)
        S = solve_bruteforce(D, prev=prev, hysteresis=hyst) if D.max()>0 else frozenset()
        sols.append(S); prev=S
    flips = sum(1 for k in range(1,len(sols)) if sols[k]!=sols[k-1])
    jac = np.mean([len(sols[k]&sols[k-1])/max(1,len(sols[k]|sols[k-1])) for k in range(1,len(sols))])
    return flips, jac, sols
f1,j1,s1 = churn(0.0, 0.0, False)
f2,j2,s2 = churn(25.0, 5.0, True)
print(f"\nSTABILITY over {len(sweep)} one-dollar perturbations of B0:")
print(f"  naive      : {f1} plan changes ({100*f1/(len(sweep)-1):.0f}% of steps), mean Jaccard {j1:.3f}")
print(f"  mitigated  : {f2} plan changes ({100*f2/(len(sweep)-1):.0f}% of steps), mean Jaccard {j2:.3f}")
print("  (mitigations: $25 buffer + $5 deficit rounding + overlap-preferring lexicographic tiebreak)")

# ---------------------------------------------------------------
# 5. INFEASIBLE CASE -> tiering + minimum external cash
# ---------------------------------------------------------------
B0_bad = B0 - 260.0
Dbad = deficits(B0_bad)
full = frozenset(range(n))
if feasible(full, Dbad):
    print("\n(infeasible test not triggered)")
else:
    gaps=[(t, (Dbad[t]-sum(cents[i] for i in full if days[i]<=t))/100) for t in range(T+1)
          if Dbad[t]>0 and sum(cents[i] for i in full if days[i]<=t) < Dbad[t]]
    need = max(g for _,g in gaps); by = min(t for t,_ in gaps)
    print(f"\nTIER 3 (structurally impossible) at B0=${B0_bad:.2f}:")
    print(f"  even cancelling ALL {n} items leaves a gap. Minimum external cash = ${need:.2f}, needed by day {by}.")

# ---------------------------------------------------------------
# 6. FIGURES
# ---------------------------------------------------------------
plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
after = do_nothing_balance(B0).copy()
for i in sol_bf:
    after[items[i][2]:] += items[i][1]
fig,ax=plt.subplots(figsize=(10,4.2))
x=np.arange(T+1)
ax.fill_between(x, base, 0, where=base<0, color="#e5484d", alpha=.22, interpolate=True)
ax.plot(x, base, "--", color="#e5484d", lw=2, label="Do nothing")
ax.plot(x, after, "-", color="#1f6feb", lw=2.4, label="With plan")
ax.axhline(0, color="#111", lw=1)
ax.axhline(25, color="#999", lw=.8, ls=":", label="$25 safety buffer")
for d_ in income: ax.axvline(d_, color="#2da44e", lw=.9, alpha=.6)
ax.annotate("payday", (12,ax.get_ylim()[1]*.92), color="#2da44e", fontsize=8)
for i in sol_bf:
    ax.annotate(f"↑ cancel {items[i][0]} (+${items[i][1]:.0f})", (items[i][2], after[items[i][2]]),
                textcoords="offset points", xytext=(4,10), fontsize=8, color="#1f6feb")
ax.plot([trough_day],[base[trough_day]],"o",color="#e5484d")
ax.set_title(f"Binding day = day {int(np.argmin(base[:12]))} · exact plan = {len(sol_bf)} changes · "
             f"date-blind greedy = {'FAILS' if gb is None else len(gb)}", fontsize=11)
ax.set_xlabel("day"); ax.set_ylabel("end-of-day balance ($)"); ax.legend(frameon=False, fontsize=9)
plt.tight_layout(); plt.savefig("fig1_before_after.png", dpi=150)

fig,ax=plt.subplots(figsize=(7,3.6))
ax.bar(["naive\n(β=0, no tiebreak)","mitigated\n(β=$25, $5 rounding,\noverlap tiebreak)"],
       [100*f1/(len(sweep)-1), 100*f2/(len(sweep)-1)], color=["#e5484d","#1f6feb"], width=.55)
ax.set_ylabel("% of $1 perturbations that flip the plan")
ax.set_title("Recommendation instability under ±$40 balance jitter")
for k,v in enumerate([100*f1/(len(sweep)-1), 100*f2/(len(sweep)-1)]):
    ax.text(k, v+1, f"{v:.0f}%", ha="center")
plt.tight_layout(); plt.savefig("fig2_stability.png", dpi=150)

fig,ax=plt.subplots(figsize=(7,3.6))
vals=[100*np.mean(np.array(res['blind_extra'])>0), 100*np.mean(np.array(res['da_extra'])>0)]
ax.bar(["date-blind greedy\n(cancel biggest first)","date-aware greedy"], vals, color=["#e5484d","#f2a93b"], width=.5)
ax.set_ylabel("% of instances where heuristic is NOT minimal")
ax.set_title(f"Heuristic vs exact over {res['N']} random instances")
for k,v in enumerate(vals): ax.text(k, v+1, f"{v:.0f}%", ha="center")
plt.tight_layout(); plt.savefig("fig3_greedy_vs_exact.png", dpi=150)
print("\nfigures written")
```

## Expert Summaries (3)

#### ChatGPT

**Approach:**

Treated the task as a conditional-proof product design problem: reframe the pitch, specify a two-stage exact solve (minimum cardinality, then minimum disruption), and refuse to assert any claim not present in its verified source record.

**Conclusion:**

Keep the timed solvency optimizer, add at most one disclosed missed-income scenario, use an exact binary solver with an explicit proof badge and infeasibility certificate, and prioritize Best First-Time Hack then Best UI/UX.

**Strengths:**

- <span class="markdown-body md-compact"></span>

  Cleanest handling of the "smallest set" claim — cardinality first, disruption second, with an explicit warning that reordering the objectives invalidates the minimality wording

- <span class="markdown-body md-compact"></span>

  Rigorous epistemic hygiene: explicitly declined to fabricate Devpost prior art, library benchmarks, or sponsor forecasts, and labeled the <span class="math inline">$`q_{it}`$</span> eligibility vector as the place where timing must be encoded

- <span class="markdown-body md-compact"></span>

  Realistic time audit — corrected the user's 28-hour figure to ~25 focused hours after meals and transitions

**Weaknesses:**

- <span class="markdown-body md-compact"></span>

  No executed verification of the formulation or of stability claims, so its recommendations rest on argument rather than measurement

- <span class="markdown-body md-compact"></span>

  Thinner on data-source specifics than Claude; did not surface the merchant-string absence that reshapes the recurring-detection demo

- <span class="markdown-body md-compact"></span>

  Prize section is procedurally sound but offers no probability calibration to rank against

*Unique:*

The strict separation between the "minimum cardinality" claim and any weighted objective, plus the staged infeasibility procedure that first maximizes the safe prefix length <span class="math inline">$`L^{*}`$</span> before minimizing peak and total shortfall.

#### Claude

**Approach:**

Decomposed the task into estimation (learning belongs here) versus decision (search belongs here), then executed code to verify the exact solver two independent ways, quantify greedy suboptimality, and measure recommendation instability.

**Conclusion:**

Keep the problem but reframe the objective to least-cost survival with priced slack; CP-SAT primary with a dependency-free pseudo-polynomial DP fallback; synthetic data primary with a real-data validation tab; optimize hardest for Best First-Time Hack.

**Strengths:**

- <span class="markdown-body md-compact"></span>

  Only expert to measure rather than assert: dual exact solvers agreeing, 55.8% vs 2.3% greedy suboptimality rates, and a 21%→1% instability reduction across an 81-point <span class="math inline">$`B_0`$</span> sweep

- <span class="markdown-body md-compact"></span>

  Most valuable single insight — pricing the slack converts infeasibility from an error state into a cheaper-or-costlier answer, and produces the tier-3 output <span class="math inline">$`\Delta^{*}`$</span> by a date

- <span class="markdown-body md-compact"></span>

  Deep, specific stack and deploy guidance (single process, single port, no CORS; deploy before product code) and a 12-item off-by-one trap list including lead time <span class="math inline">$`\ell_i`$</span> and last-day-of-month recurrence

**Weaknesses:**

- <span class="markdown-body md-compact"></span>

  Substantial portions of its dataset-schema findings carry citations that do not support the specific claim, so the CaixaBank field list and Berka standing-order count must be treated as reported rather than verified

- <span class="markdown-body md-compact"></span>

  Prize win probabilities are presented numerically but are self-described judgment anchored only on aggregate VTHacks 13 figures

- <span class="markdown-body md-compact"></span>

  Its own fixture failed to trigger the infeasible branch, which it disclosed — the tier-3 path is therefore designed but not exercised

*Unique:*

The priced-slack objective reframe, the irredundancy certificate rendered as a sentence ("remove any one and you're \$41 under on the 24th"), the zero-dependency DP fallback as insurance against solver install failure, and the honest admission that a date-aware greedy is near-optimal so the case for exact methods rests on certificates rather than heuristic failure.

#### Gemini

**Approach:**

Direct prescriptive verdict with a compact big-M MILP formulation in SciPy, verified by a small executed simulation of an infeasible case.

**Conclusion:**

Stick with the original problem, use MILP with weighted pain plus a large slack penalty and an <span class="math inline">$`\epsilon`$</span> index tie-break, generate synthetic data with Faker, and avoid live constraint manipulation.

**Strengths:**

- <span class="markdown-body md-compact"></span>

  Clearest statement of the differentiation line — incumbents are diagnostic, this is prescriptive — in a form usable verbatim in a 4-minute demo

- <span class="markdown-body md-compact"></span>

  Correctly identified the <span class="math inline">$`\epsilon`$</span>-weighted index tie-break as the cheapest stability mitigation, and flagged SciPy C-extension compilation on a fresh VM plus Python/JavaScript timezone mismatch as concrete deployment risks

- <span class="markdown-body md-compact"></span>

  Executed code demonstrating the slack mechanism converting an infeasible instance into a reported \$400 residual deficit

**Weaknesses:**

- <span class="markdown-body md-compact"></span>

  Its objective minimizes weighted pain, not cardinality, so the formulation as written cannot support the "smallest set" claim that is the product's entire differentiator

- <span class="markdown-body md-compact"></span>

  Recommended against live constraint manipulation and characterized TigerData as "borderline decorative, but ticks the box" — the latter directly contradicts the published track criteria

- <span class="markdown-body md-compact"></span>

  Suggested `ngrok` or a raw IP and avoiding Nginx, which forfeits HTTPS, the domain track, and the Caddy path the other experts identified as a four-command job

- <span class="markdown-body md-compact"></span>

  Thinnest research layer — only one of three external facts held up, and its prior-art and chart-library claims are uncited

*Unique:*

The named deployment failure modes (SciPy compilation on a bare VM, agent context-window exhaustion on large React/FastAPI files) and the crispest one-sentence answer to the incumbent-comparison judge question.

## Assumptions and Limitations

##### Assumptions

- <span class="markdown-body md-compact"></span>

  Planning horizon <span class="math inline">$`T`$</span> of 30–60 days with <span class="math inline">$`n \le 40`$</span> candidate changeable items, which makes exact optimization effectively free at runtime

- <span class="markdown-body md-compact"></span>

  All monetary quantities held in integer cents; end-of-day balance convention with <span class="math inline">$`t=0`$</span> as today after already-posted transactions

- <span class="markdown-body md-compact"></span>

  <span class="math inline">$`B_0`$</span> is the available balance excluding pending debits, not the ledger balance

- <span class="markdown-body md-compact"></span>

  Safety buffer <span class="math inline">$`\beta_t = \$25`$</span> default and deficits rounded up to the nearest \$5 for stability; final certificate re-verified against the true <span class="math inline">$`\beta = 0`$</span> constraint

- <span class="markdown-body md-compact"></span>

  Overdraft fee parameter <span class="math inline">$`\phi \approx \$35`$</span>, a rounded modeling constant anchored on the verified \$34 median fee figure rather than a directly quoted statistic

- <span class="markdown-body md-compact"></span>

  Recurring-stream maturity threshold of ≥3 occurrences with 1% amount-tolerance banding and RapidFuzz similarity ≥ 88

- <span class="markdown-body md-compact"></span>

  Action lead time <span class="math inline">$`\ell_i`$</span> modeled per item; only occurrences with <span class="math inline">$`d_{ik} \ge \ell_i`$</span> contribute to <span class="math inline">$`c_{it}`$</span>

- <span class="markdown-body md-compact"></span>

  Items may bill multiple times within the horizon, so occurrence sets <span class="math inline">$`K_i`$</span> are enumerated rather than amounts multiplied by a fixed count

- <span class="markdown-body md-compact"></span>

  Working budget of ~25–26 focused hours after 6 hours sleep, ~3 hours meals/transitions, and 2 hours submission

- <span class="markdown-body md-compact"></span>

  Synthetic data as the primary demo source, with the pay schedule explicitly labeled as modeled on screen

- <span class="markdown-body md-compact"></span>

  US-centric pay-cycle and merchant conventions for the demo, with the cadence model behind a pluggable interface — the geography decision remains formally open

- <span class="markdown-body md-compact"></span>

  Prize win probabilities are expert judgment adjusted from VTHacks 13's 112 submitted projects, not track-level historical data

##### Limitations

- <span class="markdown-body md-compact"></span>

  Nine of ten sponsor challenge statements were unpublished at analysis time, so that section is a decision procedure rather than a forecast; all sponsor details remain listed as TBD

- <span class="markdown-body md-compact"></span>

  No expert verified any specific Devpost submission or any academic paper on prescriptive personal-finance optimization — the prior-art requirement is only partially satisfied, and both ChatGPT and Claude explicitly declined to fabricate either

- <span class="markdown-body md-compact"></span>

  Several field-level dataset findings (the CaixaBank column list, the absence of any merchant name string, the standing-order table row count, the Berka transaction and account counts) carry citations that did not support the specific claim and must be confirmed by direct inspection

- <span class="markdown-body md-compact"></span>

  Nessie sandbox live status was not verified by any expert and rests solely on the user's own September 2026 check

- <span class="markdown-body md-compact"></span>

  Prize win probabilities are unvalidated judgment; no track-level entry counts or historical win rates were available

- <span class="markdown-body md-compact"></span>

  The tier-3 structural-infeasibility branch was designed but not exercised by the executed code, because the test fixture's trough landed after the first payday

- <span class="markdown-body md-compact"></span>

  Charting library recommendations (Recharts versus Chart.js) rest on uncited expert judgment about agent-writability rather than measured evidence

- <span class="markdown-body md-compact"></span>

  The "holds in N% of futures" robustness layer assumes an income-jitter distribution that no verified dataset supplies

Figures (3)

Claude (3 figures)

<span class="figure-label">Figure 1</span>
<img src="[IMG]" style="max-width:100%; border-radius:4px;" />

<span class="figure-label">Figure 2</span>
<img src="[IMG]" style="max-width:100%; border-radius:4px;" />

<span class="figure-label">Figure 3</span>
<img src="[IMG]" style="max-width:100%; border-radius:4px;" />

## Nomenclature (27 symbols)

<table class="nomenclature-table">
<colgroup>
<col style="width: 33%" />
<col style="width: 33%" />
<col style="width: 33%" />
</colgroup>
<thead>
<tr>
<th>Symbol</th>
<th>Definition</th>
<th>Units</th>
</tr>
</thead>
<tbody>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>t</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Day index within the planning horizon; <span class="math inline"><span class="math inline"><em>t</em> = 0</span></span> is today, end-of-day convention</p></td>
<td><span class="markdown-body md-compact"></span>
<p>days</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>T</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Length of the planning horizon (30–60)</p></td>
<td><span class="markdown-body md-compact"></span>
<p>days</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>B</em><sub>0</sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Starting available balance (excludes pending debits; not the ledger balance)</p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>B</em><sub><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>End-of-day account balance on day <span class="math inline"><span class="math inline"><em>t</em></span></span></p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>B̂</em><sub><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Do-nothing (naive) projected balance on day <span class="math inline"><span class="math inline"><em>t</em></span></span> if no action is taken</p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>i</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Index of a candidate changeable spending item</p></td>
<td><span class="markdown-body md-compact"></span>
<p>dimensionless</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>n</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Number of candidate changeable items (20–40)</p></td>
<td><span class="markdown-body md-compact"></span>
<p>dimensionless</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>a</em><sub><em>i</em><em>k</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Amount of the <span class="math inline"><span class="math inline"><em>k</em></span></span>-th billing occurrence of item <span class="math inline"><span class="math inline"><em>i</em></span></span></p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency (integer cents)</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>d</em><sub><em>i</em><em>k</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Date of the <span class="math inline"><span class="math inline"><em>k</em></span></span>-th billing occurrence of item <span class="math inline"><span class="math inline"><em>i</em></span></span></p></td>
<td><span class="markdown-body md-compact"></span>
<p>day index</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>x</em><sub><em>i</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Binary decision: 1 if item <span class="math inline"><span class="math inline"><em>i</em></span></span> is cancelled or changed</p></td>
<td><span class="markdown-body md-compact"></span>
<p>binary</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>c</em><sub><em>i</em><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Cash freed on or before day <span class="math inline"><span class="math inline"><em>t</em></span></span> by cancelling item <span class="math inline"><span class="math inline"><em>i</em></span></span>, i.e. <span class="math inline"><span class="math inline">∑<sub><em>k</em>: <em>d</em><sub><em>i</em><em>k</em></sub> ≤ <em>t</em></sub><em>a</em><sub><em>i</em><em>k</em></sub></span></span></p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>D</em><sub><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Deficit to be covered by day <span class="math inline"><span class="math inline"><em>t</em></span></span>: <span class="math inline"><span class="math inline">max (0, <em>β</em><sub><em>t</em></sub> − <em>B̂</em><sub><em>t</em></sub>)</span></span></p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>β</em><sub><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Safety buffer floor required on day <span class="math inline"><span class="math inline"><em>t</em></span></span> (default $25)</p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>s</em><sub><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Shortfall slack on day <span class="math inline"><span class="math inline"><em>t</em></span></span> — dollars still uncovered</p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>w</em><sub><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Binary indicator that day <span class="math inline"><span class="math inline"><em>t</em></span></span> incurs an overdraft/NSF fee</p></td>
<td><span class="markdown-body md-compact"></span>
<p>binary</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>ϕ</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Per-event overdraft/NSF fee constant used to price slack</p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>π</em><sub><em>i</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>User-declared disruption (pain) weight of changing item <span class="math inline"><span class="math inline"><em>i</em></span></span></p></td>
<td><span class="markdown-body md-compact"></span>
<p>dimensionless</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>ℓ</em><sub><em>i</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Action lead time: days required before cancellation of item <span class="math inline"><span class="math inline"><em>i</em></span></span> takes effect</p></td>
<td><span class="markdown-body md-compact"></span>
<p>days</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>P</em><sub><em>j</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Date of the <span class="math inline"><span class="math inline"><em>j</em></span></span>-th expected income/payday event</p></td>
<td><span class="markdown-body md-compact"></span>
<p>day index</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>f</em><sub><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Known inflow posting on day <span class="math inline"><span class="math inline"><em>t</em></span></span></p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>o</em><sub><em>t</em></sub></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Known unchangeable outflow posting on day <span class="math inline"><span class="math inline"><em>t</em></span></span></p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>t</em><sup>*</sup></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Binding day — the tightest satisfied constraint in the optimal plan</p></td>
<td><span class="markdown-body md-compact"></span>
<p>day index</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>Δ</em><sup>*</sup></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Minimum external cash required when the instance is structurally infeasible</p></td>
<td><span class="markdown-body md-compact"></span>
<p>currency</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>J</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Jaccard similarity between consecutive recommended plans under input perturbation</p></td>
<td><span class="markdown-body md-compact"></span>
<p>dimensionless</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>S</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Number of sampled income/spend scenarios in the robustness sweep</p></td>
<td><span class="markdown-body md-compact"></span>
<p>dimensionless</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>M</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Large penalty coefficient on slack in a single-objective (big-M) formulation</p></td>
<td><span class="markdown-body md-compact"></span>
<p>dimensionless</p></td>
</tr>
<tr>
<td class="nomenclature-symbol"><span class="math inline"><em>ϵ</em></span></td>
<td><span class="markdown-body md-compact"></span>
<p>Microscopic deterministic tie-break coefficient on item index</p></td>
<td><span class="markdown-body md-compact"></span>
<p>dimensionless</p></td>
</tr>
</tbody>
</table>

## Narrative

## Expert Comparison

| Dimension | ChatGPT | Claude | Gemini |
|:---|:---|:---|:---|
| Question Zero verdict | Keep core, reframe as "cash-flow safety plan"; add one disclosed scenario | Keep core, reframe the **objective** to least-cost survival | Keep core unchanged; pivots are traps |
| Pivot ranking | Debt allocation 3rd/5th, uncertain income 4th, thin-file last | Debt = "a sorted list"; thin-file = fatally flawed; uncertain income = layer | All three rejected outright |
| Solver choice | Exact binary solve; CP-SAT or MILP equivalent, tooling not math | CP-SAT primary + pseudo-poly DP fallback; date-aware greedy as visible foil | `scipy.optimize.milp` |
| Objective structure | Lexicographic: cardinality <span class="math inline">$`K^{*}`$</span> first, then disruption <span class="math inline">$`\sum c_i x_i`$</span> | Lexicographic: fees, shortfall, disruption, **then** cardinality, then hysteresis | Single weighted: <span class="math inline">$`\sum \pi_i x_i + M\sum s_t + \epsilon\sum i\,x_i`$</span> |
| Supports "smallest set" claim | Yes, explicitly | Yes, at objective level 4 | **No** — cardinality never minimized |
| Infeasibility | Staged: maximize safe prefix <span class="math inline">$`L^{*}`$</span>, then min peak <span class="math inline">$`M`$</span>, then total | Three tiers ending in <span class="math inline">$`\Delta^{*}`$</span> "\$62 by Thursday" | Slack absorbs it; report residual |
| Stability mitigation | Cents, reserve, quantized <span class="math inline">$`c_i`$</span>, deterministic tie-break | Measured: buffer <span class="math inline">$`\beta`$</span>=\$25 + \$5 deficit rounding + hysteresis → 21%→1% flip rate | <span class="math inline">$`\epsilon`$</span>-weighted index tie-break |
| Data verdict | Synthetic default; Plaid sandbox optional adapter | Synthetic primary + real-data validation tab | Faker script, ~50 lines |
| TigerData | Skip unless core finishes unusually early | Genuine use: continuous aggregates produce the solver's input vector; ~3h | "Borderline decorative, but ticks the box" |
| Live constraint manipulation | Only after core works, one control | Build the cheap version (locks + pain tiers), ~1.5h | Don't — it's a distraction |
| Deploy | FastAPI + server-rendered HTML + local Chart.js, systemd, Caddy if domain lands | FastAPI serving built static files, one process one port, Caddy HTTPS | FastAPI + React, `uvicorn` on port 80, `ngrok` or raw IP |
| Top prize priority | First-Time, then UI/UX | First-Time (weakest field, and optimizing for it = optimizing for overall quality) | First-Time, then UI/UX |
| Evidence base | Declined to assert unverified prior art | Executed code + 27-source research pass | Executed code, minimal research |

The agreement is broad and load-bearing. All three keep the problem, all three reject all three user-proposed pivots for the same structural reasons, all three choose exact optimization over learned models, all three absorb infeasibility with slack rather than throwing an error, all three make synthetic data the primary demo source, all three land on FastAPI on a single Vultr VM, and all three rank Best First-Time Hack above Best UI/UX. Where they differ is in the **objective ordering** (which determines whether the headline claim is defensible), the **value of TigerData**, and whether **live manipulation** earns its build time.

## Expert Divergence

**Divergence 1 — Gemini's objective cannot support the product claim.** Gemini's formulation minimizes <span class="math inline">$`\sum_i \pi_i x_i + M\sum_t s_t + \epsilon\sum_i i\,x_i`$</span>. Cardinality never appears. With uniform weights this often coincides with a small set, but it is not minimized, so "here is the *smallest* set of changes" is unsupported by the model. Gemini's own executed run illustrates the blind spot from the other direction: with a \$810 naive deficit against \$510 of cancellable items, it cancelled all five and reported \$400 of residual slack — correct behavior, but a case where cardinality is forced and therefore uninformative. **Resolution:** adopt ChatGPT's explicit ordering — minimize cardinality, then re-solve for minimum disruption subject to <span class="math inline">$`\sum_i x_i = K^{*}`$</span> — nested inside Claude's priced-slack levels above it. ChatGPT states the constraint plainly: if you minimize dollars or burden first, you are no longer entitled to the minimality claim.

**Divergence 2 — TigerData's value.** Gemini called it "borderline decorative, but ticks the box." That reasoning does not survive contact with the published brief, which names continuous aggregates, unified relational-plus-stream storage, 90%+ compression, "lag-free, real-time frontend charts," and explicitly lists "financial prediction engines" as in-scope, with the prize going to the most performance-driven use \[S25\]. A decorative connection scores zero against those named criteria. **Resolution:** Claude's construction is the only non-decorative one on the table — a daily `time\_bucket` continuous aggregate whose output *is* the <span class="math inline">$`\{f_t, o_t\}`$</span> vector the solver consumes \[S26\], making the database load-bearing rather than ornamental. ChatGPT's caution still binds: do it only after the stateless core is complete.

**Divergence 3 — live constraint manipulation.** Gemini says it distracts from "we did the math for you." Claude says per-item lock toggles plus three pain tiers hand the judge the controls and cost ~1.5h. ChatGPT splits the difference. **Resolution:** Claude's position is stronger because the interaction is a *demonstration of the solver*, not a feature — a judge naming something they would never cancel, followed by a sub-second re-solve and a new certificate, is evidence the optimization is real. Build the cheap version only; it is the first thing cut if behind.

**Divergence 4 — deployment path.** Gemini's `uvicorn` on port 80 with `ngrok` or a raw IP forfeits HTTPS, the domain track, and the well-documented Caddy path. The published runbook material Claude surfaced makes the opposite case: expose only 443 through Caddy and never open 8000 publicly \[S5\]. Gemini's own top risk — SciPy C-extensions failing to compile on a fresh VM — is real and argues for pre-downloaded wheels, not for a weaker deploy target.

## Technical Detail

### Question Zero: the framing is small, the problem is not

The user's instinct that "don't overdraft before Friday" is a hundred-dollar problem is wrong on the economics and right on the presentation. The verified numbers: a median overdraft episode lasting 3 days on a median \$50 overdraft with a median \$34 fee implies an **8,273 percent APR** \[S4\], and aggregate bank overdraft/NSF revenue was **\$5.83 billion in 2023** even after a **51% collapse since 2019** \[S20\]. Framing a product around an 8,000%-APR credit product used by tens of millions is not a small problem. What is small is the sentence "you'll be \$40 short on the 20th, cancel Hulu."

The pivots all fail for structural reasons the experts independently identified. **Debt payoff allocation** collapses to avalanche ordering under simple assumptions — a sort, not an optimization — and only acquires depth once minimum payments, due dates, and revolving interest make accrual bilinear in balance × decision, which is a nonlinear integer program and unsafe in 28 hours. **Thin-file credit building** asks you to optimize a proprietary score you cannot compute; you would be optimizing an invented proxy while claiming a guarantee, which destroys the one property that differentiates the project. **Uncertain income** is genuinely deeper but converts the central claim from a deterministic proof into a distributional one; it belongs as a bounded layer, not as the core. Notably, the credit-building population overlaps the overdraft population already — 41% of the frequent overdraft/NSF group carry subprime scores versus 10% of the no-fee group (637 vs 744 average), and 40% of the frequent group has no available credit on any card \[S4\] — so the adjacency can be stated in one sentence without building anything.

The user population is empirically solid and, usefully, the mechanism is *surprise* rather than indifference: **43% were surprised** by their most recent overdraft against 22% who expected it, with surprise highest among light overdrafters at **51%** for those with 1–3 fees \[S4\]. Among frequent-fee account holders, **54% hold ≤\$500** across checking and savings and **30% under \$100**, against **60% holding more than \$5,000** in the no-fee group \[S4\]. A forward-looking dated prescription is the correct intervention for a population that cannot see the event coming — that is the strongest 20-second opening available.

> Claude's reframe is the single highest-leverage change in this entire analysis: stop asking "which minimal set keeps <span class="math inline">$`B_t \ge 0`$</span>?" and ask "what is the cheapest way through the next <span class="math inline">$`T`$</span> days?" — because with priced slack there is no such thing as no solution, only a more expensive answer.

### Approach: why exact, and the honest reason

The task decomposes cleanly. **Estimation** — recurring streams, next-due dates, amount drift, income timing — is noisy and statistical, and learning belongs there. **Decision** — which minimal set restores feasibility — is a fully specified deterministic function over <span class="math inline">$`2^n`$</span> subsets with <span class="math inline">$`n \le 40`$</span>, checkable exactly by prefix sums. Search belongs there.

What each approach can and cannot guarantee: an exact solver returning `OPTIMAL` proves feasibility and minimum cardinality *for the encoded ledger*, and returning `INFEASIBLE` proves impossibility, with CP-SAT additionally able to surface a minimal unsat core naming the guilty constraints via `add\_assumptions` and `sufficient\_assumptions\_for\_infeasibility()` \[S1\]. A learned sequence model or transformer can estimate income timing and recurrence but cannot establish that a chosen action set keeps every future balance non-negative without a separate verifier — and there are no counterfactual action labels to train on. Reinforcement learning requires a trustworthy spending-behavior simulator that does not exist. An LLM asked to reason over 60 prefix sums fails confidently and non-deterministically; it belongs at the string-normalization and prose-rendering edges only, never inside the feasibility decision.

Claude's most valuable act of intellectual honesty is to undercut the user's own premise: across 398 random solvable instances, a **date-blind** greedy that cancels biggest-first needed more items than optimal in **55.8%** of cases (mean 1.45 extra cancellations), but a **date-aware** greedy was suboptimal in only **2.3%** of cases (mean 0.05 extra items, \$21.70 extra cut). So the case for exact optimization does not rest on heuristics being bad. It rests on two things: at <span class="math inline">$`n \le 40`$</span> the guarantee is free, and exactness is the only route to the artifacts the product claim depends on — a minimality proof, a named binding day <span class="math inline">$`t^{*}`$</span>, and a proof of impossibility. Say exactly that to a judge; it is a stronger answer than pretending greedy fails.

On tooling, CP-SAT's advantage here is not speed — at this scale everything is instant. It is the API surface: five distinct statuses distinguishing "proved optimal" from "found something unproven" from "proved impossible," plus the unsat-core mechanism and `add\_hint` warm-starting with `fix\_variables\_to\_their\_hinted\_value` \[S1\]. Note the primer's own guidance to *start* development with a 60–300 second time limit \[S1\], an order of magnitude above what a live demo tolerates, so set `max\_time\_in\_seconds` low (≈2s) and use `relative\_gap\_limit = 0.05` for any early exit with a provable quality bound \[S1\]. One directional external data point, with its bias disclosed: on 480 RCPSP instances of 300 tasks at a 1-minute limit, OR-Tools 9.14 CP-SAT landed within 10% of best-known on 100% of instances while Gurobi 11.0 produced no feasible solutions at all across the MILP formulations tried \[S21\] — published by a competing vendor on an instance class far larger than this one, so it supports "CP-SAT is strong on scheduling-shaped combinatorics," nothing more. Claude's independent verification that a ~40-line dependency-free pseudo-polynomial DP returns the identical plan to brute-force lexicographic enumeration is the practical insurance policy: if the solver dependency misbehaves at 1am on hotel wifi, the fallback is already written and already agrees.

### The formulation

Work in **integer cents throughout** — this permanently eliminates the <span class="math inline">$`B_t = -0.004`$</span> fake-overdraft bug class. Precompute once at model-build time:

<span class="math display">
``` math
\hat B_t = B_0 + \sum_{\tau \le t}(f_\tau - o_\tau) - \sum_i \sum_{k \in K_i,\, d_{ik} \le t} a_{ik}, \qquad D_t = \max(0,\; \beta_t - \hat B_t), \qquad c_{it} = \!\!\sum_{k \in K_i,\, \ell_i \le d_{ik} \le t}\!\! a_{ik}
```
</span>

The entire product is one constraint family in covering form:

<span class="math display">
``` math
\sum_{i=1}^{n} c_{it}\, x_i \;+\; s_t \;\ge\; D_t \qquad \forall t \in \{0,\dots,T\}
```
</span>

with <span class="math inline">$`s_t \le M w_t`$</span> and user locks <span class="math inline">$`x_i = 0`$</span> for "keep no matter what." Because <span class="math inline">$`c_{it}`$</span> is non-decreasing in <span class="math inline">$`t`$</span>, the constraint sets form a nested chain — this is a **covering knapsack over a chain of prefix constraints**, a liquidity-scheduling structure worth naming out loud to a judge.

The lexicographic objective, merging both defensible orderings:

1.  <span class="math inline">$`\min \sum_t \phi\, w_t`$</span> — fee count, zero if a clean plan exists
2.  <span class="math inline">$`\min \sum_t s_t`$</span> — total shortfall dollars
3.  <span class="math inline">$`\min \sum_i x_i`$</span> — **cardinality**, which licenses the "smallest set" claim
4.  <span class="math inline">$`\min \sum_i \pi_i x_i`$</span> — disruption, among equally small sets
5.  <span class="math inline">$`\max\, \lvert\{i: x_i = x_i^{\text{prev}}\}\rvert`$</span> — hysteresis against the previously shown plan
6.  Deterministic tie-break on item id

Note this synthesis places cardinality at level 3, ahead of disruption — that is ChatGPT's ordering constraint honored inside Claude's priced-slack envelope. Set <span class="math inline">$`\phi \approx \$35`$</span> as a rounded modeling parameter anchored on the verified \$34 median fee figure \[S4\]; Claude's stronger claim of a "\$35 median at large institutions" did not hold up against its source, so present <span class="math inline">$`\phi`$</span> as a parameter with a cited order of magnitude, not as a quoted statistic.

Then post-process an **irredundancy check**: remove each selected <span class="math inline">$`i`$</span> and find the day that breaks. This is <span class="math inline">$`O(n \cdot T)`$</span>, ~30 lines, and it produces the demo's best sentence. Claude's executed fixture output it verbatim — remove the rideshare budget and you are \$31.00 short on day 24; remove the annual subscription and you are \$95.00 short on day 25. That is a rendered proof, not a badge.

**Named traps.** Inclusive-versus-exclusive prefix (<span class="math inline">$`d_{ik} \le t`$</span> versus <span class="math inline">$`<t`$</span>) — pick it, docstring it, assert it in a test. Day-0 double counting: is today's posted spend inside <span class="math inline">$`B_0`$</span> or in <span class="math inline">$`o_0`$</span>? Horizon boundary <span class="math inline">$`T`$</span> — if the horizon ends the day before payday, an off-by-one hides or invents an overdraft at the single riskiest moment. Payday business-day adjustment, since a one-day error flips feasibility. Action lead time <span class="math inline">$`\ell_i`$</span>: cancelling today does not stop tomorrow's charge, and an annual subscription cancelled mid-cycle frees \$0 this horizon because it is already paid. Last-day-of-month recurrence appears as three distinct day-of-month values, 28/30/31, splitting one stream into three apparent points \[S10\] — make it a first-class cadence, not `day\_of\_month = 31`. Weekly cadences hit 4 or 5 times in a 30-day window depending on start day, so enumerate occurrences rather than multiplying by a fixed count. Available versus ledger balance — ledger overstates by exactly the pending debits that cause overdrafts. Sign conventions, noting Berka encodes debit/credit as a `trans\_type` field \[S10\]. Internal transfers look like spend plus income; net them. Refunds can make <span class="math inline">$`c_{it}`$</span> non-monotone if uncareful; clamp. Timezone at midnight, which is precisely where the constraints live — Gemini independently flagged Python/JavaScript date mismatch as a top-three risk.

One refinement over the user's stated design deserves emphasis: **an item can bill more than once in a 60-day horizon**, so model occurrence sets <span class="math inline">$`K_i`$</span>, not a single <span class="math inline">$`(a_i, d_i)`$</span> pair.

### Infeasibility: never show the word

The slack vector makes the model feasible by construction, so infeasibility becomes a positive-cost solution. Three tiers:

- **Tier 1, proven sufficient** (<span class="math inline">$`\sum_t s_t = 0`$</span>, status `OPTIMAL` \[S1\]): the plan, the irredundancy certificate, the binding day <span class="math inline">$`t^{*}`$</span>.
- **Tier 2, best partial**: minimize fee events, then peak shortfall <span class="math inline">$`\max_t s_t`$</span>, then total, then disruption. "Your levers don't cover it. Best available: one fee instead of four." ChatGPT's variant — first maximize the safe prefix length <span class="math inline">$`L^{*}`$</span>, then minimize peak and total shortfall — is a defensible alternative ordering; it delays the first breach as long as possible rather than minimizing its depth. Pick one and state the semantics in the UI.
- **Tier 3, structurally impossible**: cancelling everything still leaves a gap. Compute <span class="math inline">$`\Delta^{*} = \max_t(D_t - \sum_i c_{it})`$</span> and the latest date it can arrive. "This is an income problem, not a spending problem. The smallest thing that fixes it is \$62 by Thursday the 19th." Nobody ships this, and it is the most useful output in the product.

Claude disclosed that its own fixture's trough landed after the first payday so the tier-3 branch never fired — **plant the infeasible scenario deliberately and assert it in a unit test.** Do not assume a tuned fixture exercises it. The CP-SAT unsat-core path \[S1\] is genuine garnish for a judge but is the second implementation, not the first; note also that not all CP-SAT constraints support reification, so the core trick only works on constraints written in enforceable form.

### Stability

Claude measured this rather than theorizing, sweeping <span class="math inline">$`B_0`$</span> across ±\$40 in \$1 steps (81 solves). Naive configuration — <span class="math inline">$`\beta = 0`$</span>, no tie-break, no hysteresis — flipped the plan on **21%** of \$1 steps with mean Jaccard <span class="math inline">$`J = 0.821`$</span>. Mitigated — <span class="math inline">$`\beta = \$25`$</span>, deficits rounded up to the nearest \$5, overlap-preferring lexicographic tie-break — flipped on **1%** with <span class="math inline">$`J = 0.996`$</span>. A one-dollar change flipping the recommendation one time in five is both a trust-killer and a demo-killer; the mitigations are nearly free.

Root causes in order: **upstream detector churn** (if the stream set changes, the *model* changes, not just the solve — freeze streams per session), **degenerate optima** (the argmin is discontinuous and the solver's choice among ties varies with thread count and seed, so fix the seed and set a single worker for reproducibility), **knife-edge constraints** (deficit rounding coarsens the demand grid — this is the bulk of the measured improvement), and **no memory between solves** (hysteresis plus `add\_hint` verified with `fix\_variables\_to\_their\_hinted\_value` \[S1\]). Gemini's <span class="math inline">$`\epsilon\sum_i i\,x_i`$</span> index tie-break is the same mechanism at its cheapest and is worth including regardless.

Critically, <span class="math inline">$`\beta`$</span>, rounding, and hysteresis change the *requirement*, never the *verification*. Always re-verify the final plan against the true <span class="math inline">$`\beta = 0`$</span> constraint and report the certificate against that. And keep the wording precise: "sufficient under the schedule shown," never "guaranteed you will not overdraft." The first is true; the second breaks in one question.

The stability machinery then converts into a feature at near-zero marginal cost: re-solve across <span class="math inline">$`S \approx 200`$</span> perturbed scenarios (<span class="math inline">$`B_0 \pm \$50`$</span>, <span class="math inline">$`P_j \pm 1`$</span> day, amount jitter) and display "this plan holds in 94% of 200 simulated futures." That delivers the uncertain-income depth without pivoting and directly targets Copilot's documented absence of balance projection for irregular income \[S19\].

### Recurring-charge detection

Rule-based periodicity is the mainstream approach and the cheap high-value version. The canonical recipe derives four time anchors per transaction — day of month, business day of month, days to end of month, business days to end of month — counts occurrences of each amount within a tolerance neighbourhood, and requires both a minimum occurrence count and consistency on one of those anchors \[S10\]. The threshold is a precision/recall dial with **no good setting**: at six occurrences you miss genuine high-value charges that only occurred five times; at three you start admitting ordinary repeated €9.99 purchases \[S10\]. Expose it as a slider rather than pretending it is tuned.

For the output schema, copy Plaid's: group on **description + amount + cadence**, treat a stream as matured only at **≥3 occurrences**, and return category, merchant name, frequency ∈ {monthly, semi-monthly, biweekly, weekly}, plus average and last amounts \[S11\]. You cannot simply call the endpoint — recurring transactions are gated behind a product-access request \[S15\] — but the schema is battle-tested and makes the API look professional. Plaid's own documentation positions recurring-stream data as useful for cash-flow management and spending reduction \[S14\], which is the honest admission that the *category* is not novel; the differentiator is the timed prescriptive optimization and the proof boundary.

For merchant normalization, `rapidfuzz` is the clear pick: MIT-licensed, a C++ rewrite of FuzzyWuzzy's scorers running **20–40× faster**, with `fuzz.WRatio` as the recommended blended default and `process.cdist` for all-pairs, and FuzzyWuzzy explicitly not recommended for new projects \[S3\]. Scale is a non-issue — naive `cdist` is fine to roughly 50,000 × 50,000 and you have tens of items \[S3\]. **Do not use Dedupe:** it requires interactive active learning where `console\_label` asks you to hand-label 20–50 candidate pairs, and the source explicitly advises against it for a one-off script or when you already know the matching rules \[S3\]. Given the stated debugging constraints, that is decisive. An unsupervised alternative exists — DBSCAN on a cylinder projection with amount transformed by <span class="math inline">$`\log_{1.01}`$</span> plus <span class="math inline">$`\sin`$</span>/<span class="math inline">$`\cos`$</span> of day-of-month, which at <span class="math inline">$`\varepsilon = 2`$</span>, MinPts = 8 reproduced the same clusters as the rule-based method \[S10\] — elegant, but strictly extra risk for equal output in a weekend. One packaged option exists, `bankdatainvestigation==1.0.0`, exposing `DetectRecurrencyI`/`DetectRecurrencyII` with tunable `amount\_tolerance` (default 0.01), `period\_tolerance` (default 6 minimum occurrences), and `n\_days` (default 3 days of accepted payment-day variance) \[S10\]; it is single-author and obscure, so `pip install` and smoke-test it tonight or skip it. ChatGPT, working from a narrower source record, declined to recommend any package at all — a defensible position and the same practical conclusion.

The cheap pipeline, ~2–3 hours and agent-implementable: normalize the string (uppercase, strip digits and processor prefixes like `SQ *`, `TST*`, `PAYPAL *`, `POS`, `ACH`, strip trailing city/state, truncate), cluster with RapidFuzz `token\_set\_ratio`/`WRatio` ≥ 88 \[S3\], band amounts at 1% tolerance within cluster \[S10\], fit cadence from median inter-arrival days and snap to {7, 14, 15, 30, 90, 365} with last-day-of-month special-cased, require ≥3 occurrences \[S11\], and emit next-due date, expected amount, cadence, and confidence.

What it misses, stated before a judge finds it: variable-amount recurring (utilities, usage-based phone), annual and quarterly items with fewer than three occurrences in-window, free-trial-to-paid transitions, **BNPL installments** (four payments then stop — dangerous, because you would "free" money that was going to stop anyway), prorated first charges, price increases, and merchant rebrands. There is also a documented false-positive class where payments landing in the same *period* of the month but not every month get flagged as recurring, since same-day-of-month similarity alone does not establish periodicity, and the documented 28/30/31 date-splitting problem \[S10\]. Build the 20-minute escape hatch — a manual override toggle for "is this recurring? ✓/✗/amount/next date" — which converts a detector miss during the demo from an embarrassment into a feature.

### Data: verified findings, and what remains unverified

On the **CaixaBank set** \[S24\], the verified position is: Apache 2.0 licensing with documented transaction amounts, timestamps, merchant details, transaction types, card data, MCC codes, and demographic/account-related user data — but **no documented running checking balance, no income schedule, no payday field, and no recurring labels**. That is sufficient to answer sub-questions (a) and (b): to derive a daily balance you must fabricate <span class="math inline">$`B_0`$</span> *and* every non-card flow — rent, payroll, ACH — which is to say you would be inventing the exact series your prescription is about. Claude reports finer schema detail (that the only merchant identity is the MCC code, with no merchant name string at all, and that `users\_data` carries only an annual income scalar with no pay frequency or payday dates); those specific field-level claims traced to a Databricks workshop repository rather than the dataset documentation and did **not** verify, so treat them as reported-but-unconfirmed and inspect the actual headers before relying on either reading. Gemini reached the same practical verdict — don't use it \[S24\] — by a shorter route. Claude's licence caution also deserves carrying: the Apache-2.0 attribution traces to the author's accompanying Kaggle notebook rather than necessarily the dataset itself, so re-verify before citing it in a submission.

On **better alternatives** (sub-question c), the one verified finding is that the CTU Relational Dataset Repository still provides public guest access to export its Financial database, with temporal data and over a million rows, and its documentation references a transaction balance field \[S16\]. That last point matters enormously — a running balance is the single hardest thing to find in public financial data. Claude's report of a 6,471-record standing-order table alongside the transactions did not verify against its cited source, so the "measure my detector against real ground truth" layer should be treated as contingent on confirming that table exists when you export the database. Downsides either way: Czech, CZK, 1990s, cryptic field names, monthly salary cadence, and no merchant name strings.

On **recurring labels** (sub-question d), the answer is plainly no. No documented public dataset in the verified record is a recurring-subscription benchmark; Plaid can return recurring-stream output but that is a product response, not a labeled public benchmark \[S12\]\[S15\].

On **synthetic data** (sub-question e), all three experts converge, and Claude verified a perfect anti-example: a Kaggle dataset titled exactly "Financial Transactions Dataset" by Cankat Saraç, alternately named "Fictional Financial Transactions Dataset," generated with Faker, with a licence field of literally "Unknown" and an author statement that it is for demonstration only and "should not be used for any decision-making or analysis" — a sentence a judge could read aloud — yet carrying 20,935 views and 3,683 downloads \[S23\]. **Kaggle popularity is not fitness, and the name collision with the CaixaBank set is a live trap.** What makes synthetic data convincing instead: heavy-tailed amounts with psychological price points rather than uniform draws; a real business-day-adjusted pay cycle with ±1 day jitter; recurring streams with amount drift and one deliberate mid-horizon price increase; day-of-week seasonality; genuinely messy merchant strings (`SQ *BLUE RIDGE COFF`, `AMZN Mktp US*2K4L9`, `TST* MELLOW MUSHROOM 0114`) which you *must* synthesize because no public dataset has them; an accumulated running balance that is tight rather than comfortable; and planted demo cases — one where date-blind greedy provably fails, one tier-2, one tier-3 — each asserted in a test. No off-the-shelf agent-based transaction generator was verified by any expert; a ~150-line agent-written generator is ~45 minutes and gives total demo control, which is the actual requirement.

Plaid sandbox is worth keeping as an optional adapter for the Link-flow demo moment only. Its transactions data carries date, amount, category, merchant, and location fields with high documented fill rates \[S15\]\[S12\], but custom sandbox transactions are restricted to the dynamic user, limited in batch size, applied only to a depository account, and **cannot have future dates** \[S13\] — so it cannot create the forward paycheck and bill schedule the solver needs. Snapshot history locally and construct the forecast separately. Nessie remains unverified by all three experts; keep it off the critical path.

**Geography stays open, per the guardrail, but decide it explicitly rather than by accident.** US-centric buys biweekly/semimonthly cycles, business-day payroll adjustment, the fee anchor \[S4\], MCC assumptions, US processor-prefix merchant noise, a US judge panel, a US sponsor, and every statistic in the pitch. Country-agnostic buys a broader claim and compatibility with Czech monthly-salary data but costs the fee constant the least-cost objective depends on. Note also that Plaid's recurring availability is documented as limited to the US, Canada, and UK \[S15\]. The synthesized recommendation: build US-centric but put the pay cycle behind a small pluggable interface (biweekly / semimonthly / monthly / irregular), ~20 minutes, so "does this work outside the US?" gets answered with "the cadence model is pluggable and the fee is a parameter."

### Storage

A database is **not architecturally necessary**. One user, a 60-day horizon, ≤40 items, a few thousand transactions — stateless upload → parse → detect → solve → render is the correct and lowest-risk architecture, and it is the right answer for offline judging. Say that plainly rather than pretending otherwise.

The non-decorative TigerData version, if the core lands early: load the full transaction corpus into a hypertable, create a daily `time\_bucket` continuous aggregate per account with sum and count — which *is* the <span class="math inline">$`\{f_t, o_t\}`$</span> vector the solver consumes, making the database produce the solver's input rather than merely storing it — stack a second monthly-bucket hierarchical aggregate to power day-of-month histograms for cadence detection, and report the compression ratio \[S26\]\[S25\]. Two traps: continuous aggregates refresh in the background and avoid rebuilding the whole view unlike plain PostgreSQL materialized views \[S26\], but **real-time aggregates are disabled by default from TimescaleDB v2.13 onward** \[S26\], so blending the newest raw rows requires explicit opt-in or you will demo a chart that silently omits today's transactions. And after installing Docker on the VM you must log out and back in for group membership to take effect \[S5\] — twenty minutes lost if you don't know it. MongoDB Atlas is a pure technology checkbox with no thematic fit \[S25\]; running a second datastore for zero product reason is a liability.

### UI/UX

The strongest single-screen structure is three horizontal bands. **Band 1** is the verdict sentence at ~40px — the largest thing on screen, readable from three metres: "You go \$118 negative on Thursday, Sept 24. Three changes fix it." **Band 2** is one chart with two lines: do-nothing in muted dashed red with the below-zero region filled, with-plan solid above a faint <span class="math inline">$`\beta`$</span> buffer band, the zero line emphasized as 1px solid rather than a gridline, paydays <span class="math inline">$`P_j`$</span> as vertical ticks, the binding day <span class="math inline">$`t^{*}`$</span> marked, and **each prescribed change rendered as a small upward step on the with-plan line at <span class="math inline">$`d_i`$</span>**. That last element is the entire point — the timing thesis becomes *visible*; you can see the step land before the dip. **Band 3** is the prescription list: 3–5 rows of item, amount, date freed, and a one-line why, each with a lock toggle that re-solves.

On communicating proof: visual design cannot prove a financial claim, but it can make the claim's *scope* legible. Split the screen's epistemics by visual weight and legend it explicitly — solid line plus filled area for scheduled and dated events (detected streams at ≥3 occurrences \[S11\], known bills), dashed or faded for estimated ones, with legend text reading "solid = scheduled · dashed = estimated." Then render the certificate as a **sentence, not a badge**: "Verified minimal — remove any one of these three and you're \$41 under on the 24th." A green GUARANTEED chip with nothing behind it reads as marketing and invites attack; judges remember sentences and ignore badges. Add the percentile fan from the scenario sweep captioned with the hold rate. Never say "guaranteed" — say "sufficient under the schedule shown," and reserve the proof language for an `OPTIMAL` status only.

For charting, Recharts is the pick for an agent-directed React build (declarative, `ReferenceLine` for zero and paydays, `ReferenceDot` for <span class="math inline">$`t^{*}`$</span>, `Area` for the shortfall fill, and the most training data of any React charting library, so the agent writes it correctly first time); Chart.js with the annotation plugin is the equivalent if you skip React entirely, which is ChatGPT's preference and a legitimate lower-risk path. Avoid D3 from scratch and avoid Plotly, whose default aesthetic reads "scientific notebook" — the wrong register for consumer finance and a direct UI/UX cost.

What wins in four minutes, in order: it loads instantly and nothing is broken; one screen, one decision, no navigation; typographic hierarchy readable across a table; real data, never placeholder; designed empty, loading, and error states; exactly one memorable motion moment. What reads as unfinished: default Bootstrap/MUI, off-scale spacing, three font families, unstyled tables and scrollbars, visible console errors, and — worst — the presenter saying "ignore that." One "ignore that" costs the track.

Cheap polish, specific: one font family; three sizes only (12/16/40px); `font-variant-numeric: tabular-nums` on every currency figure, because misaligned digits is the single clearest amateur tell in a finance UI and the fix is one CSS line; a strict 8px spacing scale with nothing off-scale; one card radius and one shadow; a neutral gray ramp plus exactly one accent, with **red reserved solely for the below-zero region** so the chart does not lose its meaning; 200–300ms ease-out on chart redraw with a `prefers-reduced-motion` guard; a skeleton of the actual layout rather than a spinner; and critically an empty state offering a one-click sample account, because **judges will not upload a file** — the demo path must be one click. Skip dark mode.

### Stack and deploy

The highest-value engineering decision in this section: **build the frontend to static files and serve them from FastAPI's `StaticFiles` in the same process on the same port.** One process, one port, no CORS. The published Vultr runbook material lists browser CORS errors from a wrong `ALLOWED\_ORIGINS` as the first failure mode \[S5\], and a split frontend/backend is how you earn it; collapsing the deployment deletes that entire bug class.

Path: Ubuntu on Vultr Cloud Compute (upsize to 2 vCPU / 4 GB if running TimescaleDB against a large hypertable); Caddy for HTTPS as a short command sequence with a two-line Caddyfile reverse-proxying to the local uvicorn port, no manual certificate handling \[S5\]; expose only 443 and never open 8000 publicly \[S5\]; a `/health` endpoint returning JSON with status, version, and uptime \[S5\] as the five-second pre-demo verification you hit from your phone. Provisioning can be fully scripted through the Vultr API if you want it \[S5\], but don't gold-plate — click the console once and move on.

The single most important scheduling decision, on which Claude and ChatGPT agree and Gemini implicitly concurs: **deploy hello-world over HTTPS on the domain Friday night, before any product code**, and point DNS immediately because TLS issuance waits on propagation \[S5\]. Then redeploy after every major block. Projects die not because a feature failed but because everything worked locally and deploy was attempted at 5am. Pre-memorize the failure table: CORS → wrong `ALLOWED\_ORIGINS`; healthcheck failing → process not binding `0.0.0.0`; port unreachable → expose via Caddy on 443; TLS slow → DNS not propagated; 502 from Caddy → container stopped or internal port changed \[S5\].

Pre-departure, today: `pip download` every wheel into a local directory and **verify an offline install works** (this also neutralizes Gemini's top risk of SciPy or ortools C-extensions failing to compile on a bare VM); scaffold the frontend once at home and warm the npm cache; pull and `docker save` the TimescaleDB image if you're attempting that track; export the CTU Financial database to CSV \[S16\] and pull any Kaggle files; download fonts locally rather than trusting a CDN; smoke-test that the solver imports and solves a small model; create the Vultr account and claim free credits \[S25\]; and write a one-line deploy that rsyncs the built assets and restarts, so a flaky 30-second connection window is enough. **After 11pm, never install from the hotel** — build locally, rsync the output, keep phone tethering as backup. Record a 90-second backup walkthrough Saturday night and keep a fixture flag that runs fully offline, because judging is offline Sunday morning \[S17\] and remote hosting is a convenience, not the only working version.

### Prior art

The verified incumbent positions are narrower than either marketing or the user's fear suggests. **Rocket Money** has 10M+ users on a free tier, identifies forgotten subscriptions within 24 hours of linking, offers one-tap cancellation, and negotiates bills for 35–60% of first-year savings — and its signature primitive, "Safe to Spend," is a **scalar** \[S27\]. A scalar cannot tell you which changes to make or when the freed money arrives. **Monarch** is the best incumbent at irregular income via scenario and cash-flow projection tools, but those are user-proposed what-ifs — you propose, it projects \[S19\]\[S27\]. **Copilot** has no balance projection for irregular income and no advanced cash-flow projection for variable income \[S19\] — that gap is documented, not asserted. **YNAB** enforces discipline via zero-based budgeting \[S19\], prescriptive about method rather than about which charge to cut by when. **Simplifi** offers spending plans and projected cash flow at roughly \$3.99/month \[S27\], which establishes that *projection* is commodity.

So the unoccupied ground, stated narrowly enough to survive a judge: every incumbent either reports a scalar safe-to-spend, lists or cancels subscriptions, or lets the user hand-build scenarios. None searches the space of possible changes and returns a minimal, dated, certified-sufficient set, and none tells you the minimum external cash and the deadline when no set suffices. Keep the claim exactly that narrow. Gemini's one-liner is the usable demo form: they are diagnostic, this is prescriptive.

**Neither ChatGPT nor Claude verified any specific Devpost submission or any academic paper on prescriptive personal-finance optimization**, and both explicitly declined to invent either. That is a real coverage gap in the prior-art requirement. What is defensible without a citation is the structural framing — a covering knapsack over a chain of prefix constraints, a liquidity-scheduling problem — which signals you know what you built. And the structural risk is known: personal-finance dashboards are among the most common hackathon genres, so a judge's prior on hearing "personal finance" is *another budgeting app*. Break that prior in the first 20 seconds with the counterexample — a case where cancelling the biggest subscription still overdrafts you, because it bills after the dip.

### Prize strategy

Calibration baseline: VTHacks 13 drew 550 hackers submitting 112 projects for \$12K in prizes across 100+ universities \[S18\], so a single open track has a ~0.9% base rate. All win probabilities below are expert judgment adjusted from that anchor, not track-level data. Selection itself is cheap — the submission form asks you to select every category you want to enter \[S17\].

On the non-obvious tracks: **Ut Prosim** ("That I May Serve") rewards service and community impact — who is helped and whether the help is real — and requires no institutional connection; the overdraft-exposure evidence supplies the specificity \[S4\], at a cost of one slide. **DEI** rewards equity of access or outcome; an honest angle already exists in the distributional facts (41% of the frequent-fee group subprime versus 10%, and 40% with no available credit on any card \[S4\]), paired with a real accessibility pass — enter, don't optimize for it, and don't manufacture anything beyond that. **Best Hack That Didn't Work** is a prize for interesting, honestly documented failure — an ambitious attempt, why it broke, what was learned. It is *not* for a working project; tick it only if a real dead branch exists to narrate (a learned prescriber abandoned because it could not certify feasibility would be a genuinely good entry). **Best Domain Name from GoDaddy Registry** has essentially no build requirement beyond registering the domain \[S25\], which you need anyway for TLS — the highest return per minute on the list. **Vultr** treats deploying on an instance as itself the qualifying action, with the brief highlighting one-click deployment and scalable compute and directing you to free credits \[S25\]; differentiate with HTTPS, a custom domain, and an articulable reason you need a VM. **TigerData** names continuous aggregates, unified relational-plus-stream storage, 90% compression, and "financial prediction engines" explicitly \[S25\]. **Best First-Time Hack** judges genuine first-timers on the same criteria against a smaller and weaker field, where completeness and polish separate entries rather than ambition.

Ranked ticks, merging all three experts (Claude's probabilities, ChatGPT's eligibility discipline):

| Rank | Track | Extra build | Est. <span class="math inline">$`p_{\text{win}}`$</span> | Note |
|---:|:---|:---|:---|:---|
| 1 | Best Use of TigerData | 3.0h | 0.18 | Fewest serious entrants because it is real work; data shape matches the named criteria \[S25\] |
| 2 | Best First-Time Hack | 0 | 0.16 | Weakest field. **Optimize hardest here** |
| 3 | Best Use of Vultr | 0.5h | 0.13 | Many tick it, few do it meaningfully \[S25\] |
| 4 | Best UI/UX Hack | 0 | 0.11 | Drops to ~0.03 if the UI is merely "clean Tailwind" |
| 5 | Best Domain Name | 0.25h | 0.07 | Free; wit decides \[S25\] |
| 6 | Capital One | up to 2h | 0.06 | Conditional: ~0.20 if consumer-finance themed, ~0 otherwise |
| 7 | Best Ut Prosim | 0.3h | 0.06 | Slide-only cost, honest framing required |
| 8 | Best Hack That Didn't Work | 0 | 0.05 | Only with a real dead branch |
| 9 | Galois | 0 | 0.04 | Conditional on a verification-flavored prompt; the optimality proof and unsat core \[S1\] fit at zero extra build |
| 10 | Best DEI Hack | 1h | 0.04 | Honest distributional angle plus accessibility pass |
| 11 | Gemini API | 0.75h | 0.04 | Only if LLM merchant normalization is independently the right component |
| 12 | Databricks | 3h | 0.03 | Only pays off if already on the CaixaBank set |
| 13–15 | 3rd / 2nd / 1st Overall, Raffle | 0 | 0.025 / 0.012 / 0.008 / 0.004 | Free to tick; solo against teams of four |
| — | Solana, ElevenLabs, Presage, MongoDB Atlas | 2–4h each | ≤0.01 | No shot without building for them \[S25\]. **Don't** |

**Worth altering the build for: exactly three, ~3.75 hours total** — Vultr (0.5h, needed anyway), domain (0.25h, needed for TLS anyway), TigerData (3h, the only track where the data genuinely wants a time-series database). ChatGPT would swap TigerData for additional proof-oriented UI polish; that dissent is worth respecting as the tiebreaker if the core is even slightly behind.

**The single track to optimize hardest for is Best First-Time Hack**, and the decisive argument is not the user's stated preference — it is that optimizing for it is *identical* to optimizing for overall quality: a finished, deployed, polished, working demo. There is no tradeoff. The corollary is a standing warning: never let a sponsor integration compromise the "it works and it's finished" property. If TigerData and First-Time ever conflict, First-Time wins.

Solo **helps** on First-Time (no teammate's experience can disqualify you), UI/UX (one coherent design voice — teams produce the visual inconsistency judges read as unfinished), Ut Prosim (a first-person account of the user population is more credible from one person), and Domain Name. Solo **hurts** on overall placement (raw scope against 4× the hours), any multi-sponsor-integration strategy, and presentation depth — with no one to rehearse against, rehearse aloud three times with a timer Sunday morning.

**The Friday 7pm decision rule** — a procedure, not a forecast, since all nine sponsor challenge statements, requirements, and judging details are still listed as TBD \[S17\]. Run a fixed 20-minute triage scoring each revealed track on four axes: *fit-without-change* (2 = already satisfied as planned, 1 = satisfied with framing only, 0 = requires code); *marginal build hours <span class="math inline">$`h`$</span>*, multiplied by 1.5 for any SDK never touched; *solver risk* (touching the solver or data pipeline → auto-reject, per the user's stated low risk tolerance); and *4-minute legibility* (can you show it inside the existing demo flow without a detour). Then: **tick every track with fit ≥ 1, because those are free. Build for a track only if <span class="math inline">$`h \le 3`$</span> and solver risk = 0 and legibility = 2 and cumulative extra build ≤ 6h. Hard cap of two build-altering tracks beyond Vultr, TigerData, and the domain. All build-altering decisions locked by 9:00 PM Friday; anything not *started* by 6:00 PM Saturday is cancelled regardless of how good it looked.** ChatGPT adds two conditions worth folding in: the feature must have a local fallback and must not require new undocumented credentials or hotel-network reliability, and it should improve the base project even if the prize is lost.

Pre-committed contingencies so Friday's decision takes minutes: **Capital One** — the HackMTY "Consumer Financial Autonomy and Credit Building" precedent the user supplied is the right kind of signal and is a template, not a guarantee; if the theme lands, this becomes the primary track worth up to 4 hours (populate a Nessie account from the generated data, read it back, and address the credit-building adjacency using the overlap statistics \[S4\]); if unrelated, tick it and build nothing. **Databricks** — a ≤3h path exists only if already on the CaixaBank set; on other data, skip. **Galois** is a formal-methods house and the one to watch for a free high-value entry: if the prompt rewards verification or provable correctness, the `OPTIMAL` status, minimality certificate, and unsat core are a genuine fit at zero extra build \[S1\] — have that framing pre-written. **Deloitte, Peraton, CoStar, Impiricus, Procedura, nebulaONE** — pre-commit to not building unless fit = 2 \[S18\].

### The build order

Two scheduling principles drive everything, both from the user's own constraints. First, spend the scarce agent window (Friday evening through Saturday night) on code generation and the free Sunday-morning window on what you can do unaided — pitch writing, recording, the submission form, copy polish, manual QA. Second, anything needing bandwidth happens on venue wifi before the 11pm closure, or at home today.

| Window | Work | Kill criterion |
|:---|:---|:---|
| Fri 20:00–21:00 | Ceremony, 20-min track triage, **write the 4-minute demo script** as the scope contract | Write the script before any code regardless |
| Fri 21:00–22:30 | Vultr VM, DNS, Caddy HTTPS, `/health`, hello-world deployed, one-line deploy working | 22:30 no HTTPS → serve on IP:port, drop the Domain track |
| Fri 22:30–23:00 | Bulk data pull onto the VM; TimescaleDB container up | Ingest not started → **drop TigerData now**, not Saturday |
| Fri 23:00–Sat 01:30 (hotel) | **Solver core**: model builder, exact solve + DP fallback, lexicographic objective, slack tiers, irredundancy certificate, off-by-one unit tests | 01:30 solver not correct on fixtures → switch to the DP fallback, drop unsat-core |
| Sat 01:30–02:00 | Deploy backend as-is; verify `/health` over HTTPS | — |
| Sat 02:00–08:00 | Sleep | — |
| Sat 08:00–09:00 | Synthetic generator + fixtures with **planted** greedy-fails, tier-2 and tier-3 cases, each asserted | — |
| Sat 09:00–10:00 | Recurring detection: normalize, band, snap cadence, ≥3 occurrences | 10:00 not working → hard-code fixture streams, reframe as user-confirmed |
| Sat 10:00–11:00 | API endpoints wired to the real pipeline; **freeze the JSON contract** | — |
| Sat 11:00–14:00 | **Frontend**: three bands, chart, prescription list, lock toggles → re-solve | 14:00 chart not showing real solver output → drop toggles and scenario fan, ship static |
| Sat 14:00–15:30 | TigerData continuous aggregates + a measured "N rows → daily series in X ms" | Not ingesting at 14:00 → skip entirely, untick the track |
| Sat 15:30–17:00 | Robustness layer: scenario sweep, hold-rate caption, hysteresis | 17:00 incomplete → drop, keep the single-scenario certificate |
| Sat 17:00–18:30 | **Full deploy** + end-to-end on the live URL; fix the CORS/healthcheck/502 class \[S5\] | **HARD GATE 18:30: no working deployed demo → freeze all features, fix only** |
| Sat 18:30–20:00 | Dinner + polish pass 1: type scale, 8px spacing, tabular-nums, single accent, red-only-below-zero | — |
| Sat 20:00–23:00 | Polish pass 2: empty and skeleton states, certificate sentence, one motion moment. **Record the backup video** | Last large agent spend before the allowance thins |
| Sat 23:00–Sun 01:30 (hotel) | Buffer, or **one** added-value item. **No new dependencies** | 01:00 stretch not working → delete the branch, do not debug |
| Sun 01:30–02:00 | **Code freeze.** Commit, final deploy, verify the live URL from phone hotspot | — |
| Sun 02:00–06:00 | Sleep — and the emergency repair window, since the allowance has reset | — |
| Sun 06:00–08:00 | Submission: writeup, tick all categories \[S17\], README disclosures, video, rehearse 3× with a timer | Deadline is 08:00 \[S17\] |

This audits to roughly 26 working hours against the user's 28-hour figure — deliberate slack, and consistent with ChatGPT's independent correction that 28 hours assumes zero non-sleep breaks and a realistic focused budget is closer to 25. Note what the plan inverts: **deploy is first and polish is last.** That inversion is why most demos break and this one shouldn't.

### The three highest-risk assumptions

**1. That the demo data will support the claim being made.** Every dataset examined is missing something essential — no verified public source combines dated transactions, merchant strings, a running balance, and an income stream. The CaixaBank set has no documented running balance, income schedule, or payday field \[S24\]; the CTU Financial database references a transaction balance \[S16\] but is Czech, 1990s, monthly-cadence, and carries no merchant strings. So something will be fabricated, most likely the pay schedule — which is the single most load-bearing input in the model. If a judge opens the repository and finds a hard-coded payday generator sitting behind a "provably sufficient" badge, the demo is over. Mitigation: label synthetic elements on screen, use synthetic data openly as the primary source, and validate at least one component against real data.

**2. That the recurring detector produces a clean, demo-able candidate set on first contact.** The occurrence threshold has no good setting \[S10\], there is a documented same-period false-positive class and documented 28/30/31 date-splitting \[S10\], and card-level data is structurally poorer in recurrence than account-level data. Plan for the detector to be mediocre: the manual override toggle, one curated demo account, a hard timebox, and a hard-code fallback.

**3. That ~28 hours is enough for solver plus detection plus database plus frontend plus deploy, solo, with an agent allowance that thins at the worst moment.** Realistically this scope is 40+ hours even at high agent throughput. **The plan only closes because of the kill criteria, which means the kill criteria are not advice — they are the plan.** The failure mode is not one thing breaking; it is everything being 80% done at 6am Sunday, which scores zero on presentation and completeness. The Saturday 18:30 deployed-demo gate is the non-negotiable defence. A secondary risk nested inside: if the allowance depletes Saturday evening, the polish pass that wins UI/UX and First-Time is what you lose — which is why polish is scheduled *before* the buffer.

### Added-value layers, ranked by value per hour

| Rank | Layer | Hours | Why it earns the time |
|---:|:---|:---|:---|
| 1 | Priced slack + least-cost objective | 2.0 | Kills infeasibility as a failure mode, denominates the answer in real dollars anchored on the verified fee scale \[S4\], and produces the demo's decisive sentence |
| 2 | Irredundancy certificate rendered as a sentence | 0.75 | "Remove any one and you're \$41 under on the 24th." Converts a claim into a demonstration; best memorability per minute available |
| 3 | Minimum external cash and deadline (<span class="math inline">$`\Delta^{*}`$</span>, tier 3) | 1.0 | "\$62 by Thursday." Genuinely actionable and shipped by nobody |
| 4 | Binding-day and action-execution calendar (action, cutoff, affected bill, cash-release date) | 1.0 | ChatGPT's top two picks; makes the timing thesis legible rather than asserted |
| 5 | Greedy-vs-optimal head-to-head toggle in the UI | 1.0 | The entire technical argument rendered; pre-compute on the fixture |
| 6 | Scenario robustness hold-rate | 2.5 | Real sampled-robust depth, delivers the uncertain-income pivot without pivoting, targets Copilot's documented gap \[S19\] |
| 7 | Detector precision/recall measured against real standing-order data | 2.0 | Turns "I wrote a heuristic" into a measured number — direct hit on original contribution, contingent on confirming that table exists |
| 8 | Action lead time <span class="math inline">$`\ell_i`$</span> | 0.75 | "You can't cancel this in time — it bills tomorrow." One parameter, instant credibility, pre-empts a judge question |
| 9 | Small menu of equally minimal alternatives | 1.0 | Answers "why this subscription?" and makes tie-flips comprehensible; only after stability is proven |
| 10 | Bill-date rescheduling as a decision variable | 2.0 | "Don't cancel Spotify — move your phone bill four days." A lever no incumbent ships; integer date variables add solver risk. Stretch only |
| 11 | Sensitivity panel ("\$20 more on the 18th removes two of these three changes") | 1.5 | Shadow prices approximated by grid re-solves; cheap and feels like magic |
| 12 | Real accessibility pass (keyboard, WCAG AA, ARIA, reduced-motion) | 1.0 | Genuine DEI substance plus UI/UX points |

Explicitly negative value: user accounts and auth, multi-account aggregation, mobile responsiveness (judges use a laptop), a general constraint editor, and dark mode as a second theme. If only three layers get built, take ranks 1–3 at roughly 3.75 hours total — they convert the project from an optimizer with a chart into a tool that always has an answer, proves it, and states the exact size of the hole when there isn't one.

## Scope Definition Q&A

- **Q1:**

  Do you want the deliverable to lock in a final problem definition (original overdraft-prevention vs. one of the pivots like debt payoff or uncertain income) before the rest of the plan is built, or should the research present the ranked options and hour-by-hour plan for the CURRENT problem as a fallback if you don't pivot?

  \
  **A:**

  (not answered)

- **Q2:**

  Since all sponsor tracks except GoDaddy are unpublished until Friday 7pm, do you want the research to include pre-ceremony intelligence gathering (searching past hackathon sponsor challenge archives, sponsor tech blogs, and job postings) to predict likely themes, or should it focus only on generic guidance to apply once tracks are revealed?

  \
  **A:**

  (not answered)

- **Q3:**

  For the recurring-charge detection and data research, should the search prioritize solutions implementable by an AI coding agent in a few hours (favoring well-documented Python libraries with copy-pasteable examples), or should it also surface more powerful but harder-to-integrate options (e.g. custom NLP merchant normalization) even if they're riskier given your admitted debugging limitations?

  \
  **A:**

  (not answered)

- **Q4:**

  When searching for prior art and competing hackathon projects, should the scope be limited to Devpost hackathon submissions specifically, or should it also include shipped commercial/startup products and academic papers on prescriptive personal finance optimization?

  \
  **A:**

  (not answered)

- **Q5:**

  For the dataset research (section 6), is there a hard deadline before Friday 7pm by which you need a finalized data source decision, or can the research present multiple viable options with tradeoffs for you to finalize live during the event once you see the actual sponsor challenges?

  \
  **A:**

  (not answered)

- **Q6:**

  Should the geographic/regulatory scope of the personal finance user model be US-centric (e.g. US bank transaction conventions, biweekly/semimonthly pay cycles, US merchant naming conventions), or should it be designed to be country-agnostic?

  \
  **A:**

  (not answered)

- **Q7:**

  Is there anything else that would help refine this analysis?

  \
  **A:**

  Practical constraints that shape the plan. Buildings close at 11pm every night, so Friday and Saturday late work happens in a hotel room on hotel wifi. My Claude usage allowance resets at 2am Sunday, so Friday evening through Saturday night is my scarce window and Sunday morning is free. Four minutes to demo, which should shape what I build, not just how I pitch it. And everything I need must be downloaded or installed before I leave home today.

------------------------------------------------------------------------

## Appendix A — Scope Definition Q&A

- **Q1:**

  Do you want the deliverable to lock in a final problem definition (original overdraft-prevention vs. one of the pivots like debt payoff or uncertain income) before the rest of the plan is built, or should the research present the ranked options and hour-by-hour plan for the CURRENT problem as a fallback if you don't pivot?

  \
  **A:**

  (not answered)

- **Q2:**

  Since all sponsor tracks except GoDaddy are unpublished until Friday 7pm, do you want the research to include pre-ceremony intelligence gathering (searching past hackathon sponsor challenge archives, sponsor tech blogs, and job postings) to predict likely themes, or should it focus only on generic guidance to apply once tracks are revealed?

  \
  **A:**

  (not answered)

- **Q3:**

  For the recurring-charge detection and data research, should the search prioritize solutions implementable by an AI coding agent in a few hours (favoring well-documented Python libraries with copy-pasteable examples), or should it also surface more powerful but harder-to-integrate options (e.g. custom NLP merchant normalization) even if they're riskier given your admitted debugging limitations?

  \
  **A:**

  (not answered)

- **Q4:**

  When searching for prior art and competing hackathon projects, should the scope be limited to Devpost hackathon submissions specifically, or should it also include shipped commercial/startup products and academic papers on prescriptive personal finance optimization?

  \
  **A:**

  (not answered)

- **Q5:**

  For the dataset research (section 6), is there a hard deadline before Friday 7pm by which you need a finalized data source decision, or can the research present multiple viable options with tradeoffs for you to finalize live during the event once you see the actual sponsor challenges?

  \
  **A:**

  (not answered)

- **Q6:**

  Should the geographic/regulatory scope of the personal finance user model be US-centric (e.g. US bank transaction conventions, biweekly/semimonthly pay cycles, US merchant naming conventions), or should it be designed to be country-agnostic?

  \
  **A:**

  (not answered)

- **Q7:**

  Is there anything else that would help refine this analysis?

  \
  **A:**

  Practical constraints that shape the plan. Buildings close at 11pm every night, so Friday and Saturday late work happens in a hotel room on hotel wifi. My Claude usage allowance resets at 2am Sunday, so Friday evening through Saturday night is my scarce window and Sunday morning is free. Four minutes to demo, which should shape what I build, not just how I pitch it. And everything I need must be downloaded or installed before I leave home today.

------------------------------------------------------------------------

## Appendix B — Project Metadata

**Mode:** Deep Think

**Created:** September 18, 2026

**Expert models:**

- ChatGPT GPT-5.6 Terra · Extra High
- Claude Opus 5 · Extra High
- Gemini 3.1 Pro · High

Generated by VeriLM

