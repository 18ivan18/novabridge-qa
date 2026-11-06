import pytest

from novabridge_qa.qa.citations import ValidatedAnswer, validate


def test_valid_citations_in_order_are_unchanged() -> None:
    assert validate("Anvils sell [1]. Roofs leak [2].", 3) == ValidatedAnswer(
        "Anvils sell [1]. Roofs leak [2].", (1, 2), ()
    )


def test_citations_are_renumbered_by_first_appearance() -> None:
    result = validate("Anvils sell [3]. Roofs leak [1].", 3)

    assert result.text == "Anvils sell [1]. Roofs leak [2]."
    assert result.cited_ids_in_order == (3, 1)


def test_repeated_citations_keep_one_number() -> None:
    result = validate("A [4]. B [2]. C [4].", 4)

    assert result.text == "A [1]. B [2]. C [1]."
    assert result.cited_ids_in_order == (4, 2)


def test_comma_form_becomes_adjacent_brackets() -> None:
    result = validate("Anvils sell [2, 3].", 3)

    assert result.text == "Anvils sell [1][2]."
    assert result.cited_ids_in_order == (2, 3)


def test_adjacent_brackets_are_parsed() -> None:
    assert validate("Anvils sell [3][1].", 3).text == "Anvils sell [1][2]."


@pytest.mark.parametrize("citation", ["[1,2]", "[ 1 , 2 ]", "[1,  2]"])
def test_spacing_inside_brackets_is_tolerated(citation: str) -> None:
    assert validate(f"Anvils {citation}.", 2).text == "Anvils [1][2]."


def test_duplicate_in_one_group_is_collapsed() -> None:
    assert validate("Anvils [2, 2].", 2).text == "Anvils [1]."


def test_out_of_range_citation_is_removed_without_a_gap() -> None:
    result = validate("Anvils sell [9]. Roofs leak [1].", 3)

    assert result.text == "Anvils sell. Roofs leak [1]."
    assert result.cited_ids_in_order == (1,)
    assert result.dropped_ids == (9,)


def test_zero_is_not_a_passage() -> None:
    assert validate("Anvils [0].", 3).dropped_ids == (0,)


def test_upper_bound_is_inclusive() -> None:
    assert validate("Anvils [3].", 3).cited_ids_in_order == (3,)
    assert validate("Anvils [4].", 3).dropped_ids == (4,)


def test_invalid_id_inside_a_group_keeps_the_valid_ones() -> None:
    result = validate("Anvils [1, 9, 2].", 2)

    assert result.text == "Anvils [1][2]."
    assert result.dropped_ids == (9,)


def test_dropped_ids_are_listed_once_in_order() -> None:
    assert validate("A [9]. B [7]. C [9].", 2).dropped_ids == (9, 7)


def test_renumbering_ignores_dropped_citations() -> None:
    assert validate("A [9]. B [2].", 2).text == "A. B [1]."


@pytest.mark.parametrize("citation", ["【2】", "【2†L10-L15】", "【 2 】", "[2†L3]"])
def test_gpt_oss_citation_forms_are_normalized(citation: str) -> None:
    result = validate(f"Anvils sell {citation}.", 2)

    assert result.text == "Anvils sell [1]."
    assert result.cited_ids_in_order == (2,)


def test_adjacent_full_width_brackets_are_parsed() -> None:
    assert validate("Anvils【2】【1】.", 2).text == "Anvils[1][2]."


def test_full_width_citations_are_range_checked_too() -> None:
    result = validate("Anvils【9】.", 2)

    assert result.text == "Anvils."
    assert result.dropped_ids == (9,)


def test_mismatched_text_in_full_width_brackets_is_left_alone() -> None:
    assert validate("Anvils【note】 [1].", 1).text == "Anvils【note】 [1]."


def test_no_citations_at_all() -> None:
    result = validate("Anvils sell well.", 3)

    assert result.text == "Anvils sell well."
    assert result.cited_ids_in_order == ()


def test_only_invalid_citations_leaves_none() -> None:
    assert validate("Anvils [8][9].", 3).cited_ids_in_order == ()


def test_non_numeric_brackets_are_left_alone() -> None:
    assert validate("The [sic] anvil [1].", 1).text == "The [sic] anvil [1]."


def test_citation_at_the_start_leaves_no_leading_space() -> None:
    assert validate("[9] Anvils sell [1].", 1).text == "Anvils sell [1]."


def test_multiline_text_is_kept() -> None:
    assert validate("First [2].\n\nSecond [1].", 2).text == "First [1].\n\nSecond [2]."


def test_no_passages_means_every_citation_is_dropped() -> None:
    assert validate("Anvils [1].", 0).dropped_ids == (1,)
