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

## Live launch (2026-09-08)

- [x] Compress brand-logo.png (1.13MB → 150KB, 512px)
- [x] Push `main` to GitHub (`6b2b427`) — https://github.com/JGonsenhauser/sommelier_agent_02.12.2026
- [x] Production API via local venv + `.env` (Grok + Pinecone, 273 wines). QR target `https://jarvis.agenthaus.io/?r=maass`
- [x] SMTP from `jonathan@agenthaus.io` (password still empty — needs Google App Password)
- [ ] Vercel: import the GitHub repo as project `jarvis`, attach domain `jarvis.agenthaus.io`, paste env vars. MCP can create the empty project name but this Grok Vercel login cannot deploy (403) and GitHub is not linked.

## Sommelier reasoning (2026-09-08)

Typed language a Master Sommelier would never violate:

- [ ] Old World / New World is a hard geographic lock (Syrah old world ≠ Barossa Shiraz)
- [ ] If the classic home is not on the list, say so — do not substitute the other hemisphere
- [ ] Grok picks from the filtered shortlist (cannot invent or relocate a bottle)
- [ ] Re-audit typed sommelier phrases; agents review; deploy

## Rec quality audit (2026-09-08)

Four sommelier agents reviewed 207 chip/query combos. Ranker + ingest now lock named grapes/appellations, color Sancerre/Xarel·lo correctly, keep Champagne on Champagne AOC, and never pad Cellar with cheap bottles.

- [x] Enumerate chips × body × profile × food × typed queries (`tasks/_audit_recs.py`)
- [x] White/crisp, red/body, food, and catalog-hole agent reviews
- [x] Named lock: Sancerre, Barolo, Chardonnay, Riesling, Champagne, Cabernet, Pinot Noir
- [x] Ingest: skip dual-SKU/range/selections; keep Y Series; `$350+`; Geyserville = Zin
- [x] Re-audit: 207 queries, 0 ranker fails (off-dry empties are list holes)

### Review

Fruity white → Eden Valley Riesling. Oaky French Chardonnay → Leflaive Puligny + Roulot Meursault. Dry & crisp → Chablis + Sancerre. Champagne + crisp → Blanc de Blancs. Red + crisp → Sancerre rouge + Eyrie Pinot. Cellar white → Clos Sainte Hune + Krug. Off-dry red/rosé/Champagne stay empty when the list has no honest bottle.
