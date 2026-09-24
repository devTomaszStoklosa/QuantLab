using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;

namespace QuantLab.Api.Tests;

public class WebAppTests
{
    [Fact]
    public async Task ServesTheBuiltAppAndKeepsApiErrorsAsProblems()
    {
        var web = Directory.CreateTempSubdirectory("quantlab-web-").FullName;
        await File.WriteAllTextAsync(Path.Combine(web, "index.html"), "<!doctype html><title>QuantLab</title>", TestContext.Current.CancellationToken);
        using var api = Fixture.Api(Fixture.Store).WithWebHostBuilder(host => host.UseSetting("Web:Root", web));
        var client = api.CreateClient();

        var page = await client.GetAsync("/", TestContext.Current.CancellationToken);
        var unknown = await client.GetAsync("/api/nothing-here", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.OK, page.StatusCode);
        Assert.Contains("<title>QuantLab</title>", await page.Content.ReadAsStringAsync(TestContext.Current.CancellationToken), StringComparison.Ordinal);
        Assert.Equal(HttpStatusCode.NotFound, unknown.StatusCode);
        Assert.Equal("application/problem+json", unknown.Content.Headers.ContentType?.MediaType);
    }
}
