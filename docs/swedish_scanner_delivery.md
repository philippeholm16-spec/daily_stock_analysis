# Swedish daytrading research: delivery and coverage

## Status (feature branch only)

The existing Stock Analyst daily workflow already supports Telegram with
GitHub Secrets named `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optional
`TELEGRAM_MESSAGE_THREAD_ID` in environment `STOCK_LIST`. The new
`.github/workflows/stockholm-research-telegram.yml` reuses exactly those
names and does **not** require a second bot or chat ID.

The new pipeline collects read-only Placera headlines and three bounded
Google News RSS searches grouped around DI, Affärsvärlden, Börsvärlden, EFN,
Realtid, Aktiespararna, Privata Affärer, MFN and Cision. It performs up to 10
Avanza public stock searches, checks XSTO market identity, and ranks a
**research watchlist** based on headline catalysts, age, and turnover proxy.

It **does not** perform a full Nasdaq Stockholm universe scan. News RSS and
unofficial Avanza data cannot prove the completeness of Large/Mid/Small Cap.
Nasdaq's authoritative Nordic Equity Reference Data Files are entitlement
products. A legitimately accessible complete listing feed, with dated
provenance and AVANZA-ID mapping, is required for a claim of full coverage.

To audit supplied authorized files:
`python -m scripts.audit_stockholm_universe --reference reference.json --mapping mapping.json`
The audit fails with exit code 2 on any missing or mismatched ISIN/ticker,
order-book ID conflict, or stale/non-independent reference. Provider
attestations must be independently checked by the operator.

## Google news vs Google Search API

This phase uses publicly available **Google News RSS search feeds**, not
Google's ordinary Search API or a licensed DI/Direkt/Finwire full-content feed.
Only titles, links and timestamps are ingested: no paywall bypass or article
body scraping. Google News RSS is not a guaranteed, officially documented
long-term feed. The base Stock Analyst project already supports SerpAPI,
Tavily, Brave, and SearXNG when separately configured in the existing
`src/search_service.py`; those keys are not assumed or consumed by this
isolated scanner.

## Review before Telegram

Every candidate must pass `src/research_alert_review.py`; the external
Telegram message explicitly says RESEARCH, not a buy/sell signal, and notes
that the prices can be delayed. A separate stricter gate
`src/proposal_independent_review.py` rejects any trading proposal without
fresh authorized real-time quotes, verified issuer ISIN, full coverage,
valid prices, and net risk/reward >= 2.0, with risk <= 1% of capital.
This is deterministic validation, not a second AI's judgment.

The branch workflow runs **dry-run by default**, archives the findings as a
GitHub Actions artifact for three days, and only sends when an explicit
`workflow_dispatch.send_telegram=true` is issued after the workflow file
is on the repository default branch. The one-time smoke delivery was
completed successfully, and its branch-push trigger has been disabled.
The prepared weekday schedule at 08:00 Europe/Stockholm is dormant until
approved for the default branch. All sends require both secrets,
are plain-text, and do not transmit any private trading-account data.
Do not merge or change `main` without the owner's approval.

The current `.github/workflows/pr-review.yml` checks **code** via a
separate manually triggered review; it does not approve securities tips.
The per-candidate validation above runs automatically inside the research
workflow.
