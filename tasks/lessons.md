# Lessons

- Vercel MCP `create_git_project` can 409-create a project name without GitHub being installed on the team. `list_projects` then returns empty and deploys 403 if the Grok Vercel login is not Owner/Admin. Do not keep creating extra project names. Have the user Import GitHub in the Vercel dashboard.
- FastAPI + Pinecone + pandas + Streamlit will not boot as a Vercel Python function. Guest live site uses `api/demo_api.py` (local list + optional Grok notes). `start_api.bat` remains the full Grok/Pinecone server.
- SMTP_PASSWORD cannot be invented. Google Workspace at jonathan@agenthaus.io needs an App Password; without it, email writes `data/outbox/`.
- Never commit `.env`. Copy keys into Vercel project env (Production + Preview).
- Vercel CLI 59+ with `"framework": null` plus `"functions": { "api/index.py": ... }` fails: unmatched function pattern. FastAPI preset does not treat `/api/*.py` as old-style functions. Use `"framework": "fastapi"` and a supported entrypoint (`index.py` / `app.py` / `main.py` at repo root, or `src/` / `app/`). Drop catch-all rewrites. Do not chase `runtime.txt` until that pattern error is gone.
- Guest recs fail when ingest paints Sancerre blanc as red (default style is red if the label has no grape word). Named appellations (Sancerre, Barolo, Champagne, Riesling) must lock color/grape or catalog order dumps Opus/Monte Bello.
- Do not skip list rows on the substring `series` (kills Yalumba The Y Series). Skip `range` / `selections` / mixed-color mash-ups. `Rangen` is a vineyard, not a range.
- Cellar is a price floor. Never relax it to a $20 Pinot Gris. One honest $400 bottle beats two cheap fillers.
- Food chips must not overwrite a tapped color. Champagne + steak stays Champagne; White + steak stays rich white.
- If the guest names a class that is not on the list (Grand Cru Burgundy), return empty. Never pad with 1er Cru, village Burgundy, or New World. Super Tuscan must stay on Sassicaia/Tignanello/Ornellaia — never Caymus or Zin.
- Do not keep a second Vercel project named `jarvis` next to `jarvis_sommelier`. Live domain is jarvis_sommelier.
- Guest Grok does not pick bottles — it only writes notes after the ranker. Typed country/region (Italian, French, Piedmont) must lock in `parse_intent` or default lean whites dump Chablis. Grok will happily invent "goes with Italian food" for a Burgundy if you let a French bottle through.
- Named grape must lock both bottles. "Sangiovese" is Chianti / Brunello / Vino Nobile / Flaccianello / Tignanello — never Pinot as the "also" pour. Complementary different-grape is wrong once they named a grape.
- Old World / New World is geography, not a synonym. Syrah old world = Rhône. If this list has no Rhône Syrah, empty — never Barossa Shiraz. Grok only picks from wines that already passed that filter.
- `grape_family` must test Cabernet before "sauvignon" or Cabernet Sauvignon is tagged Sauvignon Blanc. Sancerre rouge is Pinot, not Sauvignon. Bare "pinot" = Pinot Noir. Menu copy ("french onion") must not lock country.
