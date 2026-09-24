namespace QuantLab.Api.Store;

/// <summary>Read-only access to the results store; the endpoints depend on nothing else.</summary>
public interface IResultsStore
{
    StoreHealth Health();

    /// <summary>Every registry row in registry order; empty when there is no store.</summary>
    IReadOnlyList<HypothesisSummary> Hypotheses();

    /// <summary>Whether the registry knows the hypothesis and holds a run of it.</summary>
    HypothesisState State(string hypothesis);

    /// <summary>The hypothesis with its run's evidence, or null for a hypothesis the registry does not know.</summary>
    HypothesisDetail? Hypothesis(string hypothesis);

    /// <summary>The run's snapshots in date order; only for <see cref="HypothesisState.HasRun"/>.</summary>
    IReadOnlyList<EquityPoint> Equity(string hypothesis);

    /// <summary>One page of the run's trade ledger; only for <see cref="HypothesisState.HasRun"/>.</summary>
    TradePage Trades(string hypothesis, TradeQuery query);
}

public enum HypothesisState
{
    Unknown,
    NoRun,
    HasRun,
}

public enum TradeSort
{
    EntryTs,
    ExitTs,
    InstrumentId,
    Size,
    GrossPnl,
    Costs,
    NetPnl,
    HoldingDays,
}

/// <summary>A validated trade-ledger query (REQ-723).</summary>
public sealed record TradeQuery(
    string? Instrument = null,
    string? Side = null,
    TradeSort Sort = TradeSort.EntryTs,
    bool Descending = false,
    int Offset = 0,
    int Limit = TradeQuery.DefaultLimit)
{
    public const int DefaultLimit = 100;
    public const int MaxLimit = 1000;
}
