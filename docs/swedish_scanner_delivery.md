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


## Development update: independent VERY_GOOD alerts and historical evaluation

**Telegram eligibility has been corrected:** Newspaper discovery priority does
not influence alert qualification or ranking. The alert filter uses ONLY the
independent Stock Analyst opportunity grade `VERY_GOOD`, an independently
reviewed valid indicative stop and resistance target, score at least 85/100,
net R/R at least 2.0 and projected target upside at least 3%. No alerts are
sent when no stock meets these requirements. This is technical *scenario*
potential, not an empirically validated forecast or an actionable order.

The technical model now derives stop levels from recent observed support and
a volatility (ATR14) buffer. Targets must be repeated observed historical
resistance; isolated high-price spikes are rejected. An observed resistance
may still be too close to reach R/R >= 2, in which case no setup is approved.
The model additionally requires recent enough candles, favorable relative
volume, low spread and close/chart coherence before assigning VERY_GOOD.

The pre-alert independent review verifies the technical parameters, chart age,
quote/entry agreement, RR and 1% capital risk. The news article discovery
priority can be 0 or 10 without changing Stock Analyst's own decision.

`src/stockholm_walkforward.py` provides a leakage-free historical replay:
historical bars are processed in chronological order, future bars are used
**only after** a frozen entry/stop/target decision, and ties within a candle
are treated as stop-loss rather than favorable target fills. It records net R,
outcome, sample count, win rate and drawdown, with conservative assumed costs
and gaps. This is not a substitute for out-of-sample live validation.

**Actual exploratory pilot:** the read-only Bulten one-week chart retrieved
from Avanza MCP contained 233 candles. The historical study evaluated 15
non-overlapping windows and identified **zero** VERY_GOOD setups. Therefore
this single-week sample does not yield a measurable win rate or justify claims
of prediction accuracy; it does verify the complete historical data path.

To progress past news-only discovery, the newly implemented
`src/stockholm_universe_batch.py` and
`scripts/stockholm_market_batch_research.py` can balance a verified,
authorized whole-market reference across Large/Mid/Small Cap and scan a
maximum of 12 independently mapped equities per run. Exact ISIN/XSTO/share
identity is checked on each provider call. Missing charts yield explicitly
unavailable analysis. **This is a scanner infrastructure milestone only**:
no complete independent and current licensed XSTO reference has been supplied
or verified, so no full-market sweep has occurred.

**Activation status:** `main` was not modified, and automatic Telegram
notifications remain dormant. The previously tested Telegram chat credentials
remain in GitHub Secrets. No payments, subscription, login or order flow is
used by the development workflows.

Before production activation, verify authorized universe data, data
freshness/entitlements, acceptable API rate limits, realistic execution costs,
and a substantially larger cross-stock out-of-sample evaluation.
