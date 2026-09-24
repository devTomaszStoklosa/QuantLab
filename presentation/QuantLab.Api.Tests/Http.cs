using System.Net;
using System.Text.Json;

namespace QuantLab.Api.Tests;

internal static class Http
{
    public static async Task<(HttpStatusCode Status, string? MediaType, JsonElement Body)> Get(string store, string path)
    {
        using var api = Fixture.Api(store);
        var response = await api.CreateClient().GetAsync(path, TestContext.Current.CancellationToken);
        var text = await response.Content.ReadAsStringAsync(TestContext.Current.CancellationToken);
        using var document = JsonDocument.Parse(text.Length == 0 ? "null" : text);
        return (response.StatusCode, response.Content.Headers.ContentType?.MediaType, document.RootElement.Clone());
    }

    public static async Task<JsonElement> Ok(string path)
    {
        var (status, _, body) = await Get(Fixture.Store, path);
        Assert.Equal(HttpStatusCode.OK, status);
        return body;
    }

    public static double? Number(this JsonElement element, string name) =>
        element.GetProperty(name).ValueKind == JsonValueKind.Null ? null : element.GetProperty(name).GetDouble();
}
