using Avalonia.Controls;
using Avalonia.Interactivity;
using Npgsql;
using System;

namespace ShoesApp;

public partial class AddEditProductWindow : Window
{
    public AddEditProductWindow()
    {
        InitializeComponent();
    }

    private async void OnSaveClick(object sender, RoutedEventArgs e)
    {
        try
        {
            using (var conn = Database.GetConnection())
            {
                await conn.OpenAsync();
                
                string sql = "INSERT INTO product (name, description, price, discount, stock_quantity) " +
                             "VALUES (@n, @d, @p, @disc, @c)";
                
                using (var cmd = new NpgsqlCommand(sql, conn))
                {
                    cmd.Parameters.AddWithValue("n", this.FindControl<TextBox>("NameBox").Text ?? "");
                    cmd.Parameters.AddWithValue("d", this.FindControl<TextBox>("DescBox").Text ?? "");
                    cmd.Parameters.AddWithValue("p", decimal.Parse(this.FindControl<TextBox>("PriceBox").Text ?? "0"));
                    cmd.Parameters.AddWithValue("disc", int.Parse(this.FindControl<TextBox>("DiscountBox").Text ?? "0"));
                    cmd.Parameters.AddWithValue("c", int.Parse(this.FindControl<TextBox>("CountBox").Text ?? "0"));
                    
                    await cmd.ExecuteNonQueryAsync();
                }
            }
            this.Close(); 
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine("Ошибка сохранения: " + ex.Message);
        }
    }

    private void OnCancelClick(object sender, RoutedEventArgs e) => this.Close();
}