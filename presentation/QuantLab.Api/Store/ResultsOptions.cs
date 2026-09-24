namespace QuantLab.Api.Store;

/// <summary>Where the results store written by <c>quantlab</c> lives (ADR-0008).</summary>
public sealed class ResultsOptions
{
    public const string Section = "Results";

    /// <summary>The store directory; a relative path is resolved against the content root.</summary>
    public string Path { get; set; } = "../../results";
}
