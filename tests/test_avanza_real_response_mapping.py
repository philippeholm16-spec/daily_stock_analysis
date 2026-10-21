"""Tests for actual Avanza MCP quote numeric types, no external requests."""
import unittest

from scripts.avanza_mcp_bridge import normalize_quote
from src.avanza_mcp_adapter import parse_public_quote, AvanzaDataError


class RealQuoteMappingTests(unittest.TestCase):
    def test_real_response_volume_float_is_supported(self):
        raw = {"last": 320.5, "totalVolumeTraded": 1049844.0,
               "isRealTime": False, "updated": 1792596160503}
        quote = parse_public_quote(normalize_quote(raw), order_book_id="5269")
        self.assertEqual(quote.price, 320.5)
        self.assertEqual(quote.volume, 1049844)
        self.assertFalse(quote.actionable)
        self.assertIsNone(quote.as_of)

    def test_fractional_volume_is_rejected(self):
        raw = {"last": 320.5, "totalVolumeTraded": 1049844.25}
        with self.assertRaises(AvanzaDataError):
            parse_public_quote(normalize_quote(raw), order_book_id="5269")

    def test_missing_volume_is_rejected(self):
        with self.assertRaises(AvanzaDataError):
            parse_public_quote(normalize_quote({"last": 320.5}), order_book_id="5269")


if __name__ == "__main__":
    unittest.main()
