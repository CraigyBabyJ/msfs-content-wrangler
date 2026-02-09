using System.Collections.ObjectModel;
using System.Linq;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Microsoft.Win32;
using MSFS.ContentWrangler.Core.Models;

namespace MSFS.ContentWrangler.App;

public sealed partial class SettingsDialog : Window
{
    private readonly Rules _rulesCopy;
    private readonly AppConfig _configCopy;

    private readonly ObservableCollection<CategoryRuleViewModel> _categories = new();

    public event EventHandler? RequestClearThumbCache;

    public SettingsDialog(Rules rules, AppConfig config, string currentXmlPath, Window owner)
    {
        InitializeComponent();
        Owner = owner;

        _rulesCopy = DeepCopy(rules);
        _configCopy = DeepCopy(config);

        PopulateCategories();

        ContentPathInput.Text = string.IsNullOrWhiteSpace(_configCopy.ContentXmlPath)
            ? currentXmlPath
            : _configCopy.ContentXmlPath;

        if (string.Equals(_configCopy.Theme, "light", StringComparison.OrdinalIgnoreCase))
        {
            ThemeLight.IsChecked = true;
            // Ensure the dialog title stays readable in light theme even if resources are stale.
            SettingsTitle.Foreground = Brushes.Black;
        }
        else
        {
            ThemeDark.IsChecked = true;
        }

        ShowThumbnailsCheck.IsChecked = _configCopy.ShowThumbnails;
        CleanLegacyCheck.IsChecked = _configCopy.CleanLegacyFs20;
    }

    public Rules GetUpdatedRules()
    {
        var rules = new Rules
        {
            DefaultCategory = _rulesCopy.DefaultCategory,
            Categories = _categories.Select(c => new CategoryRule
            {
                Name = c.Name,
                Patterns = c.Patterns.ToList()
            }).ToList()
        };
        return rules;
    }

    public AppConfig GetUpdatedConfig()
    {
        return _configCopy;
    }

    private void PopulateCategories()
    {
        _categories.Clear();
        foreach (var cat in _rulesCopy.Categories)
        {
            _categories.Add(new CategoryRuleViewModel(cat.Name, new ObservableCollection<string>(cat.Patterns)));
        }
        CategoryList.ItemsSource = _categories;
        if (_categories.Count > 0)
        {
            CategoryList.SelectedIndex = 0;
        }
    }

    private void OnCategorySelected(object sender, SelectionChangedEventArgs e)
    {
        if (CategoryList.SelectedItem is CategoryRuleViewModel vm)
        {
            PatternLabel.Text = $"Patterns for \"{vm.Name}\"";
            PatternList.ItemsSource = vm.Patterns;
        }
        else
        {
            PatternLabel.Text = "Patterns";
            PatternList.ItemsSource = null;
        }
    }

    private void OnAddCategory(object sender, RoutedEventArgs e)
    {
        var name = PromptForText("Add Category", "Enter new category name:");
        if (string.IsNullOrWhiteSpace(name))
        {
            return;
        }
        if (_categories.Any(c => string.Equals(c.Name, name, StringComparison.OrdinalIgnoreCase)))
        {
            ShowInfo("Duplicate", "Category already exists.");
            return;
        }
        var vm = new CategoryRuleViewModel(name, new ObservableCollection<string>());
        _categories.Add(vm);
        CategoryList.SelectedItem = vm;
    }

    private void OnRemoveCategory(object sender, RoutedEventArgs e)
    {
        if (CategoryList.SelectedItem is not CategoryRuleViewModel vm)
        {
            return;
        }
        var ok = Confirm("Remove Category", $"Are you sure you want to remove the \"{vm.Name}\" category?");
        if (!ok)
        {
            return;
        }
        _categories.Remove(vm);
        CategoryList.SelectedIndex = _categories.Count > 0 ? 0 : -1;
    }

    private void OnMoveCategoryUp(object sender, RoutedEventArgs e)
    {
        if (CategoryList.SelectedItem is not CategoryRuleViewModel vm)
        {
            return;
        }
        var idx = _categories.IndexOf(vm);
        if (idx <= 0) return;
        _categories.Move(idx, idx - 1);
        CategoryList.SelectedIndex = idx - 1;
    }

    private void OnMoveCategoryDown(object sender, RoutedEventArgs e)
    {
        if (CategoryList.SelectedItem is not CategoryRuleViewModel vm)
        {
            return;
        }
        var idx = _categories.IndexOf(vm);
        if (idx < 0 || idx >= _categories.Count - 1) return;
        _categories.Move(idx, idx + 1);
        CategoryList.SelectedIndex = idx + 1;
    }

    private void OnAddPattern(object sender, RoutedEventArgs e)
    {
        if (CategoryList.SelectedItem is not CategoryRuleViewModel vm)
        {
            return;
        }
        var pattern = (PatternInput.Text ?? string.Empty).Trim();
        if (string.IsNullOrWhiteSpace(pattern))
        {
            return;
        }
        if (!vm.Patterns.Any(p => string.Equals(p, pattern, StringComparison.OrdinalIgnoreCase)))
        {
            vm.Patterns.Add(pattern);
        }
        PatternInput.Text = string.Empty;
    }

    private void OnRemovePattern(object sender, RoutedEventArgs e)
    {
        if (CategoryList.SelectedItem is not CategoryRuleViewModel vm)
        {
            return;
        }
        if (PatternList.SelectedItem is string pattern)
        {
            vm.Patterns.Remove(pattern);
        }
    }

    private void OnBrowseContentXml(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "Select Content.xml",
            Filter = "Content.xml (*.xml)|*.xml|All files (*.*)|*.*"
        };
        if (dialog.ShowDialog(this) == true)
        {
            ContentPathInput.Text = dialog.FileName;
        }
    }

    private void OnClearThumbCache(object sender, RoutedEventArgs e)
    {
        var ok = Confirm("Clear thumbnail cache",
            "This will delete the saved thumbnail mappings.\nThey will be re-discovered as you scroll.\n\nProceed?");
        if (!ok)
        {
            return;
        }
        RequestClearThumbCache?.Invoke(this, EventArgs.Empty);
        ShowInfo("Cleared", "Thumbnail cache cleared.");
    }

    private void OnOkClick(object sender, RoutedEventArgs e)
    {
        _configCopy.ContentXmlPath = ContentPathInput.Text?.Trim() ?? string.Empty;
        _configCopy.Theme = ThemeLight.IsChecked == true ? "light" : "dark";
        _configCopy.ShowThumbnails = ShowThumbnailsCheck.IsChecked == true;
        _configCopy.CleanLegacyFs20 = CleanLegacyCheck.IsChecked == true;

        DialogResult = true;
        Close();
    }

    private void OnCancelClick(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
        Close();
    }

    private static Rules DeepCopy(Rules rules)
    {
        var json = JsonSerializer.Serialize(rules);
        return JsonSerializer.Deserialize<Rules>(json) ?? new Rules();
    }

    private static AppConfig DeepCopy(AppConfig config)
    {
        var json = JsonSerializer.Serialize(config);
        return JsonSerializer.Deserialize<AppConfig>(json) ?? new AppConfig();
    }

    private string? PromptForText(string title, string message)
    {
        var dialog = new PromptDialog(title, message)
        {
            Owner = this
        };
        return dialog.ShowDialog() == true ? dialog.ResponseText : null;
    }

    private void ShowInfo(string title, string message)
    {
        var dialog = new PromptDialog(title, message, showInputBox: false, showCancelButton: false)
        {
            Owner = this
        };
        dialog.ShowDialog();
    }

    private bool Confirm(string title, string message)
    {
        var dialog = new PromptDialog(title, message, showInputBox: false, showCancelButton: true)
        {
            Owner = this
        };
        return dialog.ShowDialog() == true;
    }
}

public sealed class CategoryRuleViewModel
{
    public CategoryRuleViewModel(string name, ObservableCollection<string> patterns)
    {
        Name = name;
        Patterns = patterns;
    }

    public string Name { get; set; }
    public ObservableCollection<string> Patterns { get; }
}
