using QuantLab.Api.Store;

namespace QuantLab.Api.Endpoints;

/// <summary>Read-only HTTP surface over the results store (REQ-720..726).</summary>
public static class ResultsEndpoints
{
    private static readonly Dictionary<string, TradeSort> Sorts =
        Enum.GetValues<TradeSort>().ToDictionary(sort => JsonName(sort.ToString()), StringComparer.Ordinal);

    public static IEndpointRouteBuilder MapResultsEndpoints(this IEndpointRouteBuilder app)
    {
        var api = app.MapGroup("/api");
        api.MapGet("/health", (IResultsStore store) => store.Health());
        api.MapGet("/hypotheses", (IResultsStore store) => store.Hypotheses());
        api.MapGet("/hypotheses/{id}", (string id, IResultsStore store) =>
            store.Hypothesis(id) is { } detail ? Results.Ok(detail) : UnknownHypothesis(id));
        api.MapGet("/hypotheses/{id}/equity", (string id, IResultsStore store) =>
            RunResource(store, id, () => store.Equity(id)));
        api.MapGet("/hypotheses/{id}/trades", (
            string id,
            string? instrument,
            string? side,
            string? sort,
            string? order,
            int? offset,
            int? limit,
            IResultsStore store) =>
        {
            var errors = new Dictionary<string, string[]>();
            if (side is not null and not ("long" or "short"))
            {
                errors["side"] = ["side is long or short"];
            }
            if (sort is not null && !Sorts.ContainsKey(sort))
            {
                errors["sort"] = [$"sort is one of {string.Join(", ", Sorts.Keys)}"];
            }
            if (order is not null and not ("asc" or "desc"))
            {
                errors["order"] = ["order is asc or desc"];
            }
            if (offset < 0)
            {
                errors["offset"] = ["offset is 0 or more"];
            }
            if (limit is < 1 or > TradeQuery.MaxLimit)
            {
                errors["limit"] = [$"limit is between 1 and {TradeQuery.MaxLimit}"];
            }
            if (errors.Count > 0)
            {
                return Results.ValidationProblem(errors);
            }
            var query = new TradeQuery(
                instrument,
                side,
                sort is null ? TradeSort.EntryTs : Sorts[sort],
                order == "desc",
                offset ?? 0,
                limit ?? TradeQuery.DefaultLimit);
            return RunResource(store, id, () => store.Trades(id, query));
        });
        return app;
    }

    /// <summary>A resource of the hypothesis's stored run: 404 for an unknown hypothesis
    /// and for one without a run (REQ-724).</summary>
    private static IResult RunResource<T>(IResultsStore store, string id, Func<T> read) =>
        store.State(id) switch
        {
            HypothesisState.HasRun => Results.Ok(read()),
            HypothesisState.NoRun => Results.Problem(
                statusCode: StatusCodes.Status404NotFound,
                title: $"No run of hypothesis '{id}' in the results store",
                detail: $"uv run quantlab run {id}"),
            _ => UnknownHypothesis(id),
        };

    private static IResult UnknownHypothesis(string id) =>
        Results.Problem(statusCode: StatusCodes.Status404NotFound, title: $"Unknown hypothesis '{id}'");

    private static string JsonName(string name) => char.ToLowerInvariant(name[0]) + name[1..];
}
