import unittest

from Backend.app.utils.row_normalization import MISSING_VALUE, normalize_country, normalize_rows


class TestRowNormalization(unittest.TestCase):
    def test_normalizes_country_aliases(self):
        self.assertEqual(normalize_country("United States of America"), "United States")
        self.assertEqual(normalize_country("USA"), "United States")
        self.assertEqual(normalize_country("US"), "United States")
        self.assertEqual(normalize_country("United Kingdom of Great Britain and Northern Ireland"), "United Kingdom")
        self.assertEqual(normalize_country("GB"), "United Kingdom")
        self.assertEqual(normalize_country("UK"), "United Kingdom")
        self.assertEqual(normalize_country("España"), "Spain")
        self.assertEqual(normalize_country("Brasil"), "Brazil")
        self.assertEqual(normalize_country("Österreich"), "Austria")
        self.assertEqual(normalize_country("Россия"), "Russia")
        self.assertEqual(normalize_country("CN"), "China")

    def test_extracts_country_from_localized_place_text(self):
        self.assertEqual(normalize_country("日本、〒194-0211 東京都町田市相原町５３２２"), "Japan")
        self.assertEqual(normalize_country("山东省威海市荣成市崖头"), "China")
        self.assertEqual(normalize_country("대한민국 강원도 횡성군 안흥면"), "South Korea")

    def test_normalizes_invalid_numeric_country_as_missing(self):
        self.assertEqual(normalize_country("450902"), MISSING_VALUE)

    def test_country_normalization_is_applied_to_rows(self):
        rows = normalize_rows(
            [
                {"source_bdd": "iNaturalist", "country": "USA", "coordinates": "43, -72"},
                {"source_bdd": "iNaturalist", "country": "658474", "coordinates": "45, 3"},
            ]
        )

        self.assertEqual(rows[0]["country"], "United States")
        self.assertEqual(rows[1]["country"], MISSING_VALUE)


if __name__ == "__main__":
    unittest.main()
