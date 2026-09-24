using System.Net;

namespace QuantLab.Api.Tests;

public class EquityTests
{
    [Fact]
    public async Task ReturnsEverySnapshotInDateOrder()
    {
        var equity = (await Http.Ok("/api/hypotheses/demo_pairs/equity")).EnumerateArray().ToList();

        var stored = Fixture.Query($"SELECT strftime(ts, '%Y-%m-%d') AS ts, equity, drawdown FROM read_parquet('{Fixture.File("demo_pairs", "equity.parquet")}') ORDER BY ts");
        Assert.Equal(
            stored.Select(p => ((string)p["ts"]!, (double)p["equity"]!, (double)p["drawdown"]!)),
            equity.Select(p => (p.GetProperty("ts").GetString()!, p.GetProperty("equity").GetDouble(), p.GetProperty("drawdown").GetDouble())));
    }

    [Theory]
    [InlineData("/api/hypotheses/demo_reversal/equity")]
    [InlineData("/api/hypotheses/demo_reversal/trades")]
    public async Task AHypothesisWithoutARunIs404NamingTheCommand(string path)
    {
        var (status, mediaType, body) = await Http.Get(Fixture.Store, path);

        Assert.Equal(HttpStatusCode.NotFound, status);
        Assert.Equal("application/problem+json", mediaType);
        Assert.Equal("No run of hypothesis 'demo_reversal' in the results store", body.GetProperty("title").GetString());
        Assert.Equal("uv run quantlab run demo_reversal", body.GetProperty("detail").GetString());
    }
}

public class TradesTests
{
    private static readonly string Trades = $"read_parquet('{Fixture.File("demo_momentum", "trades.parquet")}')";

    private static List<long> Ids(string sql) =>
        Fixture.Query(sql).Select(row => (long)row["trade_id"]!).ToList();

    private static List<long> Ids(System.Text.Json.JsonElement page) =>
        page.GetProperty("items").EnumerateArray().Select(t => t.GetProperty("tradeId").GetInt64()).ToList();

    [Fact]
    public async Task TheDefaultPageIsTheFirstHundredByEntryDate()
    {
        var page = await Http.Ok("/api/hypotheses/demo_momentum/trades");

        Assert.Equal((long)Fixture.Query($"SELECT count(*) AS n FROM {Trades}").Single()["n"]!, page.GetProperty("total").GetInt64());
        Assert.Equal(0, page.GetProperty("offset").GetInt32());
        Assert.Equal(100, page.GetProperty("limit").GetInt32());
        Assert.Equal(Ids($"SELECT trade_id FROM {Trades} ORDER BY entry_ts, trade_id LIMIT 100"), Ids(page));
    }

    [Fact]
    public async Task FiltersSortsAndPagesInTheStore()
    {
        var page = await Http.Ok("/api/hypotheses/demo_momentum/trades?instrument=eth-usdt&side=short&sort=netPnl&order=desc&offset=2&limit=5");

        var expected = Ids($"SELECT trade_id FROM {Trades} WHERE instrument_id = 'eth-usdt' AND side = 'short' ORDER BY net_pnl DESC, trade_id LIMIT 5 OFFSET 2");
        Assert.Equal(expected, Ids(page));
        Assert.Equal(
            (long)Fixture.Query($"SELECT count(*) AS n FROM {Trades} WHERE instrument_id = 'eth-usdt' AND side = 'short'").Single()["n"]!,
            page.GetProperty("total").GetInt64());
    }

    [Fact]
    public async Task ATradeCarriesTheStoredNumbers()
    {
        var trade = (await Http.Ok("/api/hypotheses/demo_momentum/trades?limit=1")).GetProperty("items")[0];

        var stored = Fixture.Query($"SELECT * FROM {Trades} ORDER BY entry_ts, trade_id LIMIT 1").Single();
        Assert.Equal((double)stored["net_pnl"]!, trade.GetProperty("netPnl").GetDouble());
        Assert.Equal((double)stored["entry_price"]!, trade.GetProperty("entryPrice").GetDouble());
        Assert.Equal((string)stored["regime_at_entry"]!, trade.GetProperty("regimeAtEntry").GetString());
        Assert.Equal((bool)stored["open_at_end"]!, trade.GetProperty("openAtEnd").GetBoolean());
    }

    [Fact]
    public async Task AnInstrumentWithoutTradesIsAnEmptyPage()
    {
        var page = await Http.Ok("/api/hypotheses/demo_momentum/trades?instrument=doge-usdt");

        Assert.Equal(0, page.GetProperty("total").GetInt64());
        Assert.Empty(page.GetProperty("items").EnumerateArray());
    }

    [Theory]
    [InlineData("side=flat", "side")]
    [InlineData("sort=entry_ts", "sort")]
    [InlineData("order=up", "order")]
    [InlineData("offset=-1", "offset")]
    [InlineData("limit=0", "limit")]
    [InlineData("limit=1001", "limit")]
    public async Task AnInvalidParameterIs400NamingIt(string query, string parameter)
    {
        var (status, mediaType, body) = await Http.Get(Fixture.Store, $"/api/hypotheses/demo_momentum/trades?{query}");

        Assert.Equal(HttpStatusCode.BadRequest, status);
        Assert.Equal("application/problem+json", mediaType);
        Assert.True(body.GetProperty("errors").TryGetProperty(parameter, out _));
    }

    [Fact]
    public async Task ANonNumericLimitIs400()
    {
        var (status, mediaType, _) = await Http.Get(Fixture.Store, "/api/hypotheses/demo_momentum/trades?limit=ten");

        Assert.Equal(HttpStatusCode.BadRequest, status);
        Assert.Equal("application/problem+json", mediaType);
    }
}
