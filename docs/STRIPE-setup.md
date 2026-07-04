# Stripe Integration — Setup Guide (PAY-04)

| | |
|---|---|
| **Applies to** | `extraction-service` (`app/billing.py`, `app/billing_routes.py`) |
| **Plans** | Free / Pro / Scholar — see `monetization-pricing.md` |
| **Status** | Config-gated: with `STRIPE_SECRET_KEY` **unset**, billing endpoints return `503` and the app still boots. Nothing here is required for on-prem/enterprise deploys. |

This guide takes you from a fresh Stripe account to a working upgrade flow, in **test mode**, then to production. Follow the steps in order; the whole thing is ~20 minutes.

---

## 0. How it works (30-second model)

```
User clicks "Upgrade"
   → SPA calls  POST /billing/checkout {plan, interval}
   → API creates a Stripe-hosted Checkout Session, returns its URL
   → SPA redirects the browser to Stripe; user pays
   → Stripe redirects back to FRONTEND_BASE_URL/billing/success
   → Stripe ALSO sends a signed webhook → POST /billing/webhook
   → API verifies the signature and sets user.plan / user.plan_status
```

**The webhook — not the browser redirect — is the source of truth.** A user who
closes the tab, or cancels/downgrades later from the billing portal, still syncs
correctly because Stripe re-sends events. Do not gate plan upgrades on the
success-page redirect alone.

Events handled (`app/billing.py → handle_event`):

| Stripe event | Effect on the user |
|---|---|
| `checkout.session.completed` | Set `plan` (from checkout metadata), `plan_status=active`, store customer + subscription IDs |
| `customer.subscription.updated` (active/trialing) | Map the price → plan; `plan_status=active` |
| `customer.subscription.updated` (past_due/unpaid) | Keep plan, `plan_status=past_due` |
| `customer.subscription.updated` (canceled) / `customer.subscription.deleted` | Downgrade to `free`, `plan_status=canceled` |

---

## 1. Create a Stripe account and get API keys

1. Sign up at **https://dashboard.stripe.com**.
2. Stay in **Test mode** (toggle, top-right) for everything until section 7.
3. Go to **Developers → API keys** and copy the **Secret key** (`sk_test_…`).
   This is `STRIPE_SECRET_KEY`. (You do **not** need the publishable key — checkout
   is hosted by Stripe, not embedded.)

---

## 2. Create the Products and Prices

The code maps a `(plan, interval)` pair to a Stripe **Price ID**. You need four
recurring prices. Suggested amounts come from `monetization-pricing.md`.

Go to **Product catalog → Add product** and create two products, each with a
monthly and an annual recurring price:

| Product | Price | Interval | Env var it fills |
|---|---|---|---|
| **KnowledgeBook Pro** | $19.00 | Monthly | `STRIPE_PRICE_PRO_MONTHLY` |
| KnowledgeBook Pro | $180.00 | Yearly | `STRIPE_PRICE_PRO_ANNUAL` |
| **KnowledgeBook Scholar** | $35.00 | Monthly | `STRIPE_PRICE_SCHOLAR_MONTHLY` |
| KnowledgeBook Scholar | $336.00 | Yearly | `STRIPE_PRICE_SCHOLAR_ANNUAL` |

After saving each price, click it and copy its **Price ID** (`price_…`) — **not**
the product ID. You will paste these into `.env` next.

> Tip: create the annual price by adding a second price to the *same* product.

---

## 3. Configure `.env`

In `extraction-service/.env` (copy from `.env.example` if needed):

```bash
# --- Subscription plans (quota; independent of Stripe) ---
PLAN_FREE_DOCS=2
PLAN_PRO_DOCS=20
PLAN_SCHOLAR_DOCS=60

# --- Stripe billing ---
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=            # filled in section 4
STRIPE_PRICE_PRO_MONTHLY=price_xxxxxxxxxxxxx
STRIPE_PRICE_PRO_ANNUAL=price_xxxxxxxxxxxxx
STRIPE_PRICE_SCHOLAR_MONTHLY=price_xxxxxxxxxxxxx
STRIPE_PRICE_SCHOLAR_ANNUAL=price_xxxxxxxxxxxxx

# Where Stripe returns the browser after checkout (your SPA origin)
FRONTEND_BASE_URL=http://localhost:5173
```

You can leave any price blank — that specific `(plan, interval)` button simply
reports unavailable via `GET /billing/config` and returns `503` if called.

---

## 4. Set up the webhook

The API listens at **`POST /billing/webhook`**. With the default compose stack
the API is at `http://localhost:8000`, so the webhook URL is:

```
http://localhost:8000/billing/webhook          (behind a domain: https://api.yourdomain.com/billing/webhook)
```

### 4a. Local development — Stripe CLI (recommended)

Stripe cannot reach `localhost` from the internet, so forward events with the CLI:

```bash
# install: https://stripe.com/docs/stripe-cli
stripe login
stripe listen --forward-to localhost:8000/billing/webhook
```

`stripe listen` prints a signing secret (`whsec_…`). Put it in `.env` as
`STRIPE_WEBHOOK_SECRET` and restart the API. Trigger a test event to confirm:

```bash
stripe trigger checkout.session.completed
```

### 4b. Production — dashboard webhook

1. **Developers → Webhooks → Add endpoint.**
2. Endpoint URL: `https://api.yourdomain.com/billing/webhook`
3. Select events to send:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Save, then reveal the **Signing secret** (`whsec_…`) and set it as
   `STRIPE_WEBHOOK_SECRET` in the production environment.

> The webhook endpoint is **public by design** (Stripe is unauthenticated) but is
> protected by signature verification — a request without a valid
> `Stripe-Signature` for your secret is rejected with `400`.

---

## 5. Restart and verify

```bash
cd extraction-service
docker compose up -d --build api worker      # rebuild to pick up the stripe SDK + .env
```

Sanity checks (get an access token by logging in first):

```bash
# 1. Billing is enabled and prices resolved
curl -s http://localhost:8000/billing/config \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
# → {"enabled": true, "available": {"pro_monthly": true, ...}, "current_plan": "free", ...}

# 2. Start a checkout — returns a Stripe URL to open in a browser
curl -s -X POST http://localhost:8000/billing/checkout \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"plan":"pro","interval":"monthly"}' | jq
# → {"url": "https://checkout.stripe.com/c/pay/..."}
```

Open that URL, pay with a **test card** (section 6). After payment, the webhook
fires and `GET /auth/me` should show `"plan": "pro"`, `"plan_status": "active"`.

Then confirm the quota reflects the new plan:

```bash
curl -s http://localhost:8000/api/usage -H "Authorization: Bearer $ACCESS_TOKEN" | jq
# → {"plan":"pro","limit":20,"used":N,"remaining":...}
```

---

## 6. Test cards

Use these only in test mode (any future expiry, any CVC, any ZIP):

| Scenario | Card number |
|---|---|
| Successful payment | `4242 4242 4242 4242` |
| Requires authentication (3DS) | `4000 0025 0000 3155` |
| Declined | `4000 0000 0000 0002` |

Full list: https://stripe.com/docs/testing

To exercise cancellation/downgrade: open **`POST /billing/portal`** (returns a
portal URL), cancel the subscription there, and confirm the user drops back to
`plan=free` after the `subscription.deleted`/`updated` webhook.

---

## 7. Going live

1. Flip the dashboard to **Live mode** and create the products/prices again (test
   and live catalogs are separate) — copy the new `price_…` (live) IDs.
2. Swap `.env` to **live** values: `STRIPE_SECRET_KEY=sk_live_…`, the live price
   IDs, and set `FRONTEND_BASE_URL` to your production SPA origin.
3. Create a **live** webhook endpoint (section 4b) and use its live `whsec_…`.
4. Ensure the webhook endpoint is HTTPS and publicly reachable.
5. Do one real (or `$0` coupon) end-to-end purchase to confirm the live path.

---

## 8. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `503 billing is not configured` | `STRIPE_SECRET_KEY` is blank or `.env` not loaded — rebuild/restart the API. |
| `503 no Stripe price configured for pro/annual` | That price env var is empty — add the `price_…` ID. |
| `503 billing SDK not installed` | The image predates the `stripe` requirement — rebuild (`--build`). |
| `400 invalid webhook signature` | `STRIPE_WEBHOOK_SECRET` doesn't match this endpoint's secret (CLI vs dashboard have different secrets), or a proxy altered the raw body. |
| Checkout succeeds but plan stays `free` | Webhook not reaching the API. Check `stripe listen` is running (local) or the dashboard endpoint's delivery log (prod). |
| Plan updates but quota unchanged | Quota is monthly; `GET /api/usage` reflects the new `limit` immediately — re-fetch after the webhook lands. |

---

## Endpoint reference

| Method + path | Auth | Purpose |
|---|---|---|
| `GET /billing/config` | user | Is billing live? Which `(plan, interval)` prices exist? Current plan/status. |
| `POST /billing/checkout` | user | Body `{plan: "pro"\|"scholar", interval: "monthly"\|"annual"}` → `{url}`. |
| `POST /billing/portal` | user | `{url}` to the Stripe billing portal (manage/cancel). |
| `POST /billing/webhook` | Stripe (signature) | Receives events; syncs `plan`/`plan_status`. |

*Related: `docs/monetization-pricing.md` (tiers & pricing rationale), `docs/feature-tracking.md` (PAY-04 row).*
