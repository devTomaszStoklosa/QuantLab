using QuantLab.Api.Results;

namespace QuantLab.Api.Endpoints;

/// <summary>Read-only HTTP surface over the results store (REQ-720..726).</summary>
public static class ResultsEndpoints
{
    public static IEndpointRouteBuilder MapResultsEndpoints(this IEndpointRouteBuilder app)
    {
        var api = app.MapGroup("/api");
        api.MapGet("/health", (IResultsStore store) => store.Health());
        api.MapGet("/hypotheses", (IResultsStore store) => store.Hypotheses());
        return app;
    }
}
