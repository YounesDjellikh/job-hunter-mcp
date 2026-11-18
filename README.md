# Job Hunter MCP

**Let Claude help you find work and keep track of every application, in the UK and across Europe.**

Job Hunter is an [MCP](https://modelcontextprotocol.io) server. Plug it into Claude Desktop, Claude Code or any MCP client, and you can just say:

> *"Find temporary jobs near me in logistics."*
>
> *"Add the one I applied to, to my tracker."*
>
> *"Any replies in my inbox?"*

It has three jobs:

| | What it does |
|---|---|
| 🔎 **Search** | Searches **Reed** (UK) and **Adzuna** (UK + 9 European countries) through their official free APIs. It filters out self-employed, freelance and commission-only roles (in 7 languages), low pay, permanent jobs (optional), duplicates and employers you've already applied to. |
| 📋 **Track** | Keeps a local database of applications and exports a **colour-coded Excel sheet**: 🟦 blue = found, not applied · 🟩 green = applied / interview / offer · 🟥 red = rejected · ⬜ grey = withdrawn. |
| 📬 **Inbox** | Reads your Gmail **read-only**, flags **rejections, interview/assessment invites, offers, acknowledgements and scams** (like fake "loan approved" emails) in **8 languages**, and matches them to the employers you're tracking. |

Everything stays on your computer. Nothing is sent, deleted or applied for on your behalf.

---

## Tools

| Tool | Purpose |
|---|---|
| `search_jobs` | Search Reed and Adzuna. Arguments: keywords, location, **country**, distance (miles or km), temp-only, minimum hourly pay, and whether to hide employers you already track. |
| `track_application` | Add a job with status `saved`, `applied`, `viewed`, `interview`, `offer`, `rejected` or `withdrawn`. |
| `update_application` | Change the status and add a dated note. |
| `list_applications` | See everything, or filter by status, with counts. |
| `remove_application` | Delete a duplicate. |
| `export_tracker` | Write the colour-coded `.xlsx`. It's rebuilt fresh every time, so links never end up on the wrong row. |
| `check_inbox` | Classify recent emails and match them to applications. Optionally apply the status changes automatically (`apply_updates=true`). |

---

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/YounesDjellikh/job-hunter-mcp.git
cd job-hunter-mcp
pip install -e ".[gmail]"      # drop [gmail] if you don't want the inbox check
```

### 1. Get free API keys

- **Reed**: https://www.reed.co.uk/developers/jobseeker (instant, free)
- **Adzuna**: https://developer.adzuna.com/ (free app id + key)

You only need one of them. The more you add, the more jobs you'll see.

### 2. Configure

```bash
mkdir -p ~/.job-hunter
cp config.example.yaml ~/.job-hunter/config.yaml
```

Edit `~/.job-hunter/config.yaml` with your default location, filters and (optionally) keys. Or keep keys out of files completely with environment variables: `REED_API_KEY`, `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.

### 3. Connect it to Claude

**Claude Desktop**: add this to `claude_desktop_config.json` (see `examples/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "job-hunter": {
      "command": "job-hunter-mcp",
      "env": { "REED_API_KEY": "your-key" }
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add job-hunter -e REED_API_KEY=your-key -- job-hunter-mcp
```

Restart Claude and ask it to search for jobs.

---

## 🇪🇺 Using it outside the UK

| Country | Code | Job sources | Currency |
|---|---|---|---|
| 🇬🇧 United Kingdom | `gb` | Reed + Adzuna | GBP |
| 🇫🇷 France | `fr` | Adzuna | EUR |
| 🇩🇪 Germany | `de` | Adzuna | EUR |
| 🇪🇸 Spain | `es` | Adzuna | EUR |
| 🇮🇹 Italy | `it` | Adzuna | EUR |
| 🇳🇱 Netherlands | `nl` | Adzuna | EUR |
| 🇧🇪 Belgium | `be` | Adzuna | EUR |
| 🇦🇹 Austria | `at` | Adzuna | EUR |
| 🇨🇭 Switzerland | `ch` | Adzuna | CHF |
| 🇵🇱 Poland | `pl` | Adzuna | PLN |

1. Get a free **Adzuna** key (Reed is UK-only).
2. In `config.yaml`, set `search.country`, `search.location` and `search.distance_km`. There are ready-made examples in `examples/config.france.yaml` and `examples/config.germany.yaml`.
3. Search with local-language keywords for the best results: *"préparateur de commandes"*, *"Lagerhelfer"*, *"mozo de almacén"*, *"magazziniere"*, *"orderpicker"*, *"magazynier"*.
4. You can switch country for a single search: *"search_jobs: keywords='Lagerhelfer', location='Hamburg', country='de'"*.

**Email checks understand** English, French, German, Spanish, Italian, Dutch, Polish and Portuguese. For example, *"Malheureusement…"*, *"Leider…"*, *"Lamentablemente…"*, *"Purtroppo…"*, *"Helaas…"* and *"Niestety…"* are all recognised as rejections. A job advert that mentions a "permanent contract" is **not** mistaken for a job offer.

**Self-employment filter**: by default it drops roles mentioning *auto-entrepreneur, indépendant, selbstständig, Freiberufler, autónomo, partita IVA, ZZP, samozatrudnienie* and their equivalents.

---

## Gmail setup (optional)

The inbox check uses **your own** Google OAuth client with the **read-only** scope (`gmail.readonly`).

1. Go to https://console.cloud.google.com/, create a project, and enable the **Gmail API**.
2. Under *APIs & Services → OAuth consent screen*, choose **External** and add yourself as a **test user**.
3. Under *Credentials → Create credentials → OAuth client ID*, choose **Desktop app**. Download the JSON.
4. Save it as `~/.job-hunter/credentials.json`.
5. The first time you run `check_inbox`, a browser window asks you to approve read-only access. The token is saved to `~/.job-hunter/token.json`.

Revoke access at any time at https://myaccount.google.com/permissions.

---

## Good to know

- **Official APIs only.** No scraping, no logging into job boards with your password, no auto-applying. You still submit every application yourself. The agent finds and tracks.
- **Your data is local.** The tracker lives in `~/.job-hunter/tracker.db`. `config.yaml`, `credentials.json`, `token.json`, `*.db` and `*.xlsx` are git-ignored, so they can't be committed by accident.
- **Email classification is keyword-based**, so check anything important yourself. Recruiters word rejections in creative ways ("we won't be moving forward", "on this occasion…"). If one slips through, add the phrase to `RULES` in `gmail.py` and open a PR.
- **Self-employed roles are hidden by default** via `exclude_keywords`. Remove those keywords in `config.yaml` if you want to see them.

## Development

```bash
pip install -e ".[dev,gmail]"
pytest
```

PRs welcome, especially:
- **new job sources** with official APIs, e.g. France Travail (France), Bundesagentur für Arbeit (Germany), Totaljobs and CV-Library (UK);
- **more countries and languages**;
- **better email rules**: if a real rejection or invite slipped through, add the phrase to `RULES` in `gmail.py`, with a test.

## License

MIT © 2026 Younes Djellikh
