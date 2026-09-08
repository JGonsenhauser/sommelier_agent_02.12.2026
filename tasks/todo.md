# Product review → improvement plan

Reviewed 2026-09-04. Implemented P0 + P1 in this session.

## P0 — dining-room ready

- [x] One guest client: FastAPI + `mobile/index.html`. Streamlit is staff/kiosk only
- [x] One QR: `/?r={restaurant_id}` (PWA reads it)
- [x] Brand as the property (MAASS logo/name). Jarvis as a quiet credit
- [x] Price chips match the list (Under $75 / $75–$150 / $150–$250 / Cellar)
- [x] Replace `alert()`; iOS safe-area / `100dvh`; no autofocus keyboard
- [x] Wine-aware ranker + constraint relaxation (xAI has no embeddings API)
- [x] Sommelier prompt: why-for-you, two complementary bottles, no invented prices, no roast chicken
- [x] Pair from tonight’s menu; omit if not on the menu
- [x] Strip `score` / `processing_time` from guest JSON

## P1 — CRM + luxury

- [x] Email these wines (no account): send or hold in outbox + log lead
- [x] Append-only recommendation events for admin
- [x] Admin login + report at `/admin` (scores only here)
- [x] Menu-aware food cues; tasting-card results
- [x] Rate-limit recommend; CORS allowlist; no 500 leak; POST-only recommend

## P2 — later

- [ ] Restaurant table instead of hardcoded `maass` registry
- [x] Tenant-scoped cache keys
- [ ] Hotel: property vs outlet, glass vs bottle

## Review

Guest PWA, engine, API, CRM, and admin landed. Live recommend path was not exercised here (no `.env` in this worktree; pandas/python.exe blocked by Windows policy). Smoke covered config, menu, CRM, mail body, and HTML contracts (`tasks/_smoke.py`).
