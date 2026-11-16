from apps.crops.models import SeasonalRule


def test_covers_month_simple_window():
    rule = SeasonalRule(sow_start_month=6, sow_end_month=7)
    assert rule.covers_month(6)
    assert rule.covers_month(7)
    assert not rule.covers_month(8)
    assert not rule.covers_month(5)


def test_covers_month_window_wrapping_year_end():
    rule = SeasonalRule(sow_start_month=11, sow_end_month=2)
    assert rule.covers_month(12)
    assert rule.covers_month(1)
    assert not rule.covers_month(6)