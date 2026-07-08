"""Comprehensive tests for utils/number_to_words — number-to-words conversion.

Covers English and Romanian languages, EUR/RON/USD currencies,
all public API behaviours, helper functions, and edge cases.
"""

from __future__ import annotations

import pytest

from utils.number_to_words import (
    CURRENCY_NAMES,
    _en_convert_hundreds,
    _en_number_to_words,
    _ro_convert_hundreds,
    _ro_number_to_words,
    number_to_words,
)


# =============================================================================
# Constants structure
# =============================================================================

class TestCurrencyNames:
    """Verify the CURRENCY_NAMES dictionary structure."""

    def test_has_expected_languages(self):
        assert set(CURRENCY_NAMES) == {"en", "ro"}

    def test_en_has_expected_currencies(self):
        assert set(CURRENCY_NAMES["en"]) == {"EUR", "RON", "USD"}

    def test_ro_has_expected_currencies(self):
        assert set(CURRENCY_NAMES["ro"]) == {"EUR", "RON", "USD"}

    def test_each_entry_is_4_tuple(self):
        for lang, currencies in CURRENCY_NAMES.items():
            for code, names in currencies.items():
                assert isinstance(names, tuple)
                assert len(names) == 4

    def test_plural_differs_from_singular(self):
        # Romanian EUR uses "euro" for both singular and plural
        for lang, currencies in CURRENCY_NAMES.items():
            for code, (s, p, ss, ps) in currencies.items():
                if lang == "ro" and code == "EUR":
                    assert p == s, f"{lang}/{code} should be invariant"
                else:
                    assert p != s, f"{lang}/{code} plural same as singular"
                assert ps != ss, f"{lang}/{code} sub-unit plural same as singular"


# =============================================================================
# _en_convert_hundreds  (0-999)
# =============================================================================

class TestEnConvertHundreds:
    """_en_convert_hundreds: converts 0-999 to English words."""

    def test_zero_returns_empty(self):
        assert _en_convert_hundreds(0) == ""

    def test_ones(self):
        assert _en_convert_hundreds(1) == "one"
        assert _en_convert_hundreds(5) == "five"
        assert _en_convert_hundreds(9) == "nine"

    def test_teens(self):
        assert _en_convert_hundreds(10) == "ten"
        assert _en_convert_hundreds(11) == "eleven"
        assert _en_convert_hundreds(15) == "fifteen"
        assert _en_convert_hundreds(19) == "nineteen"

    def test_tens(self):
        assert _en_convert_hundreds(20) == "twenty"
        assert _en_convert_hundreds(30) == "thirty"
        assert _en_convert_hundreds(90) == "ninety"

    def test_compound_tens_ones(self):
        assert _en_convert_hundreds(21) == "twenty-one"
        assert _en_convert_hundreds(35) == "thirty-five"
        assert _en_convert_hundreds(99) == "ninety-nine"

    def test_hundreds_round(self):
        assert _en_convert_hundreds(100) == "one hundred"
        assert _en_convert_hundreds(200) == "two hundred"
        assert _en_convert_hundreds(900) == "nine hundred"

    def test_hundreds_and_ones(self):
        assert _en_convert_hundreds(101) == "one hundred and one"
        assert _en_convert_hundreds(105) == "one hundred and five"

    def test_hundreds_and_teens(self):
        assert _en_convert_hundreds(111) == "one hundred and eleven"
        assert _en_convert_hundreds(119) == "one hundred and nineteen"

    def test_hundreds_and_compound(self):
        assert _en_convert_hundreds(121) == "one hundred and twenty-one"
        assert _en_convert_hundreds(999) == "nine hundred and ninety-nine"

    def test_no_and_without_hundreds(self):
        result = _en_convert_hundreds(45)
        assert result == "forty-five"
        assert "and" not in result

    def test_no_and_when_remainder_zero(self):
        result = _en_convert_hundreds(300)
        assert result == "three hundred"
        assert "and" not in result


# =============================================================================
# _en_number_to_words  (full integer range)
# =============================================================================

class TestEnNumberToWords:
    """_en_number_to_words: converts integers 0-999999 to English words."""

    def test_zero(self):
        assert _en_number_to_words(0) == "zero"

    def test_one(self):
        assert _en_number_to_words(1) == "one"

    def test_ten(self):
        assert _en_number_to_words(10) == "ten"

    def test_twenty_one(self):
        assert _en_number_to_words(21) == "twenty-one"

    def test_one_hundred(self):
        assert _en_number_to_words(100) == "one hundred"

    def test_one_hundred_and_one(self):
        assert _en_number_to_words(101) == "one hundred and one"

    def test_one_hundred_and_fifteen(self):
        assert _en_number_to_words(115) == "one hundred and fifteen"

    def test_one_thousand(self):
        assert _en_number_to_words(1000) == "one thousand"

    def test_one_thousand_one(self):
        assert _en_number_to_words(1001) == "one thousand one"

    def test_one_thousand_one_hundred(self):
        assert _en_number_to_words(1100) == "one thousand one hundred"

    def test_ten_thousand(self):
        assert _en_number_to_words(10_000) == "ten thousand"

    def test_twelve_thousand_three_hundred(self):
        assert _en_number_to_words(12_300) == "twelve thousand three hundred"

    def test_one_hundred_thousand(self):
        assert _en_number_to_words(100_000) == "one hundred thousand"

    def test_nine_hundred_ninety_nine_thousand(self):
        assert _en_number_to_words(999_999) == (
            "nine hundred and ninety-nine thousand "
            "nine hundred and ninety-nine"
        )

    def test_million(self):
        assert _en_number_to_words(1_000_000) == "one million"

    def test_negative(self):
        assert _en_number_to_words(-5) == "negative five"

    def test_negative_thousands(self):
        assert _en_number_to_words(-2500) == "negative two thousand five hundred"

    def test_max_supported(self):
        # The internal helper can go up to 999999
        assert _en_number_to_words(999_999) != ""


# =============================================================================
# _ro_convert_hundreds  (0-999)
# =============================================================================

class TestRoConvertHundreds:
    """_ro_convert_hundreds: converts 0-999 to Romanian words."""

    def test_zero_returns_empty(self):
        assert _ro_convert_hundreds(0) == ""

    def test_ones_masculine(self):
        assert _ro_convert_hundreds(1) == "unu"
        assert _ro_convert_hundreds(2) == "doi"
        assert _ro_convert_hundreds(5) == "cinci"

    def test_ones_feminine(self):
        assert _ro_convert_hundreds(1, is_fem=True) == "o"
        assert _ro_convert_hundreds(2, is_fem=True) == "două"
        # Other numbers are the same regardless of gender
        assert _ro_convert_hundreds(3, is_fem=True) == "trei"

    def test_teens(self):
        assert _ro_convert_hundreds(10) == "zece"
        assert _ro_convert_hundreds(11) == "unsprezece"
        assert _ro_convert_hundreds(12) == "doisprezece"
        assert _ro_convert_hundreds(15) == "cincisprezece"
        assert _ro_convert_hundreds(19) == "nouăsprezece"

    def test_tens(self):
        assert _ro_convert_hundreds(20) == "douăzeci"
        assert _ro_convert_hundreds(30) == "treizeci"
        assert _ro_convert_hundreds(90) == "nouăzeci"

    def test_compound_tens_ones(self):
        assert _ro_convert_hundreds(21) == "douăzeci și unu"
        assert _ro_convert_hundreds(35) == "treizeci și cinci"
        assert _ro_convert_hundreds(99) == "nouăzeci și nouă"

    def test_compound_tens_ones_feminine(self):
        # _RO_ONES_FEM[1] = "o", so 21 feminine becomes "douăzeci și o"
        assert _ro_convert_hundreds(21, is_fem=True) == "douăzeci și o"
        assert _ro_convert_hundreds(22, is_fem=True) == "douăzeci și două"

    def test_hundred_one(self):
        assert _ro_convert_hundreds(100) == "o sută"

    def test_hundreds(self):
        assert _ro_convert_hundreds(200) == "două sute"
        assert _ro_convert_hundreds(300) == "trei sute"
        assert _ro_convert_hundreds(900) == "nouă sute"

    def test_hundreds_and_ones(self):
        assert _ro_convert_hundreds(101) == "o sută unu"
        assert _ro_convert_hundreds(105) == "o sută cinci"

    def test_hundreds_and_teens(self):
        assert _ro_convert_hundreds(111) == "o sută unsprezece"
        assert _ro_convert_hundreds(119) == "o sută nouăsprezece"

    def test_hundreds_and_compound(self):
        assert _ro_convert_hundreds(121) == "o sută douăzeci și unu"
        assert _ro_convert_hundreds(999) == "nouă sute nouăzeci și nouă"

    def test_no_si_between_hundreds_and_tens(self):
        # Romanian does NOT use "și" between hundreds and lower parts
        result = _ro_convert_hundreds(250)
        assert result == "două sute cincizeci"
        assert "și" not in result

    def test_no_si_between_hundreds_and_ones(self):
        result = _ro_convert_hundreds(201)
        assert result == "două sute unu"
        assert "și" not in result


# =============================================================================
# _ro_number_to_words  (full integer range)
# =============================================================================

class TestRoNumberToWords:
    """_ro_number_to_words: converts integers 0-999999 to Romanian words."""

    def test_zero(self):
        assert _ro_number_to_words(0) == "zero"

    def test_one(self):
        assert _ro_number_to_words(1) == "unu"

    def test_ten(self):
        assert _ro_number_to_words(10) == "zece"

    def test_twenty_one(self):
        assert _ro_number_to_words(21) == "douăzeci și unu"

    def test_one_hundred(self):
        assert _ro_number_to_words(100) == "o sută"

    def test_one_hundred_one(self):
        assert _ro_number_to_words(101) == "o sută unu"

    def test_one_thousand(self):
        assert _ro_number_to_words(1000) == "o mie"

    def test_two_thousand(self):
        assert _ro_number_to_words(2000) == "două mii"

    def test_one_thousand_one(self):
        assert _ro_number_to_words(1001) == "o mie unu"

    def test_one_thousand_one_hundred(self):
        assert _ro_number_to_words(1100) == "o mie o sută"

    def test_ten_thousand(self):
        assert _ro_number_to_words(10_000) == "zece mii"

    def test_twelve_thousand_three_hundred(self):
        # _RO_TEENS[2] = "doisprezece"
        assert _ro_number_to_words(12_300) == "doisprezece mii trei sute"

    def test_one_hundred_thousand(self):
        # 100_000 → _ro_convert_hundreds(100, is_fem=True) + " mii" = "o sută mii"
        assert _ro_number_to_words(100_000) == "o sută mii"

    def test_one_million(self):
        assert _ro_number_to_words(1_000_000) == "un milion"

    def test_two_million(self):
        # scale_idx=2 calls _ro_convert_hundreds without is_fem → "doi milioane"
        assert _ro_number_to_words(2_000_000) == "doi milioane"

    def test_nine_hundred_ninety_nine_thousand(self):
        result = _ro_number_to_words(999_999)
        assert "nouă" in result
        assert "mii" in result

    def test_negative(self):
        assert _ro_number_to_words(-5) == "minus cinci"

    def test_negative_thousands(self):
        assert _ro_number_to_words(-2500) == "minus două mii cinci sute"


# =============================================================================
# number_to_words — basic amounts
# =============================================================================

class TestNumberToWordsBasic:
    """Core number_to_words behaviour with default en/EUR."""

    def test_zero_amount(self):
        result = number_to_words(0)
        assert result == "Zero euros and zero cents"

    def test_one(self):
        result = number_to_words(1)
        assert result == "One euro and zero cents"

    def test_one_point_fifty(self):
        result = number_to_words(1.50)
        assert result == "One euro and fifty cents"

    def test_two(self):
        result = number_to_words(2)
        assert result == "Two euros and zero cents"

    def test_ten(self):
        result = number_to_words(10)
        assert result == "Ten euros and zero cents"

    def test_hundred(self):
        result = number_to_words(100)
        assert result == "One hundred euros and zero cents"

    def test_thousand(self):
        result = number_to_words(1000)
        assert result == "One thousand euros and zero cents"

    def test_million(self):
        result = number_to_words(1_000_000)
        assert result == "One million euros and zero cents"

    def test_compound_number(self):
        result = number_to_words(1234.56)
        assert "one thousand" in result.lower()
        assert "fifty-six" in result.lower()

    def test_nine_hundred_ninety_nine(self):
        result = number_to_words(999.99)
        assert "nine hundred and ninety-nine" in result.lower()

    def test_very_small_decimal(self):
        result = number_to_words(0.01)
        assert result == "Zero euros and one cent"

    def test_round_number(self):
        result = number_to_words(5000)
        assert result == "Five thousand euros and zero cents"

    def test_capitalized_first_letter(self):
        result = number_to_words(1)
        assert result[0].isupper()


# =============================================================================
# number_to_words — English language specifics
# =============================================================================

class TestNumberToWordsEnglish:
    """English-specific formatting."""

    def test_uses_and_between_euros_and_cents(self):
        result = number_to_words(5.50, lang="en")
        assert " and " in result

    def test_uses_and_in_hundreds(self):
        result = number_to_words(110, lang="en")
        assert "one hundred and ten" in result.lower()

    def test_plural_currency_euros(self):
        result = number_to_words(2, "EUR", "en")
        assert "euros" in result

    def test_singular_currency_euro(self):
        result = number_to_words(1, "EUR", "en")
        assert "euro" in result

    def test_plural_subunit_cents(self):
        result = number_to_words(0.05, "EUR", "en")
        assert "cents" in result

    def test_singular_subunit_cent(self):
        result = number_to_words(0.01, "EUR", "en")
        assert "cent" in result


# =============================================================================
# number_to_words — Romanian language specifics
# =============================================================================

class TestNumberToWordsRomanian:
    """Romanian-specific formatting."""

    def test_uses_si_between_lei_and_bani(self):
        result = number_to_words(5.50, "RON", "ro")
        assert " și " in result

    def test_one_leu(self):
        result = number_to_words(1, "RON", "ro")
        assert result == "Un leu și zero bani"

    def test_one_euro(self):
        result = number_to_words(1, "EUR", "ro")
        assert result == "Un euro și zero cenți"

    def test_five_lei(self):
        result = number_to_words(5, "RON", "ro")
        assert "lei" in result

    def test_one_hundred_ron(self):
        result = number_to_words(100, "RON", "ro")
        assert "o sută" in result.lower()

    def test_one_thousand_ron(self):
        result = number_to_words(1000, "RON", "ro")
        assert "o mie" in result.lower()

    def test_two_thousand_ron(self):
        result = number_to_words(2000, "RON", "ro")
        assert "două mii" in result.lower()

    def test_million_ron(self):
        result = number_to_words(1_000_000, "RON", "ro")
        assert "un milion" in result.lower()

    def test_one_ban(self):
        result = number_to_words(0.01, "RON", "ro")
        assert "un ban" in result

    def test_five_bani(self):
        result = number_to_words(0.05, "RON", "ro")
        assert "bani" in result

    def test_amount_with_cents(self):
        result = number_to_words(150.75, "RON", "ro")
        assert "lei" in result
        assert "bani" in result

    def test_compound_number_with_si(self):
        result = number_to_words(21, "RON", "ro")
        assert "douăzeci" in result.lower()

    def test_zero_ron(self):
        result = number_to_words(0, "RON", "ro")
        assert result == "Zero lei și zero bani"

    def test_feminine_hundreds_with_thousands(self):
        # 2100 = "două mii o sută"
        result = number_to_words(2100, "RON", "ro")
        assert "două mii" in result.lower()

    def test_plural_mii(self):
        result = number_to_words(3000, "RON", "ro")
        assert "mii" in result

    def test_plural_milioane(self):
        result = number_to_words(2_000_000, "RON", "ro")
        assert "milioane" in result


# =============================================================================
# number_to_words — currencies
# =============================================================================

class TestNumberToWordsCurrencies:
    """Different currency codes."""

    def test_eur_default(self):
        result = number_to_words(1)
        assert "euro" in result

    def test_ron(self):
        result = number_to_words(1, "RON")
        assert "leu" in result

    def test_usd(self):
        result = number_to_words(1, "USD")
        assert "dollar" in result

    def test_unknown_currency_falls_back_to_eur(self):
        result = number_to_words(1, "GBP")
        assert "euro" in result

    def test_ron_plural_lei(self):
        result = number_to_words(2, "RON")
        assert "lei" in result

    def test_usd_plural_dollars(self):
        result = number_to_words(2, "USD")
        assert "dollars" in result

    def test_eur_ro_singular(self):
        result = number_to_words(1, "EUR", "ro")
        assert "euro" in result

    def test_usd_ro(self):
        result = number_to_words(1, "USD", "ro")
        assert "dolar" in result

    def test_ron_en(self):
        result = number_to_words(1, "RON", "en")
        assert "leu" in result
        assert "and" in result


# =============================================================================
# number_to_words — error handling
# =============================================================================

class TestNumberToWordsErrors:
    """Input validation and error cases."""

    def test_negative_raises_valueerror(self):
        with pytest.raises(ValueError, match="Amount cannot be negative"):
            number_to_words(-1)

    def test_negative_zero_is_ok(self):
        # -0.0 should be fine (it's not < 0)
        result = number_to_words(-0.0)
        assert isinstance(result, str)

    def test_exceeds_max_raises_valueerror(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            number_to_words(10_000_000)

    def test_max_supported_value(self):
        # 9,999,999 should work
        result = number_to_words(9_999_999)
        assert isinstance(result, str)

    def test_unknown_language_falls_back(self):
        # Unknown lang falls back to English for currency names
        result = number_to_words(5, "EUR", "fr")
        assert isinstance(result, str)
        assert "euros" in result.lower()

    def test_float_with_many_decimals(self):
        # Should handle floating point precision
        result = number_to_words(1.999)
        assert isinstance(result, str)

    def test_large_float(self):
        result = number_to_words(500_000.25)
        assert "five hundred thousand" in result.lower()


# =============================================================================
# number_to_words — edge cases
# =============================================================================

class TestNumberToWordsEdgeCases:
    """Boundary and special-case amounts."""

    def test_fractional_part_rounding_up_to_next_integer(self):
        # 0.999 → integer_part=0, fractional_part=round(99.9)=100
        result = number_to_words(0.999)
        assert isinstance(result, str)
        assert "one hundred" in result or "zero" in result

    def test_amount_just_below_max(self):
        result = number_to_words(9_999_998.99)
        assert isinstance(result, str)

    def test_tiny_amount_non_zero(self):
        result = number_to_words(0.001)
        assert isinstance(result, str)

    def test_exact_thousand(self):
        result = number_to_words(1000, "EUR", "en")
        assert "one thousand" in result.lower()

    def test_exact_million(self):
        result = number_to_words(1_000_000, "EUR", "en")
        assert "one million" in result.lower()

    def test_thousand_with_fraction(self):
        result = number_to_words(1000.01, "EUR", "en")
        assert "one thousand" in result.lower()
        assert "cent" in result.lower()

    def test_million_with_fraction(self):
        result = number_to_words(1_000_000.50, "EUR", "en")
        assert "one million" in result.lower()
        assert "fifty" in result.lower()

    def test_all_three_currencies_en(self):
        for cur in ("EUR", "RON", "USD"):
            result = number_to_words(1, cur, "en")
            assert isinstance(result, str)

    def test_all_three_currencies_ro(self):
        for cur in ("EUR", "RON", "USD"):
            result = number_to_words(1, cur, "ro")
            assert isinstance(result, str)

    def test_repeated_invocation_consistency(self):
        r1 = number_to_words(1234.56, "EUR", "en")
        r2 = number_to_words(1234.56, "EUR", "en")
        assert r1 == r2

    def test_amount_with_no_cents_output(self):
        result = number_to_words(42, "EUR", "en")
        assert "and zero cents" in result

    def test_euro_cent_singular_en(self):
        result = number_to_words(0.01, "EUR", "en")
        assert result == "Zero euros and one cent"

    def test_ban_singular_ro(self):
        result = number_to_words(0.01, "RON", "ro")
        assert "un ban" in result

    def test_cent_singular_ro(self):
        result = number_to_words(0.01, "EUR", "ro")
        assert "un cent" in result

    def test_cent_singular_usd(self):
        result = number_to_words(0.01, "USD", "en")
        assert "cent" in result

    def test_fractional_99_cents(self):
        result = number_to_words(0.99, "EUR", "en")
        assert "ninety-nine" in result


# =============================================================================
# number_to_words — Romanian special feminine forms
# =============================================================================

class TestNumberToWordsRomanianGender:
    """Romanian gendered number forms in context."""

    def test_unu_becomes_un_before_currency(self):
        result = number_to_words(1, "RON", "ro")
        assert result.startswith("Un ")

    def test_one_thousand_uses_o(self):
        result = number_to_words(1000, "RON", "ro")
        assert "o mie" in result.lower()

    def test_two_thousand_uses_doua(self):
        result = number_to_words(2000, "RON", "ro")
        assert "două mii" in result.lower()

    def test_one_million_uses_un(self):
        result = number_to_words(1_000_000, "RON", "ro")
        assert "un milion" in result.lower()

    def test_two_million_uses_doua(self):
        # Millions use masculine forms: "doi milioane"
        result = number_to_words(2_000_000, "RON", "ro")
        assert "doi milioane" in result.lower()

    def test_2001_masculine_ones(self):
        # 2001 → "două mii unu" (not "două mii una")
        result = _ro_number_to_words(2001)
        assert "unu" in result

    def test_thousands_with_feminine_ones(self):
        # 2002 with _ro_convert_hundreds(2, is_fem=True) → "două"
        result = _ro_number_to_words(2002)
        assert "două" in result


# =============================================================================
# number_to_words — large number edge cases
# =============================================================================

class TestNumberToWordsLargeNumbers:
    """Behaviour near the upper bound."""

    def test_9_999_999_en(self):
        result = number_to_words(9_999_999, "EUR", "en")
        assert "nine million" in result.lower()

    def test_9_999_999_ro(self):
        result = number_to_words(9_999_999, "RON", "ro")
        assert "nouă" in result.lower()

    def test_999_999_en(self):
        result = number_to_words(999_999, "EUR", "en")
        assert "nine hundred and ninety-nine thousand" in result.lower()

    def test_999_999_ro(self):
        result = number_to_words(999_999, "RON", "ro")
        assert "mii" in result
        assert "nouă" in result


# =============================================================================
# Helper consistency — round-trip property
# =============================================================================

class TestHelperConsistency:
    """Internal helpers behave as expected from the public function."""

    def test_en_convert_hundreds_round_trip(self):
        for n in [0, 1, 10, 21, 100, 111, 250, 999]:
            words = _en_convert_hundreds(n)
            if n == 0:
                assert words == ""
            else:
                assert isinstance(words, str)
                assert len(words) > 0

    def test_ro_convert_hundreds_round_trip(self):
        for n in [0, 1, 10, 21, 100, 111, 250, 999]:
            words = _ro_convert_hundreds(n)
            if n == 0:
                assert words == ""
            else:
                assert isinstance(words, str)
                assert len(words) > 0

    def test_en_number_to_words_expected_scale(self):
        assert "thousand" in _en_number_to_words(1000)
        assert "million" in _en_number_to_words(1_000_000)

    def test_ro_number_to_words_expected_scale(self):
        assert "mie" in _ro_number_to_words(1000)
        assert "milion" in _ro_number_to_words(1_000_000)


# =============================================================================
# Integration — across languages and currencies
# =============================================================================

class TestIntegration:
    """Cross-product integration tests."""

    def test_en_eur_zero(self):
        assert number_to_words(0, "EUR", "en") == "Zero euros and zero cents"

    def test_en_ron_zero(self):
        assert number_to_words(0, "RON", "en") == "Zero lei and zero bani"

    def test_en_usd_zero(self):
        assert number_to_words(0, "USD", "en") == "Zero dollars and zero cents"

    def test_ro_eur_zero(self):
        assert number_to_words(0, "EUR", "ro") == "Zero euro și zero cenți"

    def test_ro_ron_zero(self):
        assert number_to_words(0, "RON", "ro") == "Zero lei și zero bani"

    def test_ro_usd_zero(self):
        assert number_to_words(0, "USD", "ro") == "Zero dolari și zero cenți"

    def test_en_eur_one(self):
        assert number_to_words(1, "EUR", "en") == "One euro and zero cents"

    def test_en_ron_one(self):
        assert number_to_words(1, "RON", "en") == "One leu and zero bani"

    def test_en_usd_one(self):
        assert number_to_words(1, "USD", "en") == "One dollar and zero cents"

    def test_ro_eur_one(self):
        assert number_to_words(1, "EUR", "ro") == "Un euro și zero cenți"

    def test_ro_ron_one(self):
        assert number_to_words(1, "RON", "ro") == "Un leu și zero bani"

    def test_ro_usd_one(self):
        assert number_to_words(1, "USD", "ro") == "Un dolar și zero cenți"
