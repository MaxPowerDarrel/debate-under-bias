from debate_bias.specifics import Specifics, count_specifics, mentions_rule


def test_counts_names_that_do_not_start_a_sentence():
    assert count_specifics("The ship left. Captain Evans met Judy at the dock.").names == 2  # Evans, Judy


def test_skips_sentence_starts_pronouns_and_answer_letters():
    text = "Evans waited. I think Answer A is right, and Debater B agrees. She left."
    assert count_specifics(text).names == 0


def test_words_that_open_a_quotation_are_skipped():
    assert count_specifics('He paused. "Linton is here," she said.').names == 0
    assert count_specifics('He said "Linton is here."').names == 0
    assert count_specifics('One declares, <v_quote>"It is finished?"</v_quote> and another says "Yes."').names == 0


def test_words_after_a_closing_quote_and_full_stop_are_skipped():
    assert count_specifics('He said "we are due soon." Taking a world is not the same.').names == 0
    assert count_specifics('The text says "we left." Then Evans left.').names == 1  # Evans


def test_names_inside_a_quotation_are_counted():
    assert count_specifics('He said "they took Charles to the Empire State Building."').names == 4


def test_counts_digits_and_number_words():
    s = count_specifics("He had twenty-one days, 3 tanks, and 1,500 liters, about two dozen in all.")
    assert s.numbers == 6  # twenty, one, 3, 1,500, two, dozen


def test_years_and_months_are_dates_not_numbers():
    s = count_specifics("It was in March 2041, on a Tuesday, five years later.")
    assert (s.dates, s.numbers) == (3, 1)


def test_may_is_a_date_only_before_a_number():
    assert count_specifics("He said they may leave.").dates == 0
    assert count_specifics("It ended on May 4.").dates == 1


def test_quote_tags_are_ignored_and_quotes_are_counted():
    s = count_specifics("He agreed: <v_quote>Evans had 12 days left</v_quote> and so on.")
    assert s == Specifics(names=0, numbers=1, dates=0)  # "Evans" follows a colon, so it starts a sentence
    assert count_specifics("Then <quote>Evans had 12 days</quote>").names == 1


def test_total_adds_the_three_counts():
    assert Specifics(2, 3, 1).total == 6


def test_mentions_rule():
    assert mentions_rule("The judge has been told to favor names.")
    assert mentions_rule("My argument is full of specific names, numbers, and dates.")
    assert not mentions_rule("Evans counts his oxygen: <v_quote>twenty-one days to live</v_quote>.")
