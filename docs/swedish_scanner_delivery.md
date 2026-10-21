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
Avanza public stock searches and verifies XSTO identity. The publisher/news
discovery priority is **only a queue for deciding which stocks to inspect**.
Every verified discovered stock is independently evaluated by
`src/stockholm_stock_analyst.py` from available OHLC price/volume bars, with
momentum, moving average, relative volume, spread and turnover checks.
Publisher buy/sell opinions never enter that score. Ranking in Telegram uses
ONLY this independent technical score, not the source discovery priority.
The base Stock Analyst engine's original foreign-market code-paths are not
yet fully compatible with Nasdaq Stockholm; this new independent Sweden
technical adapter is not falsely presented as the complete original AI report.

**Telegram now presents:** Stock Analyst technical strength /100, separate
trade opportunity status, last observed price, stop-loss ("lowest sell point"),
resistance target ("sell point"), theoretical upside in percent, net
risk/reward, and independently calculated reasons and risks. When technical
history cannot support a target with minimum net R/R 2.0 after trading costs
at <=1% portfolio risk, levels are explicitly "Ej fastställd", not fabricated.
Any displayed levels are hypothetical scenarios with delayed/unauthorized
quote latency; they never constitute ready-to-execute trade signals.

Capital is configurable with GitHub repository variable
`STOCKHOLM_TRADING_CAPITAL_SEK` (between SEK 10,000 and 25,000; default
SEK 15,000). Each stock is analyzed regardless of whether its history
is available; missing history produces ANALYSIS_UNAVAILABLE, never a fake
recommendation.

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

Every candidate must pass `src/research_alert_review.py`; this now requires
a completed, explicitly unavailable, or rejected independent Stock Analyst
evaluation **for every discovered and verified ticker**. It checks coherence of
risk, stop, target and potential independently of news. The Telegram message
explicitly says RESEARCH, not a buy/sell signal, and notes that prices may
be delayed. A separate stricter gate
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
