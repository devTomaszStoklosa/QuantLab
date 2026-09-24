namespace QuantLab.Api.Store;

/// <summary>The store layout this API reads: docs/specs/q7-dotnet-react-presentation/02-spec.md.</summary>
public static class StoreSchema
{
    /// <summary>Must match <c>SCHEMA_VERSION</c> in quantlab.reporting.results_store.</summary>
    public const long Version = 1;

    public const string RegistryFile = "hypotheses.parquet";
    public const string RunFile = "run.parquet";
}

/// <summary>The store was written by another schema version than this API reads (REQ-725).</summary>
public sealed class IncompatibleStoreException(string file, long found)
    : Exception($"{file} has schema version {found}; this API reads version {StoreSchema.Version}. "
        + "Refresh the store: uv run quantlab registry, then rerun the hypotheses.")
{
    public long Found { get; } = found;
}
