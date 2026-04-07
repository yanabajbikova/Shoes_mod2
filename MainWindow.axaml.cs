using Avalonia.Controls;
using Avalonia.Interactivity;
using Npgsql;
using System;

namespace ShoesApp;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
    }

   
    public void OnLoginClick(object sender, RoutedEventArgs e)
    {
   
        var loginBox = this.Find<TextBox>("LoginBox");
        var passwordBox = this.Find<TextBox>("PasswordBox");

        if (loginBox == null || passwordBox == null) return;

        string login = loginBox.Text ?? "";
        string password = passwordBox.Text ?? "";

        try
        {
            using (var conn = Database.GetConnection())
            {
                conn.Open();
                // Проверяем логин и пароль в таблице "User"
                string sql = "SELECT id_role, fio FROM \"User\" WHERE login = @l AND password = @p";
                using (var cmd = new NpgsqlCommand(sql, conn))
                {
                    cmd.Parameters.AddWithValue("l", login);
                    cmd.Parameters.AddWithValue("p", password);

                    using (var reader = cmd.ExecuteReader())
                    {
                        if (reader.Read())
                        {
                            int roleId = reader.GetInt32(0);
                            string userFio = reader.IsDBNull(1) ? "Пользователь" : reader.GetString(1);
                            
                            // Открываем окно товаров
                            var productWindow = new ProductWindow(userFio, roleId);
                            productWindow.Show();
                            this.Close();
                        }
                        else
                        {
                            Console.WriteLine("Неверный логин или пароль");
                        }
                    }
                }
            }
        }
        catch (Exception ex) 
        { 
            Console.WriteLine("Ошибка БД: " + ex.Message); 
        }
    }

   
    public void OnGuestClick(object sender, RoutedEventArgs e)
    {
        try 
        {
            // Открываем окно товаров с ролью 0 (гость)
            var productWindow = new ProductWindow("Гость", 0);
            productWindow.Show();
            this.Close();
        }
        catch (Exception ex)
        {
            Console.WriteLine("Ошибка при входе гостем: " + ex.Message);
        }
    }
}