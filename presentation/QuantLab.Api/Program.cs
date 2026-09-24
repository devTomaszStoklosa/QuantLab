using QuantLab.Api.Endpoints;
using QuantLab.Api.Store;

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<ResultsOptions>(builder.Configuration.GetSection(ResultsOptions.Section));
builder.Services.AddSingleton<IResultsStore, DuckDbResultsStore>();
builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<StoreExceptionHandler>();
// A malformed query parameter is a 400 problem, in Development too (REQ-724).
builder.Services.Configure<RouteHandlerOptions>(routes => routes.ThrowOnBadRequest = false);

var app = builder.Build();

app.UseExceptionHandler();
app.UseStatusCodePages();
app.MapResultsEndpoints();

app.Run();

/// <summary>Entry point, public for the integration tests' WebApplicationFactory.</summary>
public partial class Program;
