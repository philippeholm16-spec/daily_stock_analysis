# Avanza MCP -> Swedish Trading Bot: data-only test

This opt-in diagnostic calls the real upstream `get_stock_quote` MCP tool
through FastMCP's in-process client and writes a JSON file. It does **not**
use an Avanza login, place orders, send Telegram messages, or generate signals.

Upstream: https://github.com/AnteWall/avanza-mcp (unofficial).
Market-data usage rights, real-time status, timestamp units and full
Nasdaq Stockholm coverage are **not verified**. Do not use for live trades.

## Run manually (Python 3.12+)

In a separate environment (do not change the existing bot dependencies):

```bash
python3.12 -m venv .venv-avanza
source .venv-avanza/bin/activate
python -m pip install 'avanza-mcp'
python -m scripts.avanza_mcp_bridge --order-book-id YOUR_VERIFIED_NUMERIC_ID
```

Find an order-book ID with the upstream `search_instruments` tool.
Do not substitute a ticker or guess an ID. The resulting
`avanza_diagnostic.json` is intentionally **non-actionable** even when
`isRealTime` is true: upstream timestamp units, venue/ISIN/share class,
market coverage, quote staleness and bid/ask remain to be independently
validated before integration with `src/swedish_market_scanner.py`.

This diagnostic is deliberately **not** scheduled in GitHub Actions.
No unattended polling of Avanza is enabled. Check permission from Avanza
before using an automated recurring feed.
