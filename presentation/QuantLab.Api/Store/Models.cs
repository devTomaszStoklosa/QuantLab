using System.Text.Json;

namespace QuantLab.Api.Store;

// Read models of the results store. Every number is the store's own: nothing
// here is derived from another number (REQ-730).

public sealed record StoreHealth(string ResultsPath, bool Exists, long? SchemaVersion, bool Compatible);

public sealed record HoldoutRecord(
    DateTimeOffset OpenedAt,
    string OpenedAtCommit,
    string CostModel,
    double? Cagr,
    double? Sharpe,
    double? Sortino,
    double? Calmar,
    double? MaxDrawdown,
    double? PValue,
    string Verdict);

public sealed record HypothesisSummary(
    string Hypothesis,
    string Strategy,
    string Universe,
    string CostModel,
    JsonElement Parameters,
    DateOnly TrainingStart,
    DateOnly TrainingEnd,
    DateOnly HoldoutStart,
    DateOnly HoldoutEnd,
    string Criterion,
    double MinSharpe,
    double MaxPValue,
    string SignificanceTest,
    string InSampleValidation,
    long Configurations,
    string FrozenAtCommit,
    DateTimeOffset RegisteredAt,
    long TrialsOnSameData,
    string Status,
    bool HasRun,
    HoldoutRecord? Holdout,
    double? TrainingSharpe,
    IReadOnlyList<double> Sparkline,
    string? DataSource);

public sealed record CostSensitivity(string Verdict, double? SharpeDifference, bool? CagrSignFlip);

public sealed record WalkForwardSummary(bool? Passed, string Rule, long PositiveWindows, long WindowsWithSharpe);

public sealed record PermutationSummary(
    bool? Passed,
    string Test,
    string Statistic,
    long Count,
    long Seed,
    double Alpha,
    long ActiveDays,
    bool LowConfidence,
    double? Actual,
    double? NullMean,
    double? NullStd,
    double? Percentile,
    double? PValue,
    string? Reason);

public sealed record MultipleTestingSummary(
    IReadOnlyList<string> Trials,
    long Configurations,
    long ReturnsCount,
    double? SharpeAnnualized,
    double? Psr,
    double? DsrThreshold,
    double? Dsr);

/// <summary>The frozen in-sample gate: <c>walk_forward</c>, or <c>cpcv</c> for a parameter grid (q8).</summary>
public sealed record InSampleGate(string Validation, bool? Passed);

public sealed record PboSummary(double Value, long Blocks, long Splits);

public sealed record CpcvSummary(
    long Groups,
    long TestGroups,
    long Purge,
    long Embargo,
    long Splits,
    long Paths,
    double? MeanSharpe,
    double? MedianSharpe,
    double? MinSharpe,
    double? MaxSharpe,
    double? PositiveShare,
    string Rule);

/// <summary>A parameter grid's evidence over the training period (q8, REQ-841).</summary>
public sealed record GridSummary(DateOnly Start, DateOnly End, PboSummary? Pbo, CpcvSummary Cpcv);

public sealed record ContrastSummary(string Hypothesis, string CostModel, double? Correlation);

public sealed record TradeCounts(long Total, long OpenAtEnd, long Winning);

public sealed record RunSummary(
    string RunId,
    string Strategy,
    JsonElement StrategyParams,
    string Universe,
    string CostModel,
    DateOnly Start,
    DateOnly End,
    DateOnly? FirstPosition,
    long Seed,
    string GitSha,
    DateTimeOffset GeneratedAt,
    string DataSource,
    CostSensitivity CostSensitivity,
    WalkForwardSummary WalkForward,
    InSampleGate InSample,
    GridSummary? Grid,
    PermutationSummary Permutation,
    MultipleTestingSummary MultipleTesting,
    ContrastSummary? Contrast,
    string RegimeMethod,
    TradeCounts Trades);

public sealed record CostModelMetrics(
    string CostModel,
    double? Cagr,
    double? Sharpe,
    double? Sortino,
    double? Calmar,
    double? MaxDrawdown,
    double Turnover,
    bool Primary);

public sealed record WalkForwardWindow(
    DateOnly Start,
    DateOnly End,
    bool Partial,
    bool Aggregate,
    double? Cagr,
    double? Sharpe,
    double? MaxDrawdown);

public sealed record RegimeMetrics(
    string Regime,
    long Days,
    double Share,
    double? Cagr,
    double? Sharpe,
    double? Sortino);

public sealed record MonthlyReturn(long Year, long Month, double NetReturn);

public sealed record YearlyReturn(long Year, double NetReturn);

public sealed record PnlGroup(
    string Dimension,
    string Key,
    long Trades,
    double WinRate,
    double TotalNetPnl,
    double MeanNetPnl,
    double MedianNetPnl,
    double WorstNetPnl,
    double BestNetPnl,
    double Costs);

public sealed record Diagnostic(string Title, string Label, double? Value);

/// <summary>One paragraph of the result's narrative, in Polish, composed in Python from the stored numbers (q13).</summary>
public sealed record NarrativeParagraph(string Section, string Text);

/// <summary>One grid value's Sharpe in one year's choice; <c>Chosen</c> marks the value traded that year.</summary>
public sealed record SelectionCell(long Year, long Days, string Value, double? Sharpe, bool Chosen);

public sealed record CpcvPath(long Position, double? Sharpe);

public sealed record CpcvChoice(string Value, double Share);

/// <summary>A hypothesis and, when the store holds one, its latest run's evidence (REQ-721).</summary>
public sealed record HypothesisDetail(
    HypothesisSummary Hypothesis,
    RunSummary? Run,
    IReadOnlyList<CostModelMetrics> Metrics,
    IReadOnlyList<WalkForwardWindow> WalkForward,
    IReadOnlyList<RegimeMetrics> Regimes,
    IReadOnlyList<MonthlyReturn> Monthly,
    IReadOnlyList<YearlyReturn> Yearly,
    IReadOnlyList<PnlGroup> PnlGroups,
    IReadOnlyList<Diagnostic> Diagnostics,
    IReadOnlyList<SelectionCell> Selection,
    IReadOnlyList<CpcvPath> CpcvPaths,
    IReadOnlyList<CpcvChoice> CpcvChoices,
    IReadOnlyList<string> TradeInstruments,
    IReadOnlyList<NarrativeParagraph> Narrative);

public sealed record EquityPoint(DateOnly Ts, double Equity, double Drawdown);

public sealed record Trade(
    long TradeId,
    string InstrumentId,
    string Side,
    DateOnly EntryTs,
    double EntryPrice,
    DateOnly ExitTs,
    double ExitPrice,
    double Size,
    double GrossPnl,
    double Costs,
    double NetPnl,
    long HoldingDays,
    string RegimeAtEntry,
    bool OpenAtEnd);

public sealed record TradePage(long Total, int Offset, int Limit, IReadOnlyList<Trade> Items);
