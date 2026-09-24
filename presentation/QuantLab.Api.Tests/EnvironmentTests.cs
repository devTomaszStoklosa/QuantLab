using DuckDB.NET.Data;

namespace QuantLab.Api.Tests;

/// <summary>
/// DuckDB's native library in .NET, like tests/test_environment.py for Python's native
/// packages: the development machine has no AVX2 (CLAUDE.md), so this must pass there.
/// </summary>
public class EnvironmentTests
{
    [Fact]
    public void DuckDbNativeLibraryLoadsAndRuns()
    {
        using var connection = new DuckDBConnection("DataSource=:memory:");
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT sum(i)::BIGINT FROM range(101) t(i)";

        Assert.Equal(5050L, command.ExecuteScalar());
    }

    [Fact]
    public void DuckDbReadsParquetWrittenByPython()
    {
        var rows = Fixture.Query($"SELECT count(*) AS n FROM read_parquet('{Fixture.File("hypotheses.parquet")}')");

        Assert.Equal(3L, rows.Single()["n"]);
    }
}
