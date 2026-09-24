using System.Text.Json;

namespace QuantLab.Api.Results;

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
    string FrozenAtCommit,
    DateTimeOffset RegisteredAt,
    long TrialsOnSameData,
    string Status,
    bool HasRun,
    HoldoutRecord? Holdout,
    double? TrainingSharpe,
    IReadOnlyList<double> Sparkline);
