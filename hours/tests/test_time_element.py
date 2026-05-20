import datetime

from hours.enums import State
from hours.models import (
    TimeElement,
    combine_and_apply_override,
    combine_element_time_spans,
)


def test_combine_and_apply_override_full_day_override():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=None,
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.CLOSED,
        override=True,
        full_day=True,
    )

    assert combine_and_apply_override([te1, te2]) == [te2]


def test_combine_and_apply_override_combine_two_same():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=12, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [
        TimeElement(
            start_time=datetime.time(hour=8, minute=0),
            end_time=datetime.time(hour=16, minute=0),
            end_time_on_next_day=False,
            resource_state=State.OPEN,
            override=False,
            full_day=False,
        )
    ]


def test_combine_and_apply_override_combine_two_same_one_unknown_start():
    te1 = TimeElement(
        start_time=None,
        end_time=datetime.time(hour=12, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=10, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [
        TimeElement(
            start_time=None,
            end_time=datetime.time(hour=16, minute=0),
            end_time_on_next_day=False,
            resource_state=State.OPEN,
            override=False,
            full_day=False,
        )
    ]


def test_combine_and_apply_override_combine_two_same_one_unknown_end():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=12, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=10, minute=0),
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [
        TimeElement(
            start_time=datetime.time(hour=8, minute=0),
            end_time=None,
            end_time_on_next_day=False,
            resource_state=State.OPEN,
            override=False,
            full_day=False,
        )
    ]


def test_combine_and_apply_override_combine_two_same_one_unknown_start_and_end():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=12, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=None,
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [
        TimeElement(
            start_time=None,
            end_time=None,
            end_time_on_next_day=False,
            resource_state=State.OPEN,
            override=False,
            full_day=False,
        )
    ]


def test_combine_and_apply_override_combine_two_same_one_unknown_start_one_unknown_end():  # noqa
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=None,
        end_time=datetime.time(hour=12, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [
        TimeElement(
            start_time=None,
            end_time=None,
            end_time_on_next_day=False,
            resource_state=State.OPEN,
            override=False,
            full_day=False,
        )
    ]


def test_combine_and_apply_override_two_separate():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=12, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=13, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [te1, te2]


def test_combine_and_apply_override_two_separate_one_unknown_start_one_unknown_end():  # noqa
    te1 = TimeElement(
        start_time=datetime.time(hour=12, minute=0),
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=None,
        end_time=datetime.time(hour=8, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [te2, te1]


def test_combine_and_apply_override_one_overriding():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=12, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        end_time_on_next_day=False,
        resource_state=State.CLOSED,
        override=True,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [
        TimeElement(
            start_time=datetime.time(hour=12, minute=0),
            end_time=datetime.time(hour=14, minute=0),
            end_time_on_next_day=False,
            resource_state=State.CLOSED,
            override=True,
            full_day=False,
        ),
    ]


def test_combine_and_apply_override_multiple_overriding():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=9, minute=0),
        end_time=datetime.time(hour=11, minute=0),
        end_time_on_next_day=False,
        resource_state=State.CLOSED,
        override=True,
        full_day=False,
    )

    te3 = TimeElement(
        start_time=datetime.time(hour=13, minute=0),
        end_time=datetime.time(hour=15, minute=0),
        end_time_on_next_day=False,
        resource_state=State.CLOSED,
        override=True,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2, te3]) == [te2, te3]


def test_combine_and_apply_override_multiple_overriding_overlapping():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=12, minute=0),
        end_time=datetime.time(hour=14, minute=0),
        end_time_on_next_day=False,
        resource_state=State.CLOSED,
        override=True,
        full_day=False,
    )

    te3 = TimeElement(
        start_time=datetime.time(hour=13, minute=0),
        end_time=datetime.time(hour=15, minute=0),
        end_time_on_next_day=False,
        resource_state=State.CLOSED,
        override=True,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2, te3]) == [
        TimeElement(
            start_time=datetime.time(hour=12, minute=0),
            end_time=datetime.time(hour=15, minute=0),
            end_time_on_next_day=False,
            resource_state=State.CLOSED,
            override=True,
            full_day=False,
        ),
    ]


def test_combine_and_apply_full_day_no_override():
    te1 = TimeElement(
        start_time=datetime.time(hour=8, minute=0),
        end_time=datetime.time(hour=16, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=None,
        end_time=None,
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=True,
    )

    assert combine_and_apply_override([te1, te2]) == [te2]


def test_combine_and_apply_override_with_previous_day():
    te1 = TimeElement(
        start_time=datetime.time(hour=0, minute=0),
        end_time=datetime.time(hour=6, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=5, minute=0),
        end_time=datetime.time(hour=9, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    expected = TimeElement(
        start_time=datetime.time(hour=0, minute=0),
        end_time=datetime.time(hour=9, minute=0),
        end_time_on_next_day=False,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [expected]


def test_combine_and_apply_override_two_next_day_ends():
    te1 = TimeElement(
        start_time=datetime.time(hour=22, minute=0),
        end_time=datetime.time(hour=4, minute=0),
        end_time_on_next_day=True,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    te2 = TimeElement(
        start_time=datetime.time(hour=23, minute=0),
        end_time=datetime.time(hour=6, minute=0),
        end_time_on_next_day=True,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    expected = TimeElement(
        start_time=datetime.time(hour=22, minute=0),
        end_time=datetime.time(hour=6, minute=0),
        end_time_on_next_day=True,
        resource_state=State.OPEN,
        override=False,
        full_day=False,
    )

    assert combine_and_apply_override([te1, te2]) == [expected]


# ---------------------------------------------------------------------------
# Tests for combine_element_time_spans – override flag validity
# ---------------------------------------------------------------------------
def _te(
    start, end, state=State.OPEN, override=False, end_next_day=False, full_day=False
):
    return TimeElement(
        start_time=start,
        end_time=end,
        end_time_on_next_day=end_next_day,
        resource_state=state,
        override=override,
        full_day=full_day,
    )


class TestCombineElementTimeSpansOverrideFlag:
    def test_default_returns_only_non_override_elements(self):
        non_override = _te(
            datetime.time(8), datetime.time(16), state=State.OPEN, override=False
        )
        overriding = _te(
            datetime.time(10), datetime.time(14), state=State.OPEN, override=True
        )

        result = combine_element_time_spans([non_override, overriding])

        assert all(not el.override for el in result)
        assert result == [non_override]

    def test_override_true_returns_only_overriding_elements(self):
        non_override = _te(
            datetime.time(8), datetime.time(16), state=State.OPEN, override=False
        )
        overriding = _te(
            datetime.time(10), datetime.time(14), state=State.CLOSED, override=True
        )

        result = combine_element_time_spans([non_override, overriding], override=True)

        assert all(el.override for el in result)
        assert result == [overriding]

    def test_mixed_override_same_state_not_combined(self):
        non_override = _te(
            datetime.time(8), datetime.time(12), state=State.OPEN, override=False
        )
        overriding = _te(
            datetime.time(10), datetime.time(16), state=State.OPEN, override=True
        )

        # Ask for override=False → should only combine the non-overriding element
        result_false = combine_element_time_spans(
            [non_override, overriding], override=False
        )
        assert result_false == [non_override]

        result_true = combine_element_time_spans(
            [non_override, overriding], override=True
        )
        assert result_true == [overriding]

    def test_two_overlapping_non_override_combined(self):
        te1 = _te(datetime.time(8), datetime.time(12), state=State.OPEN, override=False)
        te2 = _te(
            datetime.time(10), datetime.time(16), state=State.OPEN, override=False
        )

        result = combine_element_time_spans([te1, te2])

        assert result == [
            TimeElement(
                start_time=datetime.time(8),
                end_time=datetime.time(16),
                end_time_on_next_day=False,
                resource_state=State.OPEN,
                override=False,
                full_day=False,
            )
        ]

    def test_two_overlapping_overriding_combined(self):
        te1 = _te(
            datetime.time(12), datetime.time(14), state=State.CLOSED, override=True
        )
        te2 = _te(
            datetime.time(13), datetime.time(15), state=State.CLOSED, override=True
        )

        result = combine_element_time_spans([te1, te2], override=True)

        assert result == [
            TimeElement(
                start_time=datetime.time(12),
                end_time=datetime.time(15),
                end_time_on_next_day=False,
                resource_state=State.CLOSED,
                override=True,
                full_day=False,
            )
        ]

    def test_different_states_different_override_all_separated(self):
        open_normal = _te(
            datetime.time(8), datetime.time(12), state=State.OPEN, override=False
        )
        closed_normal = _te(
            datetime.time(13), datetime.time(17), state=State.CLOSED, override=False
        )
        open_override = _te(
            datetime.time(9), datetime.time(11), state=State.OPEN, override=True
        )

        result_false = combine_element_time_spans(
            [open_normal, closed_normal, open_override], override=False
        )
        assert all(not el.override for el in result_false)
        states_false = {el.resource_state for el in result_false}
        assert State.OPEN in states_false
        assert State.CLOSED in states_false

        result_true = combine_element_time_spans(
            [open_normal, closed_normal, open_override], override=True
        )
        assert result_true == [open_override]

    def test_empty_elements_returns_empty(self):
        assert combine_element_time_spans([]) == []

    def test_no_matching_override_returns_empty(self):
        non_override = _te(
            datetime.time(8), datetime.time(16), state=State.OPEN, override=False
        )
        assert combine_element_time_spans([non_override], override=True) == []

    def test_result_override_flag_matches_parameter(self):

        for flag in (False, True):
            elements = [
                _te(
                    datetime.time(8), datetime.time(16), state=State.OPEN, override=flag
                )
            ]
            result = combine_element_time_spans(elements, override=flag)
            assert all(el.override == flag for el in result)
