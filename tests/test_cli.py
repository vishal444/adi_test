from __future__ import annotations

import unittest

from kgraph_llm.cli import format_result_table


class ResultTableTest(unittest.TestCase):
    def test_formats_result_rows_and_hides_internal_columns(self) -> None:
        rendered = format_result_table(
            (
                {
                    "district_name": "Alappuzha",
                    "average_surgeries": 1015.0,
                    "note": None,
                    "_result_rank": 1,
                },
                {
                    "district_name": "Kozhikode",
                    "average_surgeries": 1650.0,
                    "note": "review|verified",
                    "_result_rank": 2,
                },
            )
        )

        self.assertIn("| district_name | average_surgeries | note", rendered)
        self.assertIn("| Alappuzha", rendered)
        self.assertIn("1015.0", rendered)
        self.assertIn("NULL", rendered)
        self.assertIn(r"review\|verified", rendered)
        self.assertNotIn("_result_rank", rendered)

    def test_empty_results_still_render_as_a_table(self) -> None:
        self.assertEqual(
            format_result_table(()),
            "| Result |\n| --- |\n| No rows returned |",
        )

    def test_rows_with_only_internal_columns_render_a_table(self) -> None:
        self.assertEqual(
            format_result_table(({"_total_rows": 0},)),
            "| Result |\n| --- |\n| No displayable columns returned |",
        )


if __name__ == "__main__":
    unittest.main()
