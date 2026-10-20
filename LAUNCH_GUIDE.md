# Meyzban deployment and launch gate

## Current status: STAGING ONLY, NOT SAFE FOR REAL BOOKINGS OR PAYMENTS
This repository is a Flask/SQLite prototype with security and staging improvements. It does not implement payment provider integration, real host payouts, verified identity, durable production storage, email verification, rate limits, full inventory concurrency across all flows, or admin operations. Do not onboard real customers or accept money.

## Test locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY=$(python -c 'import secrets;print(secrets.token_hex(32))')
export MEYZBAN_ENV=development
python -m unittest discover -s tests -v
python app.py
```
Visit http://localhost:5000. To load sample listings for local development only, set SEED_DEMO=1 on a fresh database.

## Host staging without a custom domain
1. Create a private GitHub repository and push the unzipped project contents.
2. Create a Render web service connected to the repository.
3. Use `pip install -r requirements.txt` and `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1`.
4. Configure `MEYZBAN_ENV=production`, `SECRET_KEY` as a random 64-character hex string, and `SEED_DEMO=0`.
5. Use a **persistent disk** for the SQLite database and set `DATABASE_PATH` to its mounted path. Without it, records can disappear on deploy. This is only for restricted staging; SQLite is not the intended production database.
6. Open the generated `.onrender.com` URL and test all user flows with dummy data.
7. Restrict public access during testing and never use actual payment credentials in this build.

## Before public market launch
- Migrate to managed PostgreSQL, transactional migrations and row-level locks.
- Integrate an approved payment provider with verified webhooks, idempotency, refunds, reconciliation and permitted marketplace payouts.
- Implement financial double-entry ledger and host settlement controls.
- Implement account email verification, password reset, MFA for admin, rate limits and admin moderation.
- Add property photos/uploads, verification and availability/offer/bid inventory enforcement.
- Build and pass unit, integration, E2E, load and security tests; run a backup restoration drill.
- Establish terms, privacy policy, cancellations, dispute policy, tax and payout compliance.
- Perform provider sandbox certification and controlled live transaction pilot before general availability.
