"""Deliver approved RESEARCH-ONLY digest using existing Stock Analyst Telegram secrets.

Reuse TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / TELEGRAM_MESSAGE_THREAD_ID
already supported in the repository's daily-analysis workflow. Never print
tokens, chat IDs, response bodies, or URLs with embedded credentials.
No notification at all without --send and TELEGRAM_RESEARCH_SEND_ENABLED=true.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.research_alert_review import review_research_report
from src.telegram_research_digest import format_research_digest


def build_approved_digest(report):
    review = review_research_report(report)
    if not review["all_checked"]:
        raise ValueError("partial_review")
    return review, format_research_digest(review)


def send_via_telegram(message, *, token, chat_id, thread_id=None, opener=urlopen):
    if not token or not chat_id:
        raise ValueError("missing_telegram_configuration")
    # Plain text avoids markup injection and all links remain research citations.
    if len(message.encode("utf-16-le")) // 2 > 4096:
        raise ValueError("message_too_long")
    payload = {"chat_id": chat_id, "text": message,
               "disable_web_page_preview": "true"}
    if thread_id:
        if not str(thread_id).isdigit():
            raise ValueError("invalid_thread_id")
        payload["message_thread_id"] = str(thread_id)
    request = Request("https://api.telegram.org/bot" + token + "/sendMessage",
                      data=urlencode(payload).encode("utf-8"),
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      method="POST")
    try:
        with opener(request, timeout=12) as response:
            data = json.loads(response.read(2048))
    except Exception as exc:
        # Do not echo exceptions because they may contain the secret bot URL.
        raise RuntimeError("telegram_request_failed_" + type(exc).__name__) from None
    if data.get("ok") is not True:
        raise RuntimeError("telegram_delivery_not_confirmed")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--send", action="store_true", help="Requires explicit second opt-in")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    review, digest = build_approved_digest(report)
    print(json.dumps({
        "checked": review["checked"], "approved_research": len(review["accepted"]),
        "rejected": len(review["rejected"]), "mode": "RESEARCH_ONLY",
        "send_requested": args.send,
    }, ensure_ascii=False))
    if not args.send:
        print(digest)
        print("DRY_RUN_ONLY")
        return
    if os.getenv("TELEGRAM_RESEARCH_SEND_ENABLED", "").lower() != "true":
        raise RuntimeError("telegram_send_not_enabled")
    if not review["accepted"]:
        print("NO_APPROVED_RESEARCH_NOT_SENT")
        return
    send_via_telegram(
        digest,
        token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        thread_id=os.getenv("TELEGRAM_MESSAGE_THREAD_ID", ""),
    )
    print("TELEGRAM_RESEARCH_DELIVERY_CONFIRMED")


if __name__ == "__main__":
    main()
