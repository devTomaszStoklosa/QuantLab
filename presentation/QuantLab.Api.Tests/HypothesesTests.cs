using System.Net;
using System.Text.Json;
using DuckDB.NET.Data;
using QuantLab.Api.Store;

namespace QuantLab.Api.Tests;

public class HypothesesTests
{
    private static async Task<JsonElement> Get(string store, string path)
    {
        using var api = Fixture.Api(store);
        var response = await api.CreateClient().GetAsync(path, TestContext.Current.CancellationToken);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken));
        return document.RootElement.Clone();
    }

    [Fact]
    public async Task ListsTheRegistryInItsOrderWithTheStatusPythonComputed()
    {
        var hypotheses = await Get(Fixture.Store, "/api/hypotheses");

        var expected = Fixture.Query($"SELECT hypothesis, status, has_run, frozen_at_commit, trials_on_same_data FROM read_parquet('{Fixture.File("hypotheses.parquet")}')");
        Assert.Equal(
            expected.Select(row => (row["hypothesis"], row["status"], row["has_run"], row["frozen_at_commit"], row["trials_on_same_data"])),
            hypotheses.EnumerateArray().Select(h => ((object?)h.GetProperty("hypothesis").GetString(),
                (object?)h.GetProperty("status").GetString(), (object?)h.GetProperty("hasRun").GetBoolean(),
                (object?)h.GetProperty("frozenAtCommit").GetString(), (object?)h.GetProperty("trialsOnSameData").GetInt64())));
    }

    [Fact]
    public async Task CarriesTheOpenedHoldoutRecordAndNullForASealedOne()
    {
        var hypotheses = (await Get(Fixture.Store, "/api/hypotheses")).EnumerateArray().ToList();

        var registry = Fixture.Query($"SELECT holdout_sharpe, holdout_p_value, holdout_verdict FROM read_parquet('{Fixture.File("hypotheses.parquet")}') WHERE hypothesis = 'demo_momentum'").Single();
        var holdout = hypotheses[0].GetProperty("holdout");
        Assert.Equal((double)registry["holdout_sharpe"]!, holdout.GetProperty("sharpe").GetDouble());
        Assert.Equal((double)registry["holdout_p_value"]!, holdout.GetProperty("pValue").GetDouble());
        Assert.Equal((string)registry["holdout_verdict"]!, holdout.GetProperty("verdict").GetString());
        Assert.Equal("2026-09-24T12:00:00+00:00", holdout.GetProperty("openedAt").GetString());
        Assert.Equal(JsonValueKind.Null, hypotheses[1].GetProperty("holdout").ValueKind);
    }

    [Fact]
    public async Task HeadlinesARunWithItsPrimarySharpeAndASampledEquityCurve()
    {
        var pairs = (await Get(Fixture.Store, "/api/hypotheses")).EnumerateArray()
            .Single(h => h.GetProperty("hypothesis").GetString() == "demo_pairs");

        var sharpe = Fixture.Query($"""SELECT sharpe FROM read_parquet('{Fixture.File("demo_pairs", "metrics.parquet")}') WHERE "primary" """).Single()["sharpe"];
        var equity = Fixture.Query($"SELECT equity FROM read_parquet('{Fixture.File("demo_pairs", "equity.parquet")}') ORDER BY ts").Select(row => (double)row["equity"]!).ToList();
        var sparkline = pairs.GetProperty("sparkline").EnumerateArray().Select(v => v.GetDouble()).ToList();
        Assert.Equal((double)sharpe!, pairs.GetProperty("trainingSharpe").GetDouble());
        Assert.Equal(DuckDbResultsStore.SparklinePoints, sparkline.Count);
        Assert.Equal(equity[0], sparkline[0]);
        Assert.Equal(equity[^1], sparkline[^1]);
        Assert.All(sparkline, value => Assert.Contains(value, equity));
        Assert.Equal("synthetic", pairs.GetProperty("dataSource").GetString());
    }

    [Fact]
    public async Task AHypothesisWithoutARunHasNullsNotZeros()
    {
        var reversal = (await Get(Fixture.Store, "/api/hypotheses")).EnumerateArray()
            .Single(h => h.GetProperty("hypothesis").GetString() == "demo_reversal");

        Assert.False(reversal.GetProperty("hasRun").GetBoolean());
        Assert.Equal(JsonValueKind.Null, reversal.GetProperty("trainingSharpe").ValueKind);
        Assert.Empty(reversal.GetProperty("sparkline").EnumerateArray());
        Assert.Equal(JsonValueKind.Null, reversal.GetProperty("dataSource").ValueKind);
        Assert.Equal("proposed", reversal.GetProperty("status").GetString());
    }

    [Fact]
    public async Task WritesIsoDatesAndTheDefinitionParametersAsJson()
    {
        var momentum = (await Get(Fixture.Store, "/api/hypotheses"))[0];

        Assert.Equal("2020-01-01", momentum.GetProperty("trainingStart").GetString());
        Assert.Equal("2023-06-30", momentum.GetProperty("holdoutEnd").GetString());
        Assert.Equal("2026-09-01T09:00:00+00:00", momentum.GetProperty("registeredAt").GetString());
        Assert.Equal(90, momentum.GetProperty("parameters").GetProperty("lookback_days").GetInt32());
        Assert.Equal("realistic-10bps-k0.05-vol30d", momentum.GetProperty("costModel").GetString());
    }

    [Fact]
    public async Task AMissingStoreIsAnEmptyRegistry()
    {
        var hypotheses = await Get(Path.Combine(Path.GetTempPath(), $"quantlab-missing-{Guid.NewGuid():N}"), "/api/hypotheses");

        Assert.Empty(hypotheses.EnumerateArray());
    }

    [Fact]
    public async Task AStoreOfAnotherSchemaVersionIs503NamingBothVersions()
    {
        var store = Directory.CreateTempSubdirectory("quantlab-store-").FullName;
        using (var connection = new DuckDBConnection("DataSource=:memory:"))
        {
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = $"COPY (SELECT 2::BIGINT AS schema_version) TO '{Path.Combine(store, "hypotheses.parquet").Replace('\\', '/')}' (FORMAT PARQUET)";
            command.ExecuteNonQuery();
        }
        using var api = Fixture.Api(store);

        var response = await api.CreateClient().GetAsync("/api/hypotheses", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
        var body = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        Assert.Contains("schema version 2", body, StringComparison.Ordinal);
        Assert.Contains("reads version 1", body, StringComparison.Ordinal);
    }
}

public class SparklineTests
{
    [Fact]
    public void AShortCurveIsKeptWhole()
    {
        double[] values = [1.0, 1.1, 0.9];

        Assert.Equal(values, DuckDbResultsStore.Sparkline(values, 120));
    }

    [Fact]
    public void ALongCurveIsSampledEvenlyWithBothEnds()
    {
        var values = Enumerable.Range(0, 1001).Select(i => (double)i).ToList();

        var sampled = DuckDbResultsStore.Sparkline(values, 5);

        Assert.Equal([0.0, 250.0, 500.0, 750.0, 1000.0], sampled);
    }
}
