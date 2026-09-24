using System.Data.Common;

namespace QuantLab.Api.Store;

/// <summary>Typed column access by name; NULL stays null, never 0 (REQ-726).</summary>
internal static class ReaderExtensions
{
    public static string Text(this DbDataReader row, string column) =>
        row.GetString(row.GetOrdinal(column));

    public static string? OptionalText(this DbDataReader row, string column) =>
        row.IsDBNull(row.GetOrdinal(column)) ? null : row.Text(column);

    public static double Number(this DbDataReader row, string column) =>
        row.GetDouble(row.GetOrdinal(column));

    public static double? OptionalNumber(this DbDataReader row, string column) =>
        row.IsDBNull(row.GetOrdinal(column)) ? null : row.Number(column);

    public static long Integer(this DbDataReader row, string column) =>
        row.GetInt64(row.GetOrdinal(column));

    public static long? OptionalInteger(this DbDataReader row, string column) =>
        row.IsDBNull(row.GetOrdinal(column)) ? null : row.Integer(column);

    public static bool Flag(this DbDataReader row, string column) =>
        row.GetBoolean(row.GetOrdinal(column));

    public static bool? OptionalFlag(this DbDataReader row, string column) =>
        row.IsDBNull(row.GetOrdinal(column)) ? null : row.Flag(column);

    public static DateOnly Date(this DbDataReader row, string column) =>
        row.GetFieldValue<DateOnly>(row.GetOrdinal(column));

    public static DateOnly? OptionalDate(this DbDataReader row, string column) =>
        row.IsDBNull(row.GetOrdinal(column)) ? null : row.Date(column);

    /// <summary>A UTC instant from a column selected as <c>epoch_us(...)</c>, so the
    /// machine's time zone never shifts it.</summary>
    public static DateTimeOffset Instant(this DbDataReader row, string column) =>
        DateTimeOffset.UnixEpoch.AddTicks(row.GetInt64(row.GetOrdinal(column)) * 10);

    public static DateTimeOffset? OptionalInstant(this DbDataReader row, string column) =>
        row.IsDBNull(row.GetOrdinal(column)) ? null : row.Instant(column);

    public static IReadOnlyList<string> TextList(this DbDataReader row, string column) =>
        row.GetFieldValue<List<string>>(row.GetOrdinal(column));
}
