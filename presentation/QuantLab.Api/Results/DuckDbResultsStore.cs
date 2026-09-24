using System.Data.Common;
using System.Text.Json;
using DuckDB.NET.Data;
using Microsoft.Extensions.Options;

namespace QuantLab.Api.Results;

/// <summary>
/// Reads the Parquet results store through DuckDB (ADR-0008): an in-memory connection
/// per call, so no file stays open while <c>quantlab run</c> replaces it. File paths
/// and filter values are always SQL parameters.
/// </summary>
public sealed class DuckDbResultsStore(IOptions<ResultsOptions> options, IHostEnvironment environment)
    : IResultsStore
{
    /// <summary>Most equity values a sparkline carries (REQ-720).</summary>
    public const int SparklinePoints = 120;

    private const string RegistrySql = """
        SELECT *,
               epoch_us(registered_at) AS registered_at_us,
               epoch_us(holdout_opened_at) AS holdout_opened_at_us
        FROM read_parquet($path)
        """;

    private readonly string _root = Path.GetFullPath(options.Value.Path, environment.ContentRootPath);

    private string RegistryPath => Path.Combine(_root, StoreSchema.RegistryFile);

    private string TablePath(string hypothesis, string table) =>
        Path.Combine(_root, hypothesis, $"{table}.parquet");

    public StoreHealth Health()
    {
        if (!File.Exists(RegistryPath))
        {
            return new StoreHealth(_root, Exists: false, SchemaVersion: null, Compatible: true);
        }
        var version = Version(RegistryPath);
        return new StoreHealth(_root, Exists: true, version, version is null or StoreSchema.Version);
    }

    public IReadOnlyList<HypothesisSummary> Hypotheses()
    {
        if (!File.Exists(RegistryPath))
        {
            return [];
        }
        EnsureCompatible(RegistryPath);
        return Query(RegistryPath, RegistrySql, ReadSummary).Select(WithRunHeadline).ToList();
    }

    private HypothesisSummary WithRunHeadline(HypothesisSummary summary)
    {
        if (!summary.HasRun)
        {
            return summary;
        }
        var sharpe = Query(
            TablePath(summary.Hypothesis, "metrics"),
            """SELECT sharpe FROM read_parquet($path) WHERE "primary" """,
            row => row.OptionalNumber("sharpe"));
        var equity = Query(
            TablePath(summary.Hypothesis, "equity"),
            "SELECT equity FROM read_parquet($path) ORDER BY ts",
            row => row.Number("equity"));
        return summary with { TrainingSharpe = sharpe.Single(), Sparkline = Sparkline(equity, SparklinePoints) };
    }

    private static HypothesisSummary ReadSummary(DbDataReader row) => new(
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
        Sparkline: []);

    private static JsonElement Json(string text)
    {
        using var document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }

    /// <summary>Evenly spaced values, first and last included: display sampling, not a metric.</summary>
    internal static IReadOnlyList<double> Sparkline(IReadOnlyList<double> values, int points)
    {
        if (values.Count <= points)
        {
            return values;
        }
        var sampled = new double[points];
        for (var i = 0; i < points; i++)
        {
            sampled[i] = values[(int)((long)i * (values.Count - 1) / (points - 1))];
        }
        return sampled;
    }

    private static long? Version(string path) =>
        Query(path, "SELECT schema_version FROM read_parquet($path) LIMIT 1", row => row.Integer("schema_version"))
            .Cast<long?>()
            .FirstOrDefault();

    private static void EnsureCompatible(string path)
    {
        if (Version(path) is { } found && found != StoreSchema.Version)
        {
            throw new IncompatibleStoreException(Path.GetFileName(path), found);
        }
    }

    private static List<T> Query<T>(string path, string sql, Func<DbDataReader, T> map)
    {
        using var connection = new DuckDBConnection("DataSource=:memory:");
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        command.Parameters.Add(new DuckDBParameter("path", path));
        using var reader = command.ExecuteReader();
        var rows = new List<T>();
        while (reader.Read())
        {
            rows.Add(map(reader));
        }
        return rows;
    }
}
