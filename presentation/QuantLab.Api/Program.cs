using QuantLab.Api.Endpoints;
using QuantLab.Api.Results;

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<ResultsOptions>(builder.Configuration.GetSection(ResultsOptions.Section));
builder.Services.AddSingleton<IResultsStore, DuckDbResultsStore>();
builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<StoreExceptionHandler>();

var app = builder.Build();

app.UseExceptionHandler();
app.UseStatusCodePages();
app.MapResultsEndpoints();

app.Run();

/// <summary>Entry point, public for the integration tests' WebApplicationFactory.</summary>
public partial class Program;
