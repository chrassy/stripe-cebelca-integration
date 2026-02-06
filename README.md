# Stripe to Cebelca Integration

Automatically creates invoices in Cebelca.biz when a payment succeeds in Stripe.

## Features
*   **Automatic Sync**: Listens for Stripe's `invoice.payment_succeeded` event.
*   **Customer Sync**: Automatically creates or updates customers in Cebelca based on Stripe email/name.
*   **Invoice Detail**: Copies line items, quantities, prices, and VAT rates.

## How to Configure Stripe Webhook

1.  Go to **Stripe Dashboard > Developers > Webhooks**.
2.  Click **Add Endpoint**.
3.  **Endpoint URL**: Your public URL ending in `/webhook` (e.g. using ngrok for local development: `https://your-ngrok-url.ngrok-free.app/webhook`).
4.  **Events to send**: Select `invoice.payment_succeeded`.
5.  Click **Add endpoint**.
6.  Reveal the "Signing secret" (starts with `whsec_`) and use it for `STRIPE_WEBHOOK_SECRET`.

That's it! When a payment happens, an invoice will appear in Cebelca.

## For Developers

### Local Setup
1.  Result `git clone` this repo.
2.  `pip install -r requirements.txt`
3.  `export STRIPE_API_KEY=...` (set env vars)
4.  `python stripe_cebelca_sync.py`
