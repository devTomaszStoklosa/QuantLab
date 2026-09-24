using System.Data.Common;
using DuckDB.NET.Data;
using Microsoft.AspNetCore.Mvc.Testing;

namespace QuantLab.Api.Tests;

/// <summary>
/// The synthetic results store written by the Python pipeline
/// (presentation/fixtures/results, tests/test_results_fixture.py): the tests read the
/// same files the API does, so they check the Python-to-.NET contract itself.
/// </summary>
internal static class Fixture
{
    public static string Store { get; } = FindStore();

    private static string FindStore()
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            var candidate = Path.Combine(directory.FullName, "presentation", "fixtures", "results");
            if (Directory.Exists(candidate))
            {
                return candidate;
            }
        }
        throw new DirectoryNotFoundException("presentation/fixtures/results not found above the test binaries");
    }

    public static WebApplicationFactory<Program> Api(string store) =>
        new WebApplicationFactory<Program>().WithWebHostBuilder(host => host
            .UseSetting("Results:Path", store)
            .UseSetting("Logging:LogLevel:Default", "Warning"));

    /// <summary>Rows of a query run straight on the store's Parquet files, bypassing the API.</summary>
    public static List<Dictionary<string, object?>> Query(string sql)
    {
        using var connection = new DuckDBConnection("DataSource=:memory:");
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        using var reader = command.ExecuteReader();
        var rows = new List<Dictionary<string, object?>>();
        while (reader.Read())
        {
            rows.Add(Enumerable.Range(0, reader.FieldCount)
                .ToDictionary(reader.GetName, i => reader.IsDBNull(i) ? null : reader.GetValue(i)));
        }
        return rows;
    }

    public static string File(params string[] parts) => Path.Combine([Store, .. parts]).Replace('\\', '/');
}
