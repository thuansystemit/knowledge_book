# Monetization & Pricing Model — KnowledgeBook

| | |
|---|---|
| **Document** | Commercial — Monetization & Pricing |
| **Product** | KnowledgeBook (Document Knowledge Graph) |
| **Version** | 1.0 |
| **Date** | 2026-07-04 |
| **Status** | DRAFT — for founder/PM review |
| **Feeds into** | PRD §10 open question #7 |

---

## Recommended Model: Hybrid Freemium + Subscription (with Credit Add-ons)

### Why this model

| Option | Verdict | Reason |
|---|---|---|
| Pure credits | Reject | Friction on every upload; churn from inconsistent spend; hard to build retention habit |
| Pure subscription | Reject (for now) | Hard to justify before users have proved value; converts cold leads poorly |
| Pure freemium | Reject | No revenue predictability; power users destroy margins |
| **Hybrid: free tier + subscription tiers + credit top-ups** | **Recommended** | Freemium drives acquisition; subscription creates predictable revenue; credit add-ons capture burst-usage without margin blowouts |

The model mirrors what works in comparable AI-document tools (Notion AI, Gamma, Elicit) and maps cleanly onto the known cost structure: a fixed per-document compute cost with a falling cost curve (MVP $1/$2 → Phase 2 target $0.30).

---

## Pricing Tiers

### Free — $0/month
**Target:** First-time users, students, occasional explorers.

| Included | Limit / Detail |
|---|---|
| Digital PDF uploads | 2 per month |
| Scanned PDF uploads | Not included (OCR cost too high at $2/doc to give away) |
| Output 1 — The Brief | Included |
| Output 2 — Concept Map | Included (capped at 10 concepts, vs. 25 on paid) |
| Output 3 — Chapter Guide | Not included |
| Output 4 — Grounded Q&A | Not included |
| Export (Markdown / JSON) | Not included |
| Document library | Last 2 docs only |

**Rationale for restrictions:** Free users get enough to feel the core value (Brief + partial Concept Map) but not enough to replace a paid workflow. Q&A and Chapter Guide are the stickiest features — withholding them is the clearest upgrade prompt.

---

### Pro — $19/month (or $15/month billed annually = $180/year)
**Target:** Researchers, analysts, busy practitioners (Personas A and B).

| Included | Limit / Detail |
|---|---|
| Digital PDF uploads | 20 per month |
| Scanned PDF uploads | 5 per month (included in 20 combined) |
| All 4 outputs | Full: Brief, full Concept Map (25 concepts), Chapter Guide, Q&A |
| Export | Markdown + JSON |
| Document library | Unlimited (retained per privacy policy) |
| Processing priority | Standard queue |
| Credit add-ons | $5 for 5 extra docs (any type) |

---

### Scholar — $35/month (or $28/month billed annually = $336/year)
**Target:** Heavy researchers, PhD students, consultants, team leads who run many docs themselves (Personas A and D).

| Included | Limit / Detail |
|---|---|
| Digital PDF uploads | 60 per month |
| Scanned PDF uploads | 20 per month (included in 60 combined) |
| All 4 outputs | Full |
| Export | Markdown + JSON |
| Document library | Unlimited |
| Processing priority | Priority queue (targets 30% faster processing) |
| Credit add-ons | $5 for 6 extra docs (slight volume discount) |
| Phase-2 early access | Visual graph explorer, learning-path tree, shareable cards |

---

### Team — $49/seat/month *(Phase 2, not MVP)*
**Target:** Team leads sharing knowledge across groups (Persona D).

Requires shared document library, per-team admin, and shareable concept cards — all deferred to Phase 2 (WON'T ship in this release per PRD §3). Do not sell this tier until those features exist.

---

## Credit Add-on Pricing

| Pack | Price | Per-doc effective price | Notes |
|---|---|---|---|
| 5-doc pack | $5 | $1.00/doc | Available to Free and Pro |
| 10-doc pack | $9 | $0.90/doc | Available to Scholar |
| 25-doc pack | $20 | $0.80/doc | Scholar only; aligns with Phase-2 cost targets |

Credit packs never expire (30-day cap was considered and rejected — it creates resentment; credits are the goodwill purchase).

---

## Unit Economics & Margin Illustration

**Assumptions (flag: all assumed, not validated)**
- A1: 80% of processed docs are digital ($1 cost), 20% are scanned ($2 cost).
- A2: Average effective cost per doc = 0.8 × $1 + 0.2 × $2 = **$1.20/doc** at MVP.
- A3: Phase 2 cost target = $0.30/doc (from PRD §6).
- A4: Pro users process an average of 8 docs/month (well below the 20-doc ceiling).
- A5: Scholar users process an average of 18 docs/month (below the 60-doc ceiling).
- A6: Monthly infrastructure and tooling (excluding engineer salaries): $5,000/month at launch scale.

### Per-user gross margin at MVP costs

| Tier | Revenue | Avg docs used | Avg compute cost | Gross margin | GM % |
|---|---|---|---|---|---|
| Free | $0 | 2 | $2.00 | -$2.00 | — |
| Pro (monthly) | $19 | 8 | $9.60 | **$9.40** | **49%** |
| Scholar (monthly) | $35 | 18 | $21.60 | **$13.40** | **38%** |

### Per-user gross margin at Phase 2 costs ($0.30/doc)

| Tier | Revenue | Avg docs used | Avg compute cost | Gross margin | GM % |
|---|---|---|---|---|---|
| Pro | $19 | 8 | $2.40 | **$16.60** | **87%** |
| Scholar | $35 | 18 | $5.40 | **$29.60** | **85%** |

**Key takeaway:** Margins at MVP are workable if average usage stays well below the plan ceiling (the typical SaaS outcome). Phase 2 cost reduction transforms this into a high-margin product.

### Break-even illustration

**Assumption:** 2 engineers at $10K/month fully loaded + $5K infrastructure = **$25K/month operating cost**.

| Scenario | Blended ARPU (assumption) | Paid users needed to break even |
|---|---|---|
| All Pro | $19 | ~1,320 |
| 70% Pro / 30% Scholar | $23 | ~1,090 |
| 50% Pro / 50% Scholar | $27 | ~930 |

**Assumption A7:** Freemium conversion rate of 8% (industry range: 2–15%; 8% is conservative for a tool with a clear value gate). To reach 1,100 paid users, the free tier needs to attract ~13,750 free signups. This is achievable within 6–9 months of launch with the GTM plan in `docs/gtm-one-pager.md`.

---

## Per-Persona Willingness to Pay

| Persona | Frequency | WTP (assumption) | Best fit tier | Notes |
|---|---|---|---|---|
| A — Researcher/Analyst | 5–10 docs/month | $20–$40/month | Pro or Scholar | Pays for quality tools from grants or expense accounts; comparison is $15–$50 journal/database access |
| B — Busy Practitioner | 2–5 docs/month | $15–$25/month | Pro | Expense-accountable; comparison is $20 ChatPDF Plus |
| C — Student/Learner | 3–8 docs/month | $8–$18/month | Free → Pro | Price-sensitive; convert with free tier + student discount (10 free docs/month for verified .edu email) |
| D — Team Lead/Sharer | Self: 5–10 docs/month | $20–$35/month (self) | Scholar | Team tier is the Phase-2 upsell; do not gate team features on Scholar |

**Student discount (recommended):** 3 months free Pro for verified .edu email. Drives word-of-mouth in research communities — the highest-value acquisition channel.

---

## Pricing Risk Flags

1. **MVP margin is thin at Scholar tier if power users hit 40+ docs/month.** Enforce the per-doc ceiling hard. Consider a fair-use policy for extreme outliers.
2. **Free tier costs $2/user/month in compute.** At 5,000 free users, that is $10K/month in unmonetized compute. Acceptable until the free tier is demonstrably converting at ≥7%.
3. **Scanned doc cost ($2) nearly matches Pro's per-doc credit price ($1).** If scanned usage spikes beyond the 20% assumption, margins compress. Monitor scanned-vs-digital mix weekly post-launch.
4. **Annual pricing discount (21%) must be funded by cash-flow improvement, not margin.** At MVP costs, annual Pro = $15/month × 12 = $180. Compute cost for an annual Pro user (avg 8 docs/month × 12) = 96 docs × $1.20 = $115.20. Margin = $64.80 over the year. Acceptable.

---

## What to Decide Before Launch

- [ ] Confirm free tier limits (2 docs/month) with UX team — test whether the limit is visible enough to drive upgrades without frustrating first-time users.
- [ ] Decide on student discount mechanics (honor-system .edu email vs. verified .edu email — the latter adds friction but reduces abuse).
- [ ] Set credit add-on pricing as stated or adjust based on actual Phase-1 cost spike results (PRD §10, blocking question #2).
- [ ] Decide whether annual billing is offered at launch or deferred to Month 2 (recommendation: defer — reduces launch complexity, add at Month 2).
- [ ] Confirm the Team tier is formally out of scope until Phase 2 features exist.
