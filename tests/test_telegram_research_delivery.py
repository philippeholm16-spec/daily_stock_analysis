"""Tests for native Stock Analyst Telegram research delivery, no network."""
from datetime import datetime, timedelta, timezone
import io
import json
from urllib.parse import parse_qs

import pytest
from src.research_alert_review import review_research_report
from scripts.telegram_research_delivery import build_approved_digest, send_via_telegram


NOW = datetime.now(timezone.utc)


def report():
    return {
        "trade_signals_enabled": False, "actionable_count": 0,
        "fetched_at_utc": NOW.isoformat(),
        "research_candidates": [{
            "isin": "SE0003849223", "ticker": "BULTEN", "mic": "XSTO",
            "headline": "Bulten ökar rörelseresultatet", "source": "Placera",
            "published_at": (NOW - timedelta(hours=1)).isoformat(),
            "news_url": "https://www.placera.se/nyheter/bulten",
            "catalysts": ["report"], "research_score": 6,
            "last_price": 75.8,
            "actionable": False, "trade_signal": None,
            "publisher_isin_confirmed": False, "timestamp_verified": False,
        }],
    }


def test_approved_report_generates_delayed_research_disclaimer():
    reviewed, digest = build_approved_digest(report())
    assert reviewed["checked"] == 1 and reviewed["all_checked"]
    assert "INTE KÖPREKOMMENDATION" in digest
    assert "BULTEN" in digest and "75.80" in digest


def test_fake_trade_signal_blocks_delivery():
    data = report()
    data["research_candidates"][0]["trade_signal"] = {"buy": 75.8}
    review, digest = build_approved_digest(data)
    assert review["rejected"] and "BULTEN" not in digest


def test_send_reuses_existing_secrets_but_never_logs_them():
    captured = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, _):
            return b'{"ok":true}'
    def opener(request, timeout):
        captured.append((request, timeout))
        return Response()
    assert send_via_telegram("RESEARCH ONLY", token="example-token",
                             chat_id="example-chat", opener=opener)
    req, timeout = captured[0]
    fields = parse_qs(req.data.decode())
    assert req.full_url.endswith("/botexample-token/sendMessage")
    assert fields["chat_id"] == ["example-chat"]
    assert fields["text"] == ["RESEARCH ONLY"]
    assert timeout == 12


def test_long_message_rejected():
    with pytest.raises(ValueError, match="message_too_long"):
        send_via_telegram("😀" * 3000, token="t", chat_id="c",
                          opener=lambda *args, **kwargs: None)


def test_network_fail_never_exposes_secret():
    def failure(*args, **kwargs):
        raise RuntimeError("secret-token-in-exception")
    with pytest.raises(RuntimeError, match="telegram_request_failed_RuntimeError") as error:
        send_via_telegram("test", token="super_secret_abc", chat_id="x",
                          opener=failure)
    assert "super_secret_abc" not in str(error.value)
