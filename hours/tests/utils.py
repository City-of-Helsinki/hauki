from hours.enums import RuleContext, RuleSubject
from hours.tests.conftest import RuleFactory, TimeSpanFactory, TimeSpanGroupFactory


def assert_response_status_code(response, expected_status_code):
    """
    Assert that the response has the expected status code and print
    the response data if it doesn't.
    """
    assert response.status_code == expected_status_code, "{} {}".format(
        response.status_code, response.data
    )


class TimeSpanGroupBuilder:
    """
    Helper class for building TimeSpanGroups.

    Usage:
    TimeSpanGroupBuilder(date_period).with_rule(...).with_time_span(...).create()
    """

    def __init__(self, date_period):
        self.date_period = date_period
        self.time_spans = []
        self.rule = None

    def with_rule(self, **kwargs):
        kwargs.setdefault("context", RuleContext.PERIOD)
        kwargs.setdefault("subject", RuleSubject.DAY)
        self.rule = kwargs
        return self

    def with_time_span(self, **kwargs):
        self.time_spans.append(kwargs)
        return self

    def create(self):
        time_span_group = TimeSpanGroupFactory(period=self.date_period)

        if self.rule is not None:
            RuleFactory(group=time_span_group, **self.rule)

        for time_span in self.time_spans:
            TimeSpanFactory(group=time_span_group, **time_span)

        return time_span_group
