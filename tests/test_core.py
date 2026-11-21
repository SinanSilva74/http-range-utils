import unittest

from http_range_utils import (
    format_content_range,
    format_range,
    parse_content_range,
    parse_range,
)


class ParseRangeTests(unittest.TestCase):
    def test_simple_range(self):
        self.assertEqual(parse_range("bytes=0-99"), [(0, 100)])

    def test_multiple_ranges(self):
        self.assertEqual(
            parse_range("bytes=0-0, 5-9, 20-20"),
            [(0, 1), (5, 10), (20, 21)],
        )

    def test_unit_is_case_insensitive(self):
        self.assertEqual(parse_range("BYTES=0-9"), [(0, 10)])

    def test_whitespace_around_specs(self):
        self.assertEqual(parse_range("bytes= 0-9 , 20-29 "), [(0, 10), (20, 30)])

    def test_suffix_range(self):
        self.assertEqual(parse_range("bytes=-50", complete_length=1000), [(950, 1000)])

    def test_suffix_range_longer_than_representation(self):
        self.assertEqual(parse_range("bytes=-5000", complete_length=100), [(0, 100)])

    def test_open_ended_range_with_length(self):
        self.assertEqual(parse_range("bytes=500-", complete_length=1000), [(500, 1000)])

    def test_open_ended_range_without_length(self):
        self.assertEqual(parse_range("bytes=500-"), [(500, 2**63 - 1)])

    def test_unsatisfiable_start_is_dropped(self):
        self.assertEqual(parse_range("bytes=1000-1099", complete_length=1000), [])

    def test_zero_length_suffix_is_dropped(self):
        self.assertEqual(parse_range("bytes=-0", complete_length=1000), [])

    def test_missing_unit(self):
        with self.assertRaises(ValueError):
            parse_range("0-99")

    def test_unsupported_unit(self):
        with self.assertRaises(ValueError):
            parse_range("items=0-99")

    def test_empty_specifier(self):
        with self.assertRaises(ValueError):
            parse_range("bytes=")

    def test_empty_specifier_in_list(self):
        with self.assertRaises(ValueError):
            parse_range("bytes=0-9,,20-29")

    def test_reversed_range(self):
        with self.assertRaises(ValueError):
            parse_range("bytes=10-5")

    def test_bare_dash(self):
        with self.assertRaises(ValueError):
            parse_range("bytes=-")

    def test_negative_number_is_not_a_number(self):
        with self.assertRaises(ValueError):
            parse_range("bytes=-5-10")

    def test_suffix_requires_complete_length(self):
        with self.assertRaises(ValueError):
            parse_range("bytes=-50")

    def test_negative_complete_length(self):
        with self.assertRaises(ValueError):
            parse_range("bytes=0-9", complete_length=-1)

    def test_non_string_value(self):
        with self.assertRaises(ValueError):
            parse_range(None)  # type: ignore[arg-type]


class ParseContentRangeTests(unittest.TestCase):
    def test_known_complete_length(self):
        self.assertEqual(parse_content_range("bytes 0-99/1234"), (0, 100, 1234))

    def test_unknown_complete_length(self):
        self.assertEqual(parse_content_range("bytes 0-99/*"), (0, 100, None))

    def test_unit_is_case_insensitive(self):
        self.assertEqual(parse_content_range("BYTES 0-9/100"), (0, 10, 100))

    def test_missing_complete_length(self):
        with self.assertRaises(ValueError):
            parse_content_range("bytes 0-99")

    def test_unsupported_unit(self):
        with self.assertRaises(ValueError):
            parse_content_range("items 0-99/100")

    def test_reversed_range(self):
        with self.assertRaises(ValueError):
            parse_content_range("bytes 10-5/100")

    def test_end_outside_complete_length(self):
        with self.assertRaises(ValueError):
            parse_content_range("bytes 0-150/100")

    def test_suffix_not_allowed(self):
        with self.assertRaises(ValueError):
            parse_content_range("bytes -50/100")

    def test_open_ended_not_allowed(self):
        with self.assertRaises(ValueError):
            parse_content_range("bytes 50-/100")

    def test_empty_complete_length(self):
        with self.assertRaises(ValueError):
            parse_content_range("bytes 0-9/")


class FormatTests(unittest.TestCase):
    def test_format_range(self):
        self.assertEqual(format_range(0, 100), "bytes=0-99")

    def test_format_range_single_byte(self):
        self.assertEqual(format_range(5, 6), "bytes=5-5")

    def test_format_range_empty(self):
        with self.assertRaises(ValueError):
            format_range(5, 5)

    def test_format_range_negative(self):
        with self.assertRaises(ValueError):
            format_range(-1, 10)

    def test_format_content_range(self):
        self.assertEqual(format_content_range(0, 100, 1234), "bytes 0-99/1234")

    def test_format_content_range_unknown(self):
        self.assertEqual(format_content_range(0, 100, None), "bytes 0-99/*")

    def test_format_content_range_end_exceeds_complete(self):
        with self.assertRaises(ValueError):
            format_content_range(0, 200, 100)


class RoundTripTests(unittest.TestCase):
    def test_range_round_trip(self):
        self.assertEqual(parse_range(format_range(10, 20)), [(10, 20)])

    def test_content_range_round_trip(self):
        self.assertEqual(
            parse_content_range(format_content_range(10, 20, 100)),
            (10, 20, 100),
        )

    def test_content_range_round_trip_unknown(self):
        self.assertEqual(
            parse_content_range(format_content_range(10, 20, None)),
            (10, 20, None),
        )


if __name__ == "__main__":
    unittest.main()
