using System.Net;
using System.Text.Json;

namespace QuantLab.Api.Tests;

public class DetailTests
{
    private static string Table(string hypothesis, string table) =>
        $"read_parquet('{Fixture.File(hypothesis, table + ".parquet")}')";

    [Fact]
    public async Task ARunSummaryCarriesTheStoredRunRow()
    {
        var detail = await Http.Ok("/api/hypotheses/demo_momentum");

        var stored = Fixture.Query($"SELECT * FROM {Table("demo_momentum", "run")}").Single();
        var run = detail.GetProperty("run");
        Assert.Equal(stored["run_id"], run.GetProperty("runId").GetString());
        Assert.Equal("synthetic", run.GetProperty("dataSource").GetString());
        Assert.Equal(stored["walk_forward_passed"], (object?)run.GetProperty("walkForward").GetProperty("passed").GetBoolean());
        Assert.Equal(stored["permutation_p_value"], run.GetProperty("permutation").Number("pValue"));
        Assert.Equal(stored["dsr"], run.GetProperty("multipleTesting").Number("dsr"));
        Assert.Equal(
            ["demo_momentum", "demo_reversal", "demo_pairs"],
            run.GetProperty("multipleTesting").GetProperty("trials").EnumerateArray().Select(t => t.GetString()));
        Assert.Equal("demo_pairs", run.GetProperty("contrast").GetProperty("hypothesis").GetString());
        Assert.Equal(stored["contrast_correlation"], run.GetProperty("contrast").Number("correlation"));
        Assert.Equal(90, run.GetProperty("strategyParams").GetProperty("lookback_days").GetInt32());
        Assert.Equal(stored["trades"], (object)run.GetProperty("trades").GetProperty("total").GetInt64());
        Assert.Equal("2026-09-24T12:00:00+00:00", run.GetProperty("generatedAt").GetString());
    }

    [Fact]
    public async Task EvidenceTablesKeepTheStoredOrderAndNumbers()
    {
        var detail = await Http.Ok("/api/hypotheses/demo_momentum");

        var metrics = Fixture.Query($"SELECT cost_model, sharpe, max_drawdown FROM {Table("demo_momentum", "metrics")} ORDER BY position");
        Assert.Equal(
            metrics.Select(m => ((string)m["cost_model"]!, (double?)m["sharpe"], (double?)m["max_drawdown"])),
            detail.GetProperty("metrics").EnumerateArray().Select(m =>
                (m.GetProperty("costModel").GetString()!, m.Number("sharpe"), m.Number("maxDrawdown"))));
        Assert.True(detail.GetProperty("metrics")[2].GetProperty("primary").GetBoolean());

        var windows = Fixture.Query($"SELECT sharpe, aggregate FROM {Table("demo_momentum", "walk_forward")} ORDER BY position");
        Assert.Equal(
            windows.Select(w => ((double?)w["sharpe"], (bool)w["aggregate"]!)),
            detail.GetProperty("walkForward").EnumerateArray().Select(w => (w.Number("sharpe"), w.GetProperty("aggregate").GetBoolean())));

        var regimes = Fixture.Query($"SELECT regime, share FROM {Table("demo_momentum", "regimes")} ORDER BY position");
        Assert.Equal(
            regimes.Select(r => ((string)r["regime"]!, (double)r["share"]!)),
            detail.GetProperty("regimes").EnumerateArray().Select(r => (r.GetProperty("regime").GetString()!, r.GetProperty("share").GetDouble())));

        var monthly = Fixture.Query($"SELECT net_return FROM {Table("demo_momentum", "monthly")} ORDER BY year, month");
        Assert.Equal(
            monthly.Select(m => (double)m["net_return"]!),
            detail.GetProperty("monthly").EnumerateArray().Select(m => m.GetProperty("netReturn").GetDouble()));

        var groups = detail.GetProperty("pnlGroups").EnumerateArray().Select(g => g.GetProperty("dimension").GetString()).ToList();
        Assert.Equal("regime", groups[0]);
        Assert.Equal("holding_period", groups[^1]);
        Assert.Empty(detail.GetProperty("diagnostics").EnumerateArray());
    }

    [Fact]
    public async Task APairsRunCarriesItsTrainingDiagnostics()
    {
        var detail = await Http.Ok("/api/hypotheses/demo_pairs");

        var stored = Fixture.Query($"SELECT label, value FROM {Table("demo_pairs", "diagnostics")} ORDER BY position");
        Assert.Equal(
            stored.Select(d => ((string)d["label"]!, (double?)d["value"])),
            detail.GetProperty("diagnostics").EnumerateArray().Select(d => (d.GetProperty("label").GetString()!, d.Number("value"))));
        Assert.Equal(JsonValueKind.Null, detail.GetProperty("run").GetProperty("contrast").ValueKind);
    }

    [Fact]
    public async Task AHypothesisWithoutARunHasANullRunAndEmptyEvidence()
    {
        var detail = await Http.Ok("/api/hypotheses/demo_reversal");

        Assert.Equal("proposed", detail.GetProperty("hypothesis").GetProperty("status").GetString());
        Assert.Equal(JsonValueKind.Null, detail.GetProperty("run").ValueKind);
        foreach (var list in new[] { "metrics", "walkForward", "regimes", "monthly", "pnlGroups", "diagnostics" })
        {
            Assert.Empty(detail.GetProperty(list).EnumerateArray());
        }
    }

    [Theory]
    [InlineData("/api/hypotheses/momentum_v1")]
    [InlineData("/api/hypotheses/..%2Fdemo_momentum")]
    [InlineData("/api/hypotheses/momentum_v1/equity")]
    [InlineData("/api/hypotheses/momentum_v1/trades")]
    public async Task AnUnknownHypothesisIs404ProblemJson(string path)
    {
        var (status, mediaType, body) = await Http.Get(Fixture.Store, path);

        Assert.Equal(HttpStatusCode.NotFound, status);
        Assert.Equal("application/problem+json", mediaType);
        Assert.StartsWith("Unknown hypothesis", body.GetProperty("title").GetString(), StringComparison.Ordinal);
    }
}
