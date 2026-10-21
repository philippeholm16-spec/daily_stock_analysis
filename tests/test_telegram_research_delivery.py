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
        "fetched_at_utc": NOW.isoformat(), "capital_sek": 15000,
        "research_candidates": [{
            "isin": "SE0003849223", "ticker": "BULTEN", "mic": "XSTO",
            "headline": "Bulten ökar rörelseresultatet", "source": "Placera",
            "published_at": (NOW - timedelta(hours=1)).isoformat(),
            "news_url": "https://www.placera.se/nyheter/bulten",
            "catalysts": ["report"], "discovery_priority": 7,
            "last_price": 75.8,
            "actionable": False, "trade_signal": None,
            "publisher_isin_confirmed": False, "timestamp_verified": False,
            "stock_analyst": {
                "engine": "Stock Analyst Sweden / independent technical v1",
                "status": "ANALYZED_INDICATIVE_SETUP",
                "score": 84, "quality": "Hög teknisk styrka",
                "potential_quality": "Hög teknisk affärspotential",
                "why": ["Stigande kurs jämfört med glidande medelvärde",
                        "Relativ volym 1,7 gånger"],
                "risks": ["Historisk kurs är inte realtidsverifierad"],
                "entry_price": 75.8, "lowest_sell_point": 74.0,
                "sell_point": 82.0, "potential_pct": round((82 / 75.8 - 1)*100, 2),
                "net_rr": 3.2, "max_risk_sek": 52, "quantity": 26,
                "levels_status": "ENDAST_PRELIMINÄRT_SCENARIO",
                "actionable": False, "data_verified_real_time": False,
                "source_news_opinion_used": False,
            },
        }],
    }


def test_approved_report_generates_delayed_research_disclaimer():
    reviewed, digest = build_approved_digest(report())
    assert reviewed["checked"] == 1 and reviewed["all_checked"]
    assert "INTE KÖPREKOMMENDATION" in digest
    assert "BULTEN" in digest and "75.80" in digest
    assert "Stop-loss" in digest and "74.00 kr" in digest
    assert "Målkurs" in digest and "82.00 kr" in digest
    assert "Potential" in digest and "8.18 %" in digest
    assert "VARFÖR" in digest
    assert "84/100" in digest
    assert "Affärspotential: Hög teknisk affärspotential" in digest
    assert "Bevakningspoäng 7/10" in digest


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

def test_independent_stock_analyst_score_not_press_priority():
    data = report()
    data["research_candidates"][0]["discovery_priority"] = 0
    _, digest = build_approved_digest(data)
    assert "84/100" not in digest
    assert "BULTEN" not in digest


def test_missing_analysis_yields_no_telegram_tip():
    data = report()
    data["research_candidates"][0].pop("stock_analyst")
    reviewed, digest = build_approved_digest(data)
    assert not reviewed["accepted"]
    assert "BULTEN" not in digest


def test_score_equal_to_six_produces_no_alert():
    data = report()
    data["research_candidates"][0]["discovery_priority"] = 6
    reviewed, digest = build_approved_digest(data)
    assert reviewed["checked"] == 1
    assert reviewed["reviewed_and_valid"] == 1
    assert reviewed["alert_count"] == 0
    assert "BULTEN" not in digest


def test_score_above_six_alerts_despite_no_setup():
    data = report()
    data["research_candidates"][0]["discovery_priority"] = 7
    a = data["research_candidates"][0]["stock_analyst"]
    a["status"] = "ANALYZED_NO_VALID_SETUP"
    for key in ("entry_price", "lowest_sell_point", "sell_point", "potential_pct"):
        a[key] = None
    reviewed, digest = build_approved_digest(data)
    assert reviewed["alert_count"] == 1
    assert "Ej fastställd" in digest
    assert "Stock Analysts egna bedömning" in digest


def test_threshold_rejects_nonreviewed_high_score():
    data = report()
    data["research_candidates"][0]["discovery_priority"] = 9
    data["research_candidates"][0].pop("stock_analyst")
    reviewed, digest = build_approved_digest(data)
    assert reviewed["alert_count"] == 0
    assert "BULTEN" not in digest
