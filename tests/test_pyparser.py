"""Small regression tests for the realestate text parser.

Run from repository root: python3 -m unittest discover -s tests
"""
import unittest

import pyparser


class ParserTests(unittest.TestCase):
    def test_listing_id_from_url(self):
        self.assertEqual(
            pyparser.extract_listing_id(
                "https://www.realestate.com.au/property-house-qld-redbank-12345678", ""
            ),
            "12345678",
        )

    def test_address(self):
        data = pyparser.extract_address_parts(
            "11 Bridge Street, Redbank, QLD 4301 - House for Sale"
        )
        self.assertEqual(data["postcode"], "4301")
        self.assertEqual(data["street_number"], "11")

    def test_price_range(self):
        self.assertEqual(
            pyparser.parse_price("$700,000 - $750,000")["price_min"], 700000
        )
        self.assertEqual(
            pyparser.parse_price("$700,000 - $750,000")["price_max"], 750000
        )

    def test_land_size(self):
        self.assertEqual(pyparser.clean_land_size("0.05 ha"), 500)


if __name__ == "__main__":
    unittest.main()
