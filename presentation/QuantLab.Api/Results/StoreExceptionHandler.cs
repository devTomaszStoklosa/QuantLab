using Microsoft.AspNetCore.Diagnostics;

namespace QuantLab.Api.Results;

/// <summary>An incompatible store is 503 with both versions named, not a 500 (REQ-725).</summary>
internal sealed class StoreExceptionHandler(IProblemDetailsService problems) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext, Exception exception, CancellationToken cancellationToken)
    {
        if (exception is not IncompatibleStoreException)
        {
            return false;
        }
        httpContext.Response.StatusCode = StatusCodes.Status503ServiceUnavailable;
        return await problems.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            Exception = exception,
            ProblemDetails =
            {
                Status = StatusCodes.Status503ServiceUnavailable,
                Title = "Results store has an incompatible schema version",
                Detail = exception.Message,
            },
        });
    }
}
