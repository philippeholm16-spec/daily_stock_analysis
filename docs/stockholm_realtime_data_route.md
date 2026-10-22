# Nasdaq Stockholm REALTIME data: concrete route and licensing gate (2026-10-22)

## Summary

Stock Analyst can read historical prices and public quotes, but the current
unofficial Avanza MCP marks these quotes `isRealTime:false`. We cannot
upgrade them by taking a newer REST timestamp or by polling more often.

The low-cost **candidate** for authorized primary-market live verification
is **Interactive Brokers Nordic Equity Level 1** through its documented
TWS / IB Gateway API. This is NOT activated, purchased or logged in.
Our trading account may remain at Avanza; IBKR would be a separate data
service/account for the user's own bot.

Current official IBKR pricing lists Nordic Equity L1 at **EUR 2/month for
eligible nonprofessional customers**, EUR 40.50/month for professional
customers. Published eligibility conditions also say an **individual
account normally needs USD 500 (or equivalent) equity to activate market
data services** (capital in the IBKR account, not the monthly fee).
Additional exchange, account, classification or non-display usage fees may
apply; confirm from IBKR in account settings before purchase.

Official sources:

- https://www.interactivebrokers.com/en/pricing/market-data-pricing.php
- https://ibkrcampus.com/docs/general/market-data-subscriptions/market-data-subscription-minimum-equity-balance-requirements
- https://www.interactivebrokers.com/docs/tws-api/doc/md/streaming-data
- https://www.interactivebrokers.com/docs/tws-api/doc/md/live-ticks
- https://www.interactivebrokers.com/docs/tws-api/doc/md/component-exchanges
- https://www.ibkrguides.com/clientportal/usersettings/marketdatasubscriptions.htm

## Alternatives (not equivalent)

| Provider | Primary exchange XSTO? | API? | Notes |
| --- | --- | --- | --- |
| IBKR Nordic Equity L1 | Can get Nasdaq Nordic L1 with right subscription and exchange routing | TWS/Gateway/Web API | Low individual fee, account funding, data entitlements, local gateway |
| EODHD real-time EU WebSocket | **Not guaranteed**: sourced from Cboe Europe BXE/CXE/DXE | Yes, paid | Good secondary movement discovery; trade/quote venue may differ from Stockholm; 50 symbols by default |
| Millistream MDF/MWS | Nordic primary feeds available subject to rights | Yes, contractual | Request specific personal/non-display bot quote; not assumed affordable |
| Nordnet External API | Nordic real time through authenticated Public Feed | Yes, existing clients | Nordnet's docs say no onboarding for new API customers |
| TradingView Nasdaq OMX package | Real-time *display* | API reuse not demonstrated | $9.95/mo market data on TradingView, **not** automatically usable by our bot |
| Nasdaq Nordic Web API | Yes | Yes | Nasdaq price list indicates EUR 1,260/month access fee + usage licenses |
| EODHD ordinary Live REST | No (15–20 min delayed for equities) | Yes | Not suitable for executable intraday levels |

Additional sources:
- https://eodhd.com/financial-apis/new-real-time-data-api-websockets
- https://eodhd.com/financial-apis/live-ohlcv-stocks-api
- https://www.nordnet.se/externalapi/docs/getting_started
- https://millistream.com/index.php/api-widgets-trader/
- https://www.tradingview.com/data-coverage/
- https://www.nasdaq.com/products/data/equities/nordic-baltic
- https://www.nasdaq.com/docs/data/Nasdaq_European_Other_Markets_Data_Products_Price_List_September_2026

## How the new IBKR gate works

`src/ibkr_tws_quote_adapter.py` takes callback payloads from:
`EWrapper.marketDataType`, `tickByTickAllLast` and `tickByTickBidAsk`.
It never infers trade venue from a listing's MIC: IBKR SMART and Cboe data
may be valid prices on **another venue**.

`src/stockholm_realtime_quality.py` requires:

1. authenticated IBKR session and `marketDataType == 1` (not 2, 3, 4);
2. verified Nordic Equity L1 subscription and permitted bot analytics usage;
3. exact ISIN, ticker, positive conId and Swedish currency;
4. verified **XSTO** execution venue and direct-book mapping;
5. exchange trade timestamp within 60 seconds, bid/ask tick timestamp within
   15 seconds, ingestion timestamp within 10 seconds;
6. bid < ask, bounded spread and coherent last price;
7. observable not-halted status in Stockholm's regular trading window.

These are prerequisites to quote-quality acceptance. They do NOT prove all
other Stock Analyst strategy gates. No trade recommendations, orders or
licensed tick data are uploaded to GitHub Actions.

The initial real-time data readiness tests are pure offline Python,
requiring no account and charging no fee. They deliberately include negative
tests for stale feeds, "delayed" IBKR mode, Cboe trades, ambiguous share
classes, unconfirmed entitlements and closed trading.

## Local Mac diagnostic (requires your explicit setup)

After an eligible IBKR account + active permissions are available, install
IB Gateway or TWS **locally on Mac**, configure API socket to listen on
localhost with **Read-Only API** enabled, and install official `ibapi`.
Avoid exposing the local IB Gateway API port to the internet.

Run:

```sh
python -m scripts.ibkr_local_live_probe \
  --conid YOUR_VERIFIED_IBKR_CONID \
  --isin VERIFIED_ISIN \
  --symbol 'VERIFIED_TICKER' \
  --exchange-code VERIFIED_IBKR_PRIMARY_EXCHANGE
```

IBKR's `contractDetails` must uniquely match the contract. ISIN might not
be exposed by the provider for a specific contract: no automatic approval
is possible without verifying the conId/ISIN mapping upstream.

The diagnostic starts in **unapproved** mode. Only after independently
validating the specific Nasdaq venue mapping, data entitlement, bot usage
rights and source can those values be supplied with:

- `--confirm-exchange-map`
- `--confirm-live-entitlement`
- `--confirm-bot-analytics-rights`

These flags acknowledge outside facts; the script does NOT independently
authenticate a market-data legal license. The final app must persist a
verified provider/contract entitlement record, and the end user must review
permissions. IBKR ticks may be sparse for illiquid shares, which correctly
causes the quote gate to reject stale prices.

## Recommended final architecture

**Two stages, NOT continuous full-market tick-by-tick subscriptions:**

1. Scan all verified XSTO Large/Mid/Small Cap instrument IDs and news
   discovery on non-live historical data at controlled API rates.
2. Stock Analyst generates a preliminary short list; **IBKR Nordic L1
   real-time feed** continuously verifies the short list's quote and
   then recalculates entry, stop, target and risk based on the live bid/ask
   and sufficiently fresh bars. No alert without a fresh primary-market quote.
3. Feed into existing Telegram bot via a private local service only
   after the technical and data-quality gates pass; user trades manually
   at Avanza.
4. Track staleness, outages, entitlements, subscription limits and
   realized live results. We should measure paper performance over many
   trading sessions before treating scores as predictive.

**Critical:** GitHub Actions runners cannot directly connect to a Mac's
localhost IB Gateway. A local Mac process kept awake, or an authorized
private host with a safely configured gateway, will be required. Never put
broker login credentials in public Github files or expose gateway ports.

No access, payment, user account or live prices have been verified or
activated in this branch. `main` is unchanged.

## Integration completed in the separate feature branch

`src/stockholm_realtime_entry_recheck.py` combines an already accepted
primary XSTO quote with an independently verified `VERY_GOOD` technical
research setup. It **does not** simply copy the old entry price. It assumes
a buy at the *current offer/ask*, recalculates risk and reward **after the
current spread, commission and conservative slippage**, and rejects:

- delayed/frozen/non-Nasdaq/XSTO or bad timestamp feeds;
- OHLC reference bars older than 20 minutes or a live quote older than 60s;
- a live ask that moved over 1% from the analysis entry;
- a stop or observed resistance target invalidated by the new ask;
- an expected upside below 3%, net R/R below 2.0 or risk >1% of capital.

The output is `LIVE_QUOTE_REPRICED_FOR_HUMAN_RESEARCH`, not a buy order.
Even this valid result is NOT a verified strategy win probability or
entitlement to redistribute data in Telegram. It must remain behind the
independent pre-alert review and explicit user data-license approval.

**Operational next action is external to the code:** choose and activate an
authorized primary Nasdaq Nordic Level-1 API stream in the user's own
market-data account (or contract a licensed Nordic feed). No credentials,
market-data subscription, real quote, payment or order has been activated
by creating these files. CI uses fully synthetic signed-off provider event
fixtures and cannot prove access to IBKR in production.
