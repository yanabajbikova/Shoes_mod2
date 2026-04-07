using Avalonia.Controls;
using Avalonia.Interactivity;
using Npgsql;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace ShoesApp;

public class Product
{
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public string Manufacturer { get; set; } = ""; 
    public decimal Cost { get; set; }
    public int Discount { get; set; }
    public int Count { get; set; } 
    public string Photo { get; set; } = "";
    public bool IsAdmin { get; set; }
    public bool HasDiscount => Discount > 0;
    public string RowBackground => Discount > 15 ? "#2E8B57" : "#FFFFFF";
    public string StatusColor => Count == 0 ? "#00FFFF" : (Discount > 15 ? "#FFFFFF" : "#000000");
    public string MainTextColor => Discount > 15 ? "#FFFFFF" : "#000000";
    public string StockStatus => Count > 0 ? $"В наличии: {Count} шт." : "Нет на складе";
}

public class Order
{
    public int OrderID { get; set; }
    public DateTime OrderDate { get; set; }
    public string Status { get; set; } = "";
    public decimal TotalCost { get; set; } // В твоей таблице нет суммы, пока выведем заглушку или receipt_code
    public bool IsAdmin { get; set; }
}

public partial class ProductWindow : Window
{
    private List<Product> _allProducts = new List<Product>();
    private List<Order> _allOrders = new List<Order>();
    private int _currentRoleId;

    public ProductWindow() : this("Гость", 0) { }

    public ProductWindow(string fullName, int roleId)
    {
        InitializeComponent();
        _currentRoleId = roleId;
        
        var label = this.FindControl<TextBlock>("UserFullNameLabel");
        if (label != null) label.Text = fullName;

        var searchPanel = this.FindControl<StackPanel>("SearchPanel");
        if (searchPanel != null) searchPanel.IsVisible = !(roleId == 0 || roleId == 3);

        var addButton = this.FindControl<Button>("AddProductButton");
        if (addButton != null) addButton.IsVisible = (roleId == 1);

        var ordersTab = this.FindControl<TabItem>("OrdersTab");
        if (ordersTab != null) ordersTab.IsVisible = (roleId == 1 || roleId == 2);

        LoadProducts();
        if (roleId == 1 || roleId == 2) LoadOrders();
    }

    public void OnLogoutClick(object sender, RoutedEventArgs e)
    {
        new MainWindow().Show();
        this.Close();
    }



    public async void OnAddProductClick(object sender, RoutedEventArgs e) 
    {
        var win = new AddEditProductWindow();
        await win.ShowDialog(this);
        LoadProducts(); 
    }

    public async void OnEditClick(object sender, RoutedEventArgs e) 
    {
        var product = (sender as Button)?.DataContext as Product;
        if (product == null) return;
        var win = new AddEditProductWindow(); 
        await win.ShowDialog(this);
        LoadProducts();
    }

    public async void OnDeleteClick(object sender, RoutedEventArgs e) 
    {
        var product = (sender as Button)?.DataContext as Product;
        if (product == null) return;
        try {
            using (var conn = Database.GetConnection()) {
                await conn.OpenAsync();
                using (var cmd = new NpgsqlCommand("DELETE FROM product WHERE name = @n", conn)) {
                    cmd.Parameters.AddWithValue("n", product.Name);
                    await cmd.ExecuteNonQueryAsync();
                }
            }
            LoadProducts();
        } catch (Exception ex) { ShowError(ex.Message); }
    }



    public async void OnDeleteOrderClick(object sender, RoutedEventArgs e) 
    {
        var order = (sender as Button)?.DataContext as Order;
        if (order == null) return;

        try {
            using (var conn = Database.GetConnection()) {
                await conn.OpenAsync();
                // ИСПРАВЛЕНО: id_order вместо order_id
                using (var cmd = new NpgsqlCommand("DELETE FROM \"Order\" WHERE id_order = @id", conn)) {
                    cmd.Parameters.AddWithValue("id", order.OrderID);
                    await cmd.ExecuteNonQueryAsync();
                }
            }
            LoadOrders();
        } catch (Exception ex) { ShowError(ex.Message); }
    }

    public void OnEditOrderClick(object sender, RoutedEventArgs e) { }

    private void OnSearchChanged(object sender, TextChangedEventArgs e)
    {
        string text = (this.FindControl<TextBox>("SearchBox")?.Text ?? "").ToLower();
        var filtered = _allProducts.Where(p => p.Name.ToLower().Contains(text) || p.Description.ToLower().Contains(text)).ToList();
        var pList = this.FindControl<ListBox>("ProductList");
        if (pList != null) pList.ItemsSource = filtered;
    }

    private void LoadProducts()
    {
        _allProducts.Clear();
        try {
            using (var conn = Database.GetConnection()) {
                conn.Open();
                using (var cmd = new NpgsqlCommand("SELECT name, description, price, discount, stock_quantity, photo FROM product", conn))
                using (var reader = cmd.ExecuteReader()) {
                    while (reader.Read()) {
                        _allProducts.Add(new Product {
                            Name = reader.GetString(0),
                            Description = reader.IsDBNull(1) ? "" : reader.GetString(1),
                            Cost = reader.GetDecimal(2),
                            Discount = reader.IsDBNull(3) ? 0 : reader.GetInt32(3),
                            Count = reader.GetInt32(4),
                            Photo = reader.IsDBNull(5) ? "" : reader.GetString(5),
                            IsAdmin = (_currentRoleId == 1)
                        });
                    }
                }
            }
            var pList = this.FindControl<ListBox>("ProductList");
            if (pList != null) pList.ItemsSource = _allProducts.ToList();
            UpdateStatus($"Товаров: {_allProducts.Count}");
        } catch (Exception ex) { ShowError("Ошибка товаров: " + ex.Message); }
    }

    private void LoadOrders()
    {
        _allOrders.Clear();
        try {
            using (var conn = Database.GetConnection()) {
                conn.Open();
                // ИСПРАВЛЕНО: id_order, order_date, status, receipt_code (вместо суммы)
                string sql = "SELECT id_order, order_date, status, receipt_code FROM \"Order\"";
                using (var cmd = new NpgsqlCommand(sql, conn))
                using (var reader = cmd.ExecuteReader()) {
                    while (reader.Read()) {
                        _allOrders.Add(new Order {
                            OrderID = reader.GetInt32(0),
                            OrderDate = reader.GetDateTime(1),
                            Status = reader.GetString(2),
                            TotalCost = reader.GetInt32(3), // Временно выводим код получения как число
                            IsAdmin = (_currentRoleId == 1)
                        });
                    }
                }
            }
            var oList = this.FindControl<ListBox>("OrderList");
            if (oList != null) oList.ItemsSource = _allOrders.ToList();
            UpdateStatus($"Загружено заказов: {_allOrders.Count}");
        } catch (Exception ex) { 
            ShowError("Ошибка заказов: " + ex.Message); 
        }
    }

    private void ShowError(string msg) {
        var sLabel = this.FindControl<TextBlock>("StatusLabel");
        if (sLabel != null) {
            sLabel.Text = msg;
            sLabel.Foreground = Avalonia.Media.Brushes.Red;
        }
    }

    private void UpdateStatus(string msg) {
        var sLabel = this.FindControl<TextBlock>("StatusLabel");
        if (sLabel != null) {
            sLabel.Text = msg;
            sLabel.Foreground = Avalonia.Media.Brushes.Black;
        }
    }
}