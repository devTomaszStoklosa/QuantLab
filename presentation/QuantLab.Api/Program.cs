using Microsoft.Extensions.FileProviders;
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

// The built React app (presentation/web/dist), when there is one. It routes on the URL
// hash, so there is no fallback route that could answer an unknown /api path with HTML.
var web = Path.GetFullPath(app.Configuration["Web:Root"] ?? "../web/dist", app.Environment.ContentRootPath);
if (Directory.Exists(web))
{
    var files = new PhysicalFileProvider(web);
    app.UseDefaultFiles(new DefaultFilesOptions { FileProvider = files });
    app.UseStaticFiles(new StaticFileOptions { FileProvider = files });
}

app.MapResultsEndpoints();

app.Run();

/// <summary>Entry point, public for the integration tests' WebApplicationFactory.</summary>
public partial class Program;
