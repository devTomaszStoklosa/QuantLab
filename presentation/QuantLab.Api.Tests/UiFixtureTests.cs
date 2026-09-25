using System.Text.Json;
using System.Text.Json.Nodes;

namespace QuantLab.Api.Tests;

/// <summary>
/// The UI's tests run on captured API responses; these tests keep them what the API
/// returns for the synthetic store, so the TypeScript types are checked against the real
/// contract. After an intended change: QUANTLAB_UPDATE_FIXTURES=1 dotnet test ...
/// </summary>
public class UiFixtureTests
{
    private static readonly Dictionary<string, string> Captures = new()
    {
        ["registry.json"] = "/api/hypotheses",
        ["demo_momentum.json"] = "/api/hypotheses/demo_momentum",
        ["demo_reversal.json"] = "/api/hypotheses/demo_reversal",
        ["demo_pairs.json"] = "/api/hypotheses/demo_pairs",
        ["demo_select.json"] = "/api/hypotheses/demo_select",
        ["demo_momentum-equity.json"] = "/api/hypotheses/demo_momentum/equity",
        ["demo_momentum-trades.json"] = "/api/hypotheses/demo_momentum/trades?limit=25",
    };

    private static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };

    public static TheoryData<string> Files => new(Captures.Keys);

    [Theory]
    [MemberData(nameof(Files))]
    public async Task TheUiTestDataIsWhatTheApiReturns(string file)
    {
        using var api = Fixture.Api(Fixture.Store);
        var response = JsonNode.Parse(await api.CreateClient().GetStringAsync(Captures[file], TestContext.Current.CancellationToken));
        var path = Path.Combine(Fixture.WebTestData, file);
        if (Environment.GetEnvironmentVariable("QUANTLAB_UPDATE_FIXTURES") == "1")
        {
            // The equity curve is long; one line keeps the file small.
            var text = file.EndsWith("-equity.json", StringComparison.Ordinal)
                ? response!.ToJsonString()
                : response!.ToJsonString(Indented);
            await File.WriteAllTextAsync(path, text + "\n", TestContext.Current.CancellationToken);
        }

        var captured = JsonNode.Parse(await File.ReadAllTextAsync(path, TestContext.Current.CancellationToken));

        Assert.True(JsonNode.DeepEquals(captured, response), $"{file} is stale; regenerate it (see UiFixtureTests)");
    }
}
