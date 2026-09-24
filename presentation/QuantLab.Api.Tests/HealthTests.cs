using System.Net.Http.Json;
using QuantLab.Api.Store;

namespace QuantLab.Api.Tests;

public class HealthTests
{
    [Fact]
    public async Task ReportsACompatibleStore()
    {
        using var api = Fixture.Api(Fixture.Store);

        var health = await api.CreateClient().GetFromJsonAsync<StoreHealth>("/api/health", TestContext.Current.CancellationToken);

        Assert.Equal(new StoreHealth(Fixture.Store, true, StoreSchema.Version, true), health);
    }

    [Fact]
    public async Task ReportsAMissingStoreWithoutFailing()
    {
        var missing = Path.Combine(Path.GetTempPath(), $"quantlab-missing-{Guid.NewGuid():N}");
        using var api = Fixture.Api(missing);

        var health = await api.CreateClient().GetFromJsonAsync<StoreHealth>("/api/health", TestContext.Current.CancellationToken);

        Assert.Equal(new StoreHealth(missing, false, null, true), health);
    }
}
