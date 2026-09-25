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
            ["demo_momentum", "demo_reversal", "demo_pairs", "demo_select"],
            run.GetProperty("multipleTesting").GetProperty("trials").EnumerateArray().Select(t => t.GetString()));
        Assert.Equal(stored["configurations"], (object)run.GetProperty("multipleTesting").GetProperty("configurations").GetInt64());
        Assert.Equal("demo_pairs", run.GetProperty("contrast").GetProperty("hypothesis").GetString());
        Assert.Equal(stored["contrast_correlation"], run.GetProperty("contrast").Number("correlation"));
        Assert.Equal(90, run.GetProperty("strategyParams").GetProperty("lookback_days").GetInt32());
        Assert.Equal(stored["trades"], (object)run.GetProperty("trades").GetProperty("total").GetInt64());
        Assert.Equal("2026-09-24T12:00:00+00:00", run.GetProperty("generatedAt").GetString());
    }

    [Fact]
    public async Task ARunNamesTheSignificanceTestItsCriterionChose()
    {
        var momentum = await Http.Ok("/api/hypotheses/demo_momentum");
        var equities = await Http.Ok("/api/hypotheses/demo_xsmom");

        Assert.Equal("day_shuffle", momentum.GetProperty("hypothesis").GetProperty("significanceTest").GetString());
        Assert.Equal("day_shuffle", momentum.GetProperty("run").GetProperty("permutation").GetProperty("test").GetString());
        Assert.Equal("random_portfolio", equities.GetProperty("hypothesis").GetProperty("significanceTest").GetString());
        var permutation = equities.GetProperty("run").GetProperty("permutation");
        Assert.Equal("random_portfolio", permutation.GetProperty("test").GetString());
        var stored = Fixture.Query($"SELECT permutation_p_value FROM {Table("demo_xsmom", "run")}").Single();
        Assert.Equal(stored["permutation_p_value"], permutation.Number("pValue"));
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

        var yearly = Fixture.Query($"SELECT year, net_return FROM {Table("demo_momentum", "yearly")} ORDER BY year");
        Assert.Equal(
            yearly.Select(y => ((long)y["year"]!, (double)y["net_return"]!)),
            detail.GetProperty("yearly").EnumerateArray().Select(y => (y.GetProperty("year").GetInt64(), y.GetProperty("netReturn").GetDouble())));
        Assert.Equal(
            Fixture.Query($"SELECT DISTINCT instrument_id FROM {Table("demo_momentum", "trades")} ORDER BY 1").Select(r => (string)r["instrument_id"]!),
            detail.GetProperty("tradeInstruments").EnumerateArray().Select(i => i.GetString()!));

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
        foreach (var list in new[] { "metrics", "walkForward", "regimes", "monthly", "yearly", "pnlGroups", "diagnostics", "selection", "cpcvPaths", "cpcvChoices", "tradeInstruments" })
        {
            Assert.Empty(detail.GetProperty(list).EnumerateArray());
        }
    }

    [Fact]
    public async Task ASelectionRunCarriesItsGridItsYearlyChoicesAndItsCpcvPaths()
    {
        var detail = await Http.Ok("/api/hypotheses/demo_select");

        var stored = Fixture.Query($"SELECT * FROM {Table("demo_select", "run")}").Single();
        var run = detail.GetProperty("run");
        Assert.Equal("cpcv", run.GetProperty("inSample").GetProperty("validation").GetString());
        Assert.Equal(stored["in_sample_passed"], (object?)run.GetProperty("inSample").GetProperty("passed").GetBoolean());
        var grid = run.GetProperty("grid");
        Assert.Equal("2020-01-01", grid.GetProperty("start").GetString());
        Assert.Equal(stored["grid_pbo"], grid.GetProperty("pbo").Number("value"));
        Assert.Equal(stored["grid_pbo_splits"], (object)grid.GetProperty("pbo").GetProperty("splits").GetInt64());
        var cpcv = grid.GetProperty("cpcv");
        Assert.Equal(10, cpcv.GetProperty("groups").GetInt64());
        Assert.Equal(stored["cpcv_paths"], (object)cpcv.GetProperty("paths").GetInt64());
        Assert.Equal(stored["cpcv_median_sharpe"], cpcv.Number("medianSharpe"));
        Assert.Equal(stored["cpcv_rule"], cpcv.GetProperty("rule").GetString());
        Assert.Equal("cpcv", detail.GetProperty("hypothesis").GetProperty("inSampleValidation").GetString());
        Assert.Equal(3, detail.GetProperty("hypothesis").GetProperty("configurations").GetInt64());

        var selection = Fixture.Query($"SELECT year, value, sharpe, chosen FROM {Table("demo_select", "selection")} ORDER BY year, position");
        Assert.Equal(
            selection.Select(s => ((long)s["year"]!, (string)s["value"]!, (double?)s["sharpe"], (bool)s["chosen"]!)),
            detail.GetProperty("selection").EnumerateArray().Select(s => (
                s.GetProperty("year").GetInt64(), s.GetProperty("value").GetString()!, s.Number("sharpe"), s.GetProperty("chosen").GetBoolean())));
        var paths = Fixture.Query($"SELECT sharpe FROM {Table("demo_select", "cpcv_paths")} ORDER BY position");
        Assert.Equal(
            paths.Select(p => (double?)p["sharpe"]),
            detail.GetProperty("cpcvPaths").EnumerateArray().Select(p => p.Number("sharpe")));
        var choices = Fixture.Query($"SELECT value, share FROM {Table("demo_select", "cpcv_choices")} ORDER BY position");
        Assert.Equal(
            choices.Select(c => ((string)c["value"]!, (double)c["share"]!)),
            detail.GetProperty("cpcvChoices").EnumerateArray().Select(c => (c.GetProperty("value").GetString()!, c.GetProperty("share").GetDouble())));
    }

    [Fact]
    public async Task ARunWithoutAGridHasANullGridAndItsWalkForwardAsTheGate()
    {
        var detail = await Http.Ok("/api/hypotheses/demo_momentum");

        var run = detail.GetProperty("run");
        Assert.Equal(JsonValueKind.Null, run.GetProperty("grid").ValueKind);
        Assert.Equal("walk_forward", run.GetProperty("inSample").GetProperty("validation").GetString());
        Assert.Equal(
            run.GetProperty("walkForward").GetProperty("passed").GetBoolean(),
            run.GetProperty("inSample").GetProperty("passed").GetBoolean());
        foreach (var list in new[] { "selection", "cpcvPaths", "cpcvChoices" })
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
