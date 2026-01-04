# Stripe to Cebelca Integration

Automatically creates invoices in Cebelca.biz when a payment succeeds in Stripe.

## Features
*   **Automatic Sync**: Listens for Stripe's `invoice.payment_succeeded` event.
*   **Customer Sync**: Automatically creates or updates customers in Cebelca based on Stripe email/name.
*   **Invoice Detail**: Copies line items, quantities, prices, and VAT rates.

## How to use (Non-Programmers)

The easiest way to run this is to deploy it to the cloud using **Render**. It has a free tier that is sufficient for low volume.

### Step 1: Deploy to Render

1.  Click the button below:
    
    [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)
    
2.  Sign in or Create an Account on Render.
3.  Give your service a name (e.g., `my-company-invoicing`).
4.  Enter the required API Keys when asked:
    *   `STRIPE_API_KEY`: Found in Stripe Dashboard -> Developers -> API Keys.
    *   `CEBELCA_API_KEY`: Found in Cebelca Settings.
    *   `STRIPE_WEBHOOK_SECRET`: You will get this **after** setting up the webhook in Step 2. for now, you can put a placeholder or set up the webhook first. Or better:
        1.  Go to Stripe Dashboard -> Developers -> Webhooks.
        2.  Click "Add Endpoint".
        3.  For the URL, put `https://YOUR-RENDER-NAME.onrender.com/webhook` (You might need to deploy first to get the URL, then update this variable later in Render Dashboard -> Environment).
        4.  Select event: `invoice.payment_succeeded`.
        5.  Reveal the "Signing secret" (starts with `whsec_`) and use it for `STRIPE_WEBHOOK_SECRET`.

### Step 2: Configure Stripe Webhook

Once your app is running on Render, you will get a URL like `https://my-app.onrender.com`.

1.  Go to **Stripe Dashboard > Developers > Webhooks**.
2.  Click **Add Endpoint**.
3.  **Endpoint URL**: `https://YOUR-APP-URL.onrender.com/webhook`
4.  **Events to send**: Select `invoice.payment_succeeded`.
5.  Click **Add endpoint**.

That's it! When a payment happens, an invoice will appear in Cebelca.

## For Developers

### Local Setup
1.  Result `git clone` this repo.
2.  `pip install -r requirements.txt`
3.  `export STRIPE_API_KEY=...` (set env vars)
4.  `python stripe_cebelca_sync.py`
