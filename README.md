# Meyzban — Test Marketplace MVP

A deployable **functional testing MVP** for guest/host accounts, listings, accommodation requests, host bids, price offers and test bookings. No animation, no real payment processing.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python app.py
```

Visit http://localhost:5000. A SQLite database is initialized automatically with six sample Lahore listings.

**Demo host:** `host@meyzban.test` / `Test12345!` (CHANGE/REMOVE before exposing the site publicly). Register a new guest account in the app to test both sides.

## Deploy without a domain

1. Unzip this folder, push the files to a **private GitHub repository**.
2. In **Render**, create a new **Web Service** connected to that repo (or use the included `render.yaml`).
3. Set build command: `pip install -r requirements.txt`.
4. Set start command: `gunicorn app:app --bind 0.0.0.0:$PORT`.
5. Set environment variable `SECRET_KEY` to a long random string.
6. Open your free `*.onrender.com` URL.

**Important database caveat:** Render's ephemeral filesystem on a free web service can erase SQLite data during restart/redeploy. This is acceptable only for disposable demos. For persistent multi-user testing, use a paid persistent disk (with SQLite) or migrate to managed PostgreSQL before inviting testers. The current source uses SQLite; **setting a PostgreSQL URL alone will not migrate it**.

## Current workflows

- Register/login as guest or host; hashed passwords and session auth
- Browse/search listings; view property detail
- Hosts publish listings
- Guests publish requests; hosts bid; guests accept bids
- Guests submit price offers; hosts accept/decline
- Guests create date-based pending-payment test bookings; cancel bookings
- Separate guest and host dashboards

## Important limitations — NOT production-ready

- No payment gateway, payouts, refund processing, tax calculation, verification, messaging or notification delivery.
- Accepting a request bid records a **match**, not a confirmed booking. A property offer accepted by a host creates a `pending_payment` booking.
- Booking availability is checked for direct bookings but not fully synchronized across offers/bids. It is not safe to sell real inventory.
- No rate limiting, email verification, password reset, moderation, image uploads, full host verification, audit trail, or robust account recovery.
- Demo host credentials are public in the login screen and must be removed before wider public exposure.
- Dates/guest capacity are not used in homepage filtering beyond guest count.
- Property images are placeholders, not user uploads.
- Database is SQLite for local/demo use only; use PostgreSQL and migrations for persistent multi-user testing.
- The demo has no admin panel.

Do **not** accept real customer payments or publish real private customer information until these issues are addressed.
