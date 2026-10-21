"""Independent very-good Stock Analyst alerts, no live Telegram requests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs
import pytest

from scripts.telegram_research_delivery import build_approved_digest, send_via_telegram


NOW = datetime.now(timezone.utc)


def report():
    return {
        "trade_signals_enabled": False,
        "actionable_count": 0,
        "fetched_at_utc": NOW.isoformat(),
        "capital_sek": 15000,
        "research_candidates": [{
            "isin": "SE0003849223", "ticker": "BULTEN", "mic": "XSTO",
            "headline": "Bulten ökar rörelseresultatet", "source": "Placera",
            "published_at": (NOW - timedelta(hours=1)).isoformat(),
            "news_url": "https://www.placera.se/nyheter/bulten",
            "catalysts": ["report"],
            "discovery_priority": 0,  # press/newspaper score is IRRELEVANT
            "last_price": 75.8, "spread_pct": 0.12,
            "actionable": False, "trade_signal": None,
            "publisher_isin_confirmed": False, "timestamp_verified": False,
            "stock_analyst": {
                "engine": "Stock Analyst Sweden / independent technical v1",
                "status": "ANALYZED_INDICATIVE_SETUP",
                "opportunity_grade": "VERY_GOOD",
                "score": 90, "quality": "Hög teknisk styrka",
                "potential_quality": "Mycket god preliminär teknisk potential",
                "why": ["Stigande kurs jämfört med 20-stapels medelvärde",
                        "Förhöjd handelsvolym"],
                "risks": ["Kursdata inte realtidsverifierad"],
                "entry_price": 75.8, "lowest_sell_point": 74.0,
                "sell_point": 82.0,
                "potential_pct": round((82 / 75.8 - 1)*100, 2),
                "net_rr": 3.2, "max_risk_sek": 52, "quantity": 26,
                "resistance_touches": 3,
                "relative_volume_vs_prior20": 1.8,
                "chart_as_of": NOW.isoformat(),
                "levels_status": "ENDAST_PRELIMINÄRT_SCENARIO",
                "actionable": False, "data_verified_real_time": False,
                "source_news_opinion_used": False,
            },
        }],
    }


def test_very_good_alert_includes_entry_stop_target_potential_and_reasons():
    review, digest = build_approved_digest(report())
    assert review["alert_count"] == 1
    assert "BULTEN" in digest and "90/100" in digest
    assert "Affärspotential: Mycket god" in digest
    assert "74.00 kr" in digest and "82.00 kr" in digest
    assert "8.18 %" in digest and "VARFÖR" in digest
    assert "INTE KÖPREKOMMENDATION" in digest


def test_low_discovery_priority_does_not_block_very_good_stock_analyst():
    data = report()
    data["research_candidates"][0]["discovery_priority"] = 0
    review, digest = build_approved_digest(data)
    assert review["alert_count"] == 1
    assert "BULTEN" in digest


def test_high_discovery_priority_cannot_force_unapproved_setup():
    data = report()
    data["research_candidates"][0]["discovery_priority"] = 10
    analysis = data["research_candidates"][0]["stock_analyst"]
    analysis.update({
        "status": "ANALYZED_NO_VALID_SETUP", "opportunity_grade": "NONE",
        "lowest_sell_point": None, "sell_point": None,
        "potential_pct": None, "entry_price": None,
    })
    review, digest = build_approved_digest(data)
    assert review["alert_count"] == 0
    assert "BULTEN" not in digest


def test_score_below_85_cannot_alert():
    data = report()
    data["research_candidates"][0]["stock_analyst"]["score"] = 84
    review, digest = build_approved_digest(data)
    assert not review["accepted"] and "BULTEN" not in digest


def test_lower_opportunity_grade_cannot_alert_even_with_100_score():
    data = report()
    a = data["research_candidates"][0]["stock_analyst"]
    a["score"] = 100
    a["opportunity_grade"] = "WATCH_ONLY"
    review, digest = build_approved_digest(data)
    assert not review["accepted"] and "BULTEN" not in digest


def test_no_unreviewed_idea_can_be_sent():
    data = report()
    data["research_candidates"][0].pop("stock_analyst")
    review, digest = build_approved_digest(data)
    assert review["alert_count"] == 0 and "BULTEN" not in digest


def test_newsroom_opinion_never_impacts_stock_analyst_rating():
    original = report()
    changed = deepcopy(original)
    changed["research_candidates"][0]["source"] = "Dagens industri"
    changed["research_candidates"][0]["headline"] = "Bulten ser dyr ut"
    changed["research_candidates"][0]["discovery_priority"] = 10
    x, _ = build_approved_digest(original)
    y, _ = build_approved_digest(changed)
    assert x["alert_count"] == y["alert_count"] == 1


def test_duplicate_share_class_not_alerted_twice():
    data = report()
    copy = deepcopy(data["research_candidates"][0])
    copy["news_url"] = "https://www.placera.se/nyheter/second"
    data["research_candidates"].append(copy)
    approved, _ = build_approved_digest(data)
    assert approved["reviewed_and_valid"] == 2
    assert approved["alert_count"] == 1


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
    request, timeout = captured[0]
    fields = parse_qs(request.data.decode())
    assert request.full_url.endswith("/botexample-token/sendMessage")
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
