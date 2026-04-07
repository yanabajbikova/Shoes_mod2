using Npgsql;

namespace ShoesApp;

public static class Database
{
    // Твои настройки: сервер на этом компьютере, база ShoesStore, юзер mae
    private static string _connString = "Host=localhost;Username=mae;Database=ShoesStore;Port=5432";

    public static NpgsqlConnection GetConnection()
    {
        return new NpgsqlConnection(_connString);
    }
}