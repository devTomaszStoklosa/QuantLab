import re
from datetime import UTC, date, datetime, timedelta

import pytest

from quantlab.backtest.run import BacktestRun, PortfolioSnapshot
from quantlab.core.data.provider import PriceBar
from quantlab.reporting.cost_comparison import RunMetrics, run_metrics
from quantlab.reporting.metrics import drawdown_series
from quantlab.reporting.multiple_testing import MultipleTesting
from quantlab.reporting.tear_sheet import DISCLAIMER, Contrast, TearSheet, render_html
from quantlab.risk.conditional import RegimeMetrics, regime_conditional_metrics
from quantlab.validation.holdout import HoldoutRecord
from quantlab.validation.permutation import PermutationTestValidator
from quantlab.validation.walk_forward import WalkForwardValidator

_FIRST_DAY = date(2020, 1, 1)
_DAYS = 800  # into 2022, so the chart has year ticks and walk-forward has windows
_PERIODS_PER_YEAR = 365
# Varying magnitudes and signs: the curve has drawdowns and every metric is defined.
_PATTERN = [0.02, -0.01, 0.03, -0.02, 0.01, -0.03, 0.015, -0.005, 0.025, -0.017]


def _day(i: int) -> date:
    return _FIRST_DAY + timedelta(days=i)


def _closes() -> list[float]:
    closes = [100.0]
    for i in range(_DAYS):
        closes.append(closes[-1] * (1.0 + _PATTERN[i % len(_PATTERN)]))
    return closes


def _bars() -> dict[str, list[PriceBar]]:
    return {
        "a": [
            PriceBar(
                instrument_id="a",
                ts=_day(i),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1.0,
                adj_close=None,
                source="test",
            )
            for i, close in enumerate(_closes())
        ]
    }


def _run(held: bool = True, strategy_params: dict | None = None) -> BacktestRun:
    """Fully long instrument "a" from day 0, so equity follows its closes."""
    closes = _closes()
    return BacktestRun(
        id="run-1",
        strategy_name="time_series_momentum",
        strategy_params=strategy_params or {"lookback_days": 365},
        cost_model_name="realistic",
        universe_name="test-universe",
        start=_FIRST_DAY,
        end=_day(_DAYS),
        seed=0,
        git_sha="0123456789abcdef",
        snapshots=[
            PortfolioSnapshot(
                ts=_day(i),
                cash=0.0,
                positions={"a": 1.0} if held and i > 0 else {},
                equity=close / closes[0] if held else 1.0,
            )
            for i, close in enumerate(closes)
        ],
    )


def _holdout(**changes: object) -> HoldoutRecord:
    record = HoldoutRecord(
        hypothesis="momentum_v1",
        frozen_at_commit="aaaaaaa1111111",
        opened_at=datetime(2026, 9, 23, 14, 1, tzinfo=UTC),
        opened_at_commit="bbbbbbb2222222",
        start=date(2023, 1, 1),
        end=date(2023, 12, 31),
        cost_model_name="realistic",
        cagr=0.7654,
        sharpe=9.87,
        sortino=8.76,
        calmar=7.65,
        max_drawdown=-0.4321,
        p_value=0.6135,
        permutation={},
        criterion="Holdout net Sharpe > 0 and p-value < 0.1",
        verdict="inconclusive",
    )
    return record.model_copy(update=changes)


def _sheet(run: BacktestRun | None = None, **changes: object) -> TearSheet:
    run = run or _run()
    labels = {_day(i): ("low" if i % 3 else "high") for i in range(_DAYS + 1)}
    fields = {
        "hypothesis": "momentum_v1",
        "run": run,
        "regimes": regime_conditional_metrics(run, labels, _PERIODS_PER_YEAR),
        "regime_method": "Test regimes.",
        "walk_forward": WalkForwardValidator(_PERIODS_PER_YEAR).validate(run),
        "permutation": PermutationTestValidator(
            bars=_bars(), n_permutations=50, alpha=0.1, periods_per_year=_PERIODS_PER_YEAR
        ).validate(run),
        "holdout": _holdout(),
        "generated_at": datetime(2026, 9, 24, 10, 0, tzinfo=UTC),
    }
    if "cost_comparison" not in changes:
        metrics = run_metrics(run, _PERIODS_PER_YEAR)
        fields["cost_comparison"] = [
            metrics.model_copy(update={"cost_model_name": "zero-cost"}),
            metrics,
        ]
    fields.update(changes)
    return TearSheet(**fields)


def _section(page: str, section_id: str) -> str:
    start = page.index(f'<section id="{section_id}"')
    return page[start : page.index("</section>", start)]


def _points(page: str, chart_id: str) -> list[tuple[float, float]]:
    chart = page[page.index(f'<svg id="{chart_id}"') :]
    points = re.search(r'<polyline class="[^"]+" points="([^"]+)"', chart).group(1)
    return [tuple(float(v) for v in point.split(",")) for point in points.split()]


def test_tear_sheet_has_equity_and_drawdown_charts_metrics_and_regime_tables() -> None:
    sheet = _sheet()

    page = render_html(sheet)

    assert '<svg id="equity-chart"' in page
    assert '<svg id="drawdown-chart"' in page
    assert '<h3 id="metrics">' in page
    assert '<h3 id="regimes">' in page
    regimes = page[page.index('<h3 id="regimes">') : page.index('<h3 id="walk-forward">')]
    assert "<code>low</code>" in regimes
    assert "<code>high</code>" in regimes


def test_charts_draw_one_point_per_snapshot() -> None:
    sheet = _sheet()

    page = render_html(sheet)

    assert len(_points(page, "equity-chart")) == len(sheet.run.snapshots)
    assert len(_points(page, "drawdown-chart")) == len(sheet.run.snapshots)


def test_drawdown_chart_plots_the_drawdown_series() -> None:
    sheet = _sheet()
    drawdowns = drawdown_series([snapshot.equity for snapshot in sheet.run.snapshots])

    points = _points(render_html(sheet), "drawdown-chart")

    # SVG y grows downward: the deepest drawdown is the lowest point on screen.
    assert points[drawdowns.index(min(drawdowns))][1] == max(y for _, y in points)
    assert all(y == points[0][1] for (_, y), dd in zip(points, drawdowns) if dd == 0.0)


def test_axis_labels_are_distinct() -> None:
    page = render_html(_sheet())

    for chart_id in ("equity-chart", "drawdown-chart"):
        chart = page[
            page.index(f'<svg id="{chart_id}"') : page.index("</svg>", page.index(chart_id))
        ]
        labels = re.findall(r'text-anchor="end">([^<]+)</text>', chart)
        assert len(labels) >= 2
        assert len(set(labels)) == len(labels)


def test_training_and_holdout_results_are_separate_sections() -> None:
    sheet = _sheet()
    training_sharpe = f"{sheet.cost_comparison[1].sharpe:.2f}".replace("-", "−")

    page = render_html(sheet)
    training = _section(page, "training")
    holdout = _section(page, "holdout")

    assert training_sharpe in training
    assert training_sharpe not in holdout
    for holdout_value in ("76.5%", "9.87", "8.76", "7.65", "−43.2%", "0.614"):
        assert holdout_value in holdout
        assert holdout_value not in training
    assert "inconclusive" in holdout
    assert "Werdykt" not in training


def test_run_overlapping_the_holdout_is_refused() -> None:
    with pytest.raises(ValueError, match="overlaps the holdout"):
        _sheet(holdout=_holdout(start=_day(_DAYS - 10)))


def test_holdout_record_of_another_hypothesis_is_refused() -> None:
    with pytest.raises(ValueError, match="not momentum_v1"):
        _sheet(holdout=_holdout(hypothesis="other_v1"))


def test_sealed_holdout_shows_no_numbers() -> None:
    page = render_html(_sheet(holdout=None))

    holdout = _section(page, "holdout")
    assert "nie został jeszcze otwarty" in holdout
    assert "<table" not in holdout
    assert not re.search(r"\d", holdout.split("</h2>", 1)[1])


def test_run_cost_model_must_be_in_the_cost_comparison() -> None:
    with pytest.raises(ValueError, match="No metrics for the run's cost model"):
        _sheet(cost_comparison=[])


def test_validation_results_must_match_their_slots() -> None:
    sheet = _sheet()

    with pytest.raises(ValueError, match="Expected a walk-forward result"):
        _sheet(walk_forward=sheet.permutation)


def test_negative_numbers_use_a_real_minus_sign() -> None:
    sheet = _sheet()
    max_drawdown = sheet.cost_comparison[1].max_drawdown
    assert max_drawdown < 0

    page = render_html(sheet)

    assert f"{max_drawdown:.1%}".replace("-", "−") in page
    assert f"{max_drawdown:.1%}" not in page


def test_undefined_metric_is_shown_as_a_dash() -> None:
    regimes = {
        "high": RegimeMetrics(label="high", days=1, cagr=0.1, sharpe=None, sortino=None),
    }

    page = render_html(_sheet(regimes=regimes))

    row = re.search(r"<tr><td><code>high</code></td>.*?</tr>", page).group(0)
    assert row.count("—") == 2


def test_text_from_inputs_is_escaped() -> None:
    run = _run(strategy_params={"note": "<script>alert(1)</script>"})

    page = render_html(_sheet(run))

    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_disclaimer_closes_the_page() -> None:
    page = render_html(_sheet())

    assert page.index(DISCLAIMER) > page.index('<section id="holdout"')
    for advice in ("kup", "sprzedaj", "zwiększ"):
        assert not re.search(rf"\b{advice}", page, re.IGNORECASE)


def test_run_without_positions_renders() -> None:
    run = _run(held=False)
    flat = RunMetrics(
        cost_model_name="realistic",
        cagr=0.0,
        sharpe=0.0,
        sortino=0.0,
        calmar=0.0,
        max_drawdown=0.0,
        turnover=0.0,
    )

    page = render_html(_sheet(run, cost_comparison=[flat], regimes={}))

    assert len(_points(page, "equity-chart")) == len(run.snapshots)
    assert "Brak dni z pozycją" in page
    assert "Brak okien z pozycją" in page
    permutation = page[page.index('<h3 id="permutation">') :]
    assert "<strong>inconclusive</strong>" in permutation


def test_a_random_portfolio_test_is_named_and_described_as_one() -> None:
    sheet = _sheet()
    detail = {**sheet.permutation.detail, "test": "random_portfolio"}
    permutation = sheet.permutation.model_copy(update={"detail": detail})
    record = _holdout()
    holdout = record.model_copy(update={"permutation": {**record.permutation, **detail}})

    page = render_html(_sheet(permutation=permutation, holdout=holdout))

    section = page[page.index('<h3 id="permutation">') :]
    assert section.startswith('<h3 id="permutation">Test losowych portfeli</h3>')
    assert "losowych portfeli z przekroju każdej decyzji" in section
    assert "wobec średniej losowych portfeli" in section
    assert "p-value (test losowych portfeli)" in page


def test_low_confidence_permutation_is_flagged() -> None:
    sheet = _sheet()
    detail = {**sheet.permutation.detail, "low_confidence": True, "active_days": 120}
    permutation = sheet.permutation.model_copy(update={"detail": detail})

    page = render_html(_sheet(permutation=permutation))

    assert "Niska wiarygodność: tylko 120 dni z pozycją" in page


@pytest.mark.parametrize(
    ("walk_forward_passed", "holdout_verdict", "status"),
    [
        (True, "inconclusive", "inconclusive"),
        (True, "passed", "confirmed"),
        (False, "passed", "rejected"),
        (True, "rejected", "rejected"),
    ],
)
def test_verdict_leads_with_the_status_the_gates_give(
    walk_forward_passed: bool, holdout_verdict: str, status: str
) -> None:
    walk_forward = _sheet().walk_forward.model_copy(update={"passed": walk_forward_passed})

    page = render_html(_sheet(walk_forward=walk_forward, holdout=_holdout(verdict=holdout_verdict)))

    verdict = _section(page, "verdict")
    assert page.index('<section id="verdict"') < page.index('<section id="training"')
    assert f'<strong class="verdict verdict-{status}">{status}</strong>' in verdict
    assert f"holdout: <strong>{holdout_verdict}</strong>" in verdict


def test_sealed_holdout_gives_no_verdict() -> None:
    page = render_html(_sheet(holdout=None))

    verdict = _section(page, "verdict")
    assert "Brak werdyktu" in verdict
    for status in ("confirmed", "rejected", "inconclusive"):
        assert f"verdict-{status}" not in verdict


def test_metrics_table_shows_turnover() -> None:
    sheet = _sheet()
    turnover = f"{sheet.cost_comparison[1].turnover:.1f}\u00d7"

    page = render_html(sheet)

    assert "Obrót (\u00d7/rok)" in page
    assert turnover in _section(page, "training")


def test_contrast_is_shown_only_when_given() -> None:
    contrast = Contrast(hypothesis="momentum_v1", cost_model_name="realistic", correlation=-0.42)

    with_contrast = render_html(_sheet(contrast=contrast))
    without_contrast = render_html(_sheet())

    section = with_contrast[with_contrast.index('<h3 id="contrast">') :]
    assert "<code>momentum_v1</code>" in section
    assert "<strong>\u22120.42</strong>" in section
    assert '<h3 id="contrast">' not in without_contrast


def test_undefined_contrast_is_shown_as_a_dash() -> None:
    contrast = Contrast(hypothesis="momentum_v1", cost_model_name="realistic", correlation=None)

    page = render_html(_sheet(contrast=contrast))

    assert "<strong>\u2014</strong>" in page[page.index('<h3 id="contrast">') :]


def test_multiple_testing_is_shown_only_when_given() -> None:
    deflation = MultipleTesting(
        trials=["momentum_v1", "mean_reversion_v1"],
        n_returns=1_961,
        sharpe_annualized=0.45,
        psr=0.84,
        threshold_annualized=0.22,
        dsr=0.70,
    )

    with_section = render_html(_sheet(multiple_testing=deflation))
    without_section = render_html(_sheet())

    start = with_section.index('<h3 id="multiple-testing">')
    section = with_section[start : with_section.index("</section>", start)]
    assert "<strong>2</strong>" in section
    assert "<code>momentum_v1</code>, <code>mean_reversion_v1</code>" in section
    for value in ("0.45", "0.84", "0.22", "0.70", "1\u2009961 dni"):
        assert value in section
    assert "nie jest częścią żadnej reguły" in section
    assert '<h3 id="multiple-testing">' not in without_section
    assert '<h3 id="multiple-testing">' in _section(with_section, "training")
