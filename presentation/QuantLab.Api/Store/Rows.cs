using System.Data.Common;
using System.Text.Json;

namespace QuantLab.Api.Store;

/// <summary>Maps one Parquet row of each store table to its read model, column by column.</summary>
internal static class Rows
{
    public static HypothesisSummary Summary(DbDataReader row) => new(
        Hypothesis: row.Text("hypothesis"),
        Strategy: row.Text("strategy"),
        Universe: row.Text("universe"),
        CostModel: row.Text("cost_model"),
        Parameters: Json(row.Text("parameters")),
        TrainingStart: row.Date("training_start"),
        TrainingEnd: row.Date("training_end"),
        HoldoutStart: row.Date("holdout_start"),
        HoldoutEnd: row.Date("holdout_end"),
        Criterion: row.Text("criterion"),
        MinSharpe: row.Number("min_sharpe"),
        MaxPValue: row.Number("max_p_value"),
        FrozenAtCommit: row.Text("frozen_at_commit"),
        RegisteredAt: row.Instant("registered_at_us"),
        TrialsOnSameData: row.Integer("trials_on_same_data"),
        Status: row.Text("status"),
        HasRun: row.Flag("has_run"),
        Holdout: row.OptionalText("holdout_verdict") is { } verdict
            ? new HoldoutRecord(
                OpenedAt: row.Instant("holdout_opened_at_us"),
                OpenedAtCommit: row.Text("holdout_opened_at_commit"),
                CostModel: row.Text("holdout_cost_model"),
                Cagr: row.OptionalNumber("holdout_cagr"),
                Sharpe: row.OptionalNumber("holdout_sharpe"),
                Sortino: row.OptionalNumber("holdout_sortino"),
                Calmar: row.OptionalNumber("holdout_calmar"),
                MaxDrawdown: row.OptionalNumber("holdout_max_drawdown"),
                PValue: row.OptionalNumber("holdout_p_value"),
                Verdict: verdict)
            : null,
        TrainingSharpe: null,
        Sparkline: [],
        DataSource: null);

    public static RunSummary Run(DbDataReader row) => new(
        RunId: row.Text("run_id"),
        Strategy: row.Text("strategy"),
        StrategyParams: Json(row.Text("strategy_params")),
        Universe: row.Text("universe"),
        CostModel: row.Text("cost_model"),
        Start: row.Date("start"),
        End: row.Date("end"),
        FirstPosition: row.OptionalDate("first_position"),
        Seed: row.Integer("seed"),
        GitSha: row.Text("git_sha"),
        GeneratedAt: row.Instant("generated_at_us"),
        DataSource: row.Text("data_source"),
        CostSensitivity: new CostSensitivity(
            row.Text("cost_sensitivity"),
            row.OptionalNumber("cost_sharpe_difference"),
            row.OptionalFlag("cost_cagr_sign_flip")),
        WalkForward: new WalkForwardSummary(
            row.OptionalFlag("walk_forward_passed"),
            row.Text("walk_forward_rule"),
            row.Integer("walk_forward_positive_windows"),
            row.Integer("walk_forward_windows_with_sharpe")),
        Permutation: new PermutationSummary(
            Passed: row.OptionalFlag("permutation_passed"),
            Statistic: row.Text("permutation_statistic"),
            Count: row.Integer("permutation_count"),
            Seed: row.Integer("permutation_seed"),
            Alpha: row.Number("permutation_alpha"),
            ActiveDays: row.Integer("permutation_active_days"),
            LowConfidence: row.Flag("permutation_low_confidence"),
            Actual: row.OptionalNumber("permutation_actual"),
            NullMean: row.OptionalNumber("permutation_null_mean"),
            NullStd: row.OptionalNumber("permutation_null_std"),
            Percentile: row.OptionalNumber("permutation_percentile"),
            PValue: row.OptionalNumber("permutation_p_value"),
            Reason: row.OptionalText("permutation_reason")),
        MultipleTesting: new MultipleTestingSummary(
            row.TextList("trials"),
            row.Integer("returns_count"),
            row.OptionalNumber("sharpe_annualized"),
            row.OptionalNumber("psr"),
            row.OptionalNumber("dsr_threshold"),
            row.OptionalNumber("dsr")),
        Contrast: row.OptionalText("contrast_hypothesis") is { } contrast
            ? new ContrastSummary(
                contrast, row.Text("contrast_cost_model"), row.OptionalNumber("contrast_correlation"))
            : null,
        RegimeMethod: row.Text("regime_method"),
        Trades: new TradeCounts(
            row.Integer("trades"), row.Integer("trades_open_at_end"), row.Integer("trades_winning")));

    public static CostModelMetrics Metrics(DbDataReader row) => new(
        row.Text("cost_model"),
        row.OptionalNumber("cagr"),
        row.OptionalNumber("sharpe"),
        row.OptionalNumber("sortino"),
        row.OptionalNumber("calmar"),
        row.OptionalNumber("max_drawdown"),
        row.Number("turnover"),
        row.Flag("primary"));

    public static WalkForwardWindow Window(DbDataReader row) => new(
        row.Date("start"),
        row.Date("end"),
        row.Flag("partial"),
        row.Flag("aggregate"),
        row.OptionalNumber("cagr"),
        row.OptionalNumber("sharpe"),
        row.OptionalNumber("max_drawdown"));

    public static RegimeMetrics Regime(DbDataReader row) => new(
        row.Text("regime"),
        row.Integer("days"),
        row.Number("share"),
        row.OptionalNumber("cagr"),
        row.OptionalNumber("sharpe"),
        row.OptionalNumber("sortino"));

    public static MonthlyReturn Month(DbDataReader row) =>
        new(row.Integer("year"), row.Integer("month"), row.Number("net_return"));

    public static PnlGroup Group(DbDataReader row) => new(
        row.Text("dimension"),
        row.Text("key"),
        row.Integer("trades"),
        row.Number("win_rate"),
        row.Number("total_net_pnl"),
        row.Number("mean_net_pnl"),
        row.Number("median_net_pnl"),
        row.Number("worst_net_pnl"),
        row.Number("best_net_pnl"),
        row.Number("costs"));

    public static Diagnostic Diagnostic(DbDataReader row) =>
        new(row.Text("title"), row.Text("label"), row.OptionalNumber("value"));

    public static EquityPoint Equity(DbDataReader row) =>
        new(row.Date("ts"), row.Number("equity"), row.Number("drawdown"));

    public static Trade Trade(DbDataReader row) => new(
        row.Integer("trade_id"),
        row.Text("instrument_id"),
        row.Text("side"),
        row.Date("entry_ts"),
        row.Number("entry_price"),
        row.Date("exit_ts"),
        row.Number("exit_price"),
        row.Number("size"),
        row.Number("gross_pnl"),
        row.Number("costs"),
        row.Number("net_pnl"),
        row.Integer("holding_days"),
        row.Text("regime_at_entry"),
        row.Flag("open_at_end"));

    private static JsonElement Json(string text)
    {
        using var document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }
}
