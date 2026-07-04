# GTM One-Pager — KnowledgeBook Launch

| | |
|---|---|
| **Document** | Commercial — Go-to-Market Plan |
| **Product** | KnowledgeBook (Document Knowledge Graph) |
| **Version** | 1.0 |
| **Date** | 2026-07-04 |
| **Status** | DRAFT — for founder/PM review |
| **Launch window** | Targeting Week 10–12 of MVP build (per PRD §11 timeline) |

---

## Beachhead Persona: Researcher / Analyst (Persona A)

**Who:** PhD students, academic researchers, policy analysts, management consultants, and strategy professionals who regularly read 5–10 long-form documents per month (papers, books, technical reports).

**Why this persona first:**

1. **Frequency.** They process the most documents per month of any persona — this means faster activation, faster feedback, and faster organic word-of-mouth within research communities.

2. **Pain intensity.** The core PRD problem ("200–400 page books with 15–20 novel ideas buried in repetition") hits hardest here. A researcher with 40 papers in their reading queue has an acute, daily problem.

3. **Willingness to pay.** Researchers have institutional budgets, grant funding, or expense accounts. The comparison set is journal database access ($15–50/month), reference manager software (Zotero Pro, Mendeley), and Elicit ($12–50/month). A $19/month Pro tier is in-range.

4. **Word-of-mouth density.** Researchers talk to other researchers in labs, departments, Slack groups, Twitter/X, and Discord servers. A single researcher who loves the product can refer 10–20 peers in their network within days.

5. **Trust alignment.** Researchers care most about citation accuracy and confidence transparency — the exact things KnowledgeBook is built around (100% citation coverage, confidence scores on every claim, source-verification affordance). This persona is the best fit for what makes KnowledgeBook different from ChatPDF.

**Not first:** Students (price-sensitive, high churn), Busy Practitioners (lower frequency, harder to reach), Team Leads (need Phase-2 sharing features that do not exist yet).

---

## Positioning & Messaging

### Headline (for landing page, ads, PH tagline)
> "Stop skimming. Get the map."

### One-sentence pitch
> KnowledgeBook reads your 300-page PDF and gives you a navigable concept map, executive brief, chapter guide, and grounded Q&A — all source-cited, in minutes.

### Versus messaging (for acquisition copy)
> "ChatPDF answers your questions. KnowledgeBook shows you what questions to ask."

### Trust hook (for researcher audience specifically)
> "Every concept links to its source excerpt. Every answer shows its confidence. If the scan quality is low, we tell you — we never present guesses as facts."

### Three-word brand positioning
> **Structure. Transparency. Speed.**

---

## Launch Channels — Ranked by Expected ROI

### Channel 1: Research Twitter/X and Academic Communities (Day 1)
**Tactic:** Post a demo thread showing KnowledgeBook's four outputs applied to a well-known, widely-read book (suggestion: a book most target users have been meaning to read). Show the Concept Map first — it is the most visually differentiating output. Link to a waitlist / free-tier signup.

**Why:** Academic Twitter has high signal-to-noise for tool launches. A single retweet from one credible researcher can reach thousands of relevant users. Cost: zero.

**Assumption:** Founder or a known voice in the target community posts, not a brand account.

**Target:** 500 waitlist signups from a single well-executed thread.

### Channel 2: Hacker News — Show HN (Week 2–3 of soft launch)
**Tactic:** "Show HN: I built a tool that builds a concept map from a 300-page book (OCR + knowledge graph)" — lead with the technical substance (how it works), not just the output. HN readers will engage with the pipeline decision (why a graph, not just RAG; what entity resolution looks like; cost per document).

**Why:** HN drives sustained referral traffic, SEO inbound, and high-quality early adopters who will give detailed feedback. A top-10 Show HN drives 500–2,000 signups within 48 hours (assumption based on comparable AI tool launches).

**Assumption:** The founder is comfortable discussing the technical implementation. The OCR quality gate story and "trust over hallucination" angle play well on HN.

### Channel 3: Reddit — r/PhD, r/MachineLearning, r/productivity, r/Professors
**Tactic:** Soft posts framed as "I built this to solve my own problem" — lead with the problem (drowning in papers) before the solution. Share the four outputs for a paper the subreddit community would recognize. Do not hard-sell.

**Why:** These communities are large (r/PhD: 500K+) and have high intent overlap. Reddit converts to free-tier signups well when the post is genuine and the tool is immediately useful.

**Caution:** Each subreddit has strict self-promotion rules. Read them before posting. Post as a community member, not a marketer.

### Channel 4: Product Hunt (Week 6–8 of soft launch)
**Tactic:** Full Product Hunt launch — "KnowledgeBook: Build a concept map of any book or paper in minutes." Gallery images show the four outputs side-by-side for a recognizable book. Embed a short demo video (90 seconds max). Coordinate a hunter with an existing following in the productivity/AI space.

**Why:** Product Hunt provides a structured launch moment, SEO value, and a credibility signal. It converts best after a soft launch has already surfaced bugs and sharpened the onboarding.

**Timing:** Do NOT launch on PH as the very first public moment. Use HN/Reddit soft launch first, fix critical issues, then PH for the amplification round.

**Target:** Top 5 product of the day → 1,000–2,500 free signups within 24 hours (assumption).

### Channel 5: Direct Outreach to Research Communities (Month 2)
**Tactic:** Identify 10–15 research-focused Slack groups, Discord servers, and email lists (lab group Slacks, academic tool communities, university library tool-share lists). Offer 3 months free Pro to any group that tries it and shares feedback with the team.

**Why:** These communities are small but highly concentrated with the exact persona. Conversion to paid from this channel should be higher than any social channel.

---

## Day-1 CTA

The single, unambiguous ask on the landing page and in every piece of launch copy:

> **"Upload your next paper — get the full concept map free."**

No email required to start (remove this barrier for the first 30 days). Collect email after the first output is generated ("Save your concept map — create a free account").

**Rationale:** The tool's value is immediate and visual. Asking users to sign up before seeing anything creates drop-off. The concept map is the WOW moment — show it first, then ask for the email.

---

## Activation Metric

**Primary activation event:** User views the Concept Map for their first uploaded document.

**Activation target (PRD §13):** ≥70% of users rate the concept list "accurate or mostly accurate" — measure with a single in-product prompt shown after the Concept Map loads: "Are these the right concepts? (thumbs up / thumbs down)."

**Secondary activation event:** User asks at least one Q&A question in the same session as viewing the Concept Map. PRD target: ≥50% of viewers use Q&A in the same session.

**Why these:** Viewing the Concept Map is the moment of delivered value — users either see "yes, this understands the book" or they don't. Asking a Q&A question signals they trust the output enough to go deeper. Both are measurable from Day 1 without a survey.

**Tracking plan:** Both events must be instrumented in the web UI before launch. Do not rely on manual checks or post-hoc analysis.

---

## 90-Day Launch Sequence

### Pre-launch (Weeks 1–9, during build)
- [ ] Week 1: Resolve 4 blocking PRD open questions; run PDF/OCR spike.
- [ ] Week 2: Run UX validation with 5 researchers using a hand-crafted Concept Map for a book they know. Need ≥4/5 "yes, this would change how I read." If not, stop and reframe before building.
- [ ] Week 3–4: Stand up waitlist landing page. Run the Twitter/X thread to build a pre-launch list of 300+ signups.
- [ ] Week 6: Private beta with 20–30 waitlist users (researchers). Gather structured feedback on all four outputs.
- [ ] Week 7: Instrument activation metric tracking. Fix top-reported issues.
- [ ] Week 8: Enable Pro tier pricing. At least 5 users should offer to pay voluntarily during beta — if not, revisit pricing and value proposition before public launch.
- [ ] Week 9: Finalize privacy policy, terms of service, and data retention language (especially for uploaded documents).

### Soft Launch (Weeks 10–11)
- [ ] Week 10: Remove waitlist. Anyone can sign up. Enable free tier with 2-doc limit.
- [ ] Week 10: Post Show HN.
- [ ] Week 10–11: Reddit posts in r/PhD and r/MachineLearning.
- [ ] Week 11: Monitor activation metric daily. Target: ≥60% of first-time uploads result in an activated user (Concept Map viewed + thumbs interaction).
- [ ] Week 11: First revenue check — how many free users have upgraded to Pro?

### Growth Round (Weeks 12–13)
- [ ] Week 12: Product Hunt launch (coordinate hunter, launch assets, demo video).
- [ ] Week 12: Email every beta user who gave positive feedback — ask them to upvote and share on PH day.
- [ ] Week 13: Post-PH: analyze traffic sources. Double down on the channel with the highest conversion rate.
- [ ] Week 13: Begin direct outreach to research community Slack/Discord groups with 3-month-free-Pro offer.

### Retention & Monetization (Days 60–90)
- [ ] Day 60: First cohort retention check — what % of Week-1 users uploaded a second document within 30 days? Target ≥30% (PRD §13).
- [ ] Day 60: Email sequence for free users who have used both free doc slots — trigger upgrade prompt at the natural limit moment.
- [ ] Day 75: Introduce student discount ($0 or 50% off Pro for verified .edu email) to expand the Student/Learner persona.
- [ ] Day 90: Revenue review — are we on track for 500 paid users by Month 4? Adjust pricing, GTM, or positioning based on what the data shows.

---

## What Could Kill the Launch

| Risk | Early warning sign | Response |
|---|---|---|
| UX validation fails (< 4/5 researchers say yes) | Validation interviews in Week 2 | Stop. Re-scope. The problem is real; the output format may not be the right solution. |
| Activation rate < 40% (most users don't engage with the Concept Map) | First week of soft launch data | Investigate: is the output quality low, or is the UI not surfacing the right thing first? Fix before PH. |
| Zero organic upgrades during beta | No one offers to pay in Weeks 6–8 | The free tier is too generous, the price is too high, or the value is not landing. Run 5 "would you pay?" conversations immediately. |
| OCR quality failures at launch | Users post complaints about scanned doc results | The quality gate banner (PRD FR-0.5) exists precisely for this. Confirm it is visible and prominent in the UI. |
| Competitor announces a directly competing feature | Monitor monthly | Ship Phase-2 features faster; sharpen the trust/citation differentiation in all messaging. |
