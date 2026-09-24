namespace QuantLab.Api.Results;

/// <summary>Read-only access to the results store; the endpoints depend on nothing else.</summary>
public interface IResultsStore
{
    StoreHealth Health();

    /// <summary>Every registry row in registry order; empty when there is no store.</summary>
    IReadOnlyList<HypothesisSummary> Hypotheses();
}
