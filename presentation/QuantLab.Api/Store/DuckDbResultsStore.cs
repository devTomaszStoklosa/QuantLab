using System.Data.Common;
using DuckDB.NET.Data;
using Microsoft.Extensions.Options;

namespace QuantLab.Api.Store;

/// <summary>
/// Reads the Parquet results store through DuckDB (ADR-0008): one in-memory connection
/// per call, so no file stays open while <c>quantlab run</c> replaces it. File paths
/// and filter values are always SQL parameters, sort columns come from a fixed list,
/// and a hypothesis's directory is only ever opened for an id the registry holds.
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

    private static readonly Dictionary<TradeSort, string> SortColumns = new()
    {
        [TradeSort.EntryTs] = "entry_ts",
        [TradeSort.ExitTs] = "exit_ts",
        [TradeSort.InstrumentId] = "instrument_id",
        [TradeSort.Size] = "size",
        [TradeSort.GrossPnl] = "gross_pnl",
        [TradeSort.Costs] = "costs",
        [TradeSort.NetPnl] = "net_pnl",
        [TradeSort.HoldingDays] = "holding_days",
    };

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
        using var db = Open();
        var version = Version(db, RegistryPath);
        return new StoreHealth(_root, Exists: true, version, version is null or StoreSchema.Version);
    }

    public IReadOnlyList<HypothesisSummary> Hypotheses()
    {
        using var db = Open();
        return Registry(db, hypothesis: null).Select(summary => WithRunHeadline(db, summary)).ToList();
    }

    public HypothesisState State(string hypothesis)
    {
        using var db = Open();
        return Registry(db, hypothesis).SingleOrDefault() switch
        {
            null => HypothesisState.Unknown,
            { HasRun: true } => HypothesisState.HasRun,
            _ => HypothesisState.NoRun,
        };
    }

    public HypothesisDetail? Hypothesis(string hypothesis)
    {
        using var db = Open();
        if (Registry(db, hypothesis).SingleOrDefault() is not { } summary)
        {
            return null;
        }
        summary = WithRunHeadline(db, summary);
        if (!summary.HasRun)
        {
            return new HypothesisDetail(summary, null, [], [], [], [], [], []);
        }
        var runPath = TablePath(summary.Hypothesis, "run");
        EnsureCompatible(db, runPath);
        return new HypothesisDetail(
            summary,
            Query(db, runPath, "SELECT *, epoch_us(generated_at) AS generated_at_us FROM read_parquet($path)", Rows.Run).Single(),
            Table(db, summary.Hypothesis, "metrics", "position", Rows.Metrics),
            Table(db, summary.Hypothesis, "walk_forward", "position", Rows.Window),
            Table(db, summary.Hypothesis, "regimes", "position", Rows.Regime),
            Table(db, summary.Hypothesis, "monthly", "year, month", Rows.Month),
            Table(db, summary.Hypothesis, "pnl_groups", orderBy: null, Rows.Group), // as written: regime, then holding period
            Table(db, summary.Hypothesis, "diagnostics", "position", Rows.Diagnostic));
    }

    public IReadOnlyList<EquityPoint> Equity(string hypothesis)
    {
        using var db = Open();
        return Table(db, RunHypothesis(db, hypothesis), "equity", "ts", Rows.Equity);
    }

    public TradePage Trades(string hypothesis, TradeQuery query)
    {
        using var db = Open();
        var path = TablePath(RunHypothesis(db, hypothesis), "trades");
        var filters = new List<string>();
        var parameters = new Dictionary<string, object>();
        if (query.Instrument is not null)
        {
            filters.Add("instrument_id = $instrument");
            parameters["instrument"] = query.Instrument;
        }
        if (query.Side is not null)
        {
            filters.Add("side = $side");
            parameters["side"] = query.Side;
        }
        var where = filters.Count == 0 ? "" : $"WHERE {string.Join(" AND ", filters)}";
        var total = Query(db, path, $"SELECT count(*) AS total FROM read_parquet($path) {where}", row => row.Integer("total"), parameters).Single();
        var order = $"{SortColumns[query.Sort]} {(query.Descending ? "DESC" : "ASC")}, trade_id ASC";
        var items = Query(
            db,
            path,
            $"SELECT * FROM read_parquet($path) {where} ORDER BY {order} LIMIT $limit OFFSET $offset",
            Rows.Trade,
            new Dictionary<string, object>(parameters) { ["limit"] = query.Limit, ["offset"] = query.Offset });
        return new TradePage(total, query.Offset, query.Limit, items);
    }

    /// <summary>Registry rows, all or the one with this id; empty when there is no store.</summary>
    private List<HypothesisSummary> Registry(DuckDBConnection db, string? hypothesis)
    {
        if (!File.Exists(RegistryPath))
        {
            return [];
        }
        EnsureCompatible(db, RegistryPath);
        return hypothesis is null
            ? Query(db, RegistryPath, RegistrySql, Rows.Summary)
            : Query(db, RegistryPath, $"{RegistrySql} WHERE hypothesis = $hypothesis", Rows.Summary,
                new Dictionary<string, object> { ["hypothesis"] = hypothesis });
    }

    /// <summary>The id as the registry holds it, for a hypothesis with a stored run.</summary>
    private string RunHypothesis(DuckDBConnection db, string hypothesis)
    {
        if (Registry(db, hypothesis).SingleOrDefault() is not { HasRun: true } summary)
        {
            throw new InvalidOperationException($"No stored run of hypothesis '{hypothesis}'");
        }
        EnsureCompatible(db, TablePath(summary.Hypothesis, "run"));
        return summary.Hypothesis;
    }

    private HypothesisSummary WithRunHeadline(DuckDBConnection db, HypothesisSummary summary)
    {
        if (!summary.HasRun)
        {
            return summary;
        }
        var sharpe = Query(
            db,
            TablePath(summary.Hypothesis, "metrics"),
            """SELECT sharpe FROM read_parquet($path) WHERE "primary" """,
            row => row.OptionalNumber("sharpe"));
        var equity = Query(
            db,
            TablePath(summary.Hypothesis, "equity"),
            "SELECT equity FROM read_parquet($path) ORDER BY ts",
            row => row.Number("equity"));
        return summary with { TrainingSharpe = sharpe.Single(), Sparkline = Sparkline(equity, SparklinePoints) };
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

    private List<T> Table<T>(
        DuckDBConnection db, string hypothesis, string table, string? orderBy, Func<DbDataReader, T> map) =>
        Query(
            db,
            TablePath(hypothesis, table),
            orderBy is null ? "SELECT * FROM read_parquet($path)" : $"SELECT * FROM read_parquet($path) ORDER BY {orderBy}",
            map);

    private static long? Version(DuckDBConnection db, string path) =>
        Query(db, path, "SELECT schema_version FROM read_parquet($path) LIMIT 1", row => row.Integer("schema_version"))
            .Cast<long?>()
            .FirstOrDefault();

    private static void EnsureCompatible(DuckDBConnection db, string path)
    {
        if (Version(db, path) is { } found && found != StoreSchema.Version)
        {
            throw new IncompatibleStoreException(Path.GetFileName(path), found);
        }
    }

    private static DuckDBConnection Open()
    {
        var connection = new DuckDBConnection("DataSource=:memory:");
        connection.Open();
        return connection;
    }

    private static List<T> Query<T>(
        DuckDBConnection db,
        string path,
        string sql,
        Func<DbDataReader, T> map,
        Dictionary<string, object>? parameters = null)
    {
        using var command = db.CreateCommand();
        command.CommandText = sql;
        command.Parameters.Add(new DuckDBParameter("path", path));
        foreach (var (name, value) in parameters ?? [])
        {
            command.Parameters.Add(new DuckDBParameter(name, value));
        }
        using var reader = command.ExecuteReader();
        var rows = new List<T>();
        while (reader.Read())
        {
            rows.Add(map(reader));
        }
        return rows;
    }
}
