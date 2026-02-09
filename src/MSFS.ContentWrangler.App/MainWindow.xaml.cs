using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shell;
using System.Windows.Threading;
using Microsoft.Win32;
using MSFS.ContentWrangler.Core.Models;
using MSFS.ContentWrangler.Core.Services;
using WpfWindowState = System.Windows.WindowState;

namespace MSFS.ContentWrangler.App;

public sealed partial class MainWindow : Window
{
    private readonly AppConfig _config;
    private readonly AppSettingsStore _settings;
    private readonly string _rulesPath;

    private Rules _rules;
    private string? _currentXml;
    private ThumbCache? _thumbCache;
    private ThumbnailLoader? _thumbLoader;

    private readonly ObservableCollection<PackageRowViewModel> _rows = new();
    private readonly ObservableCollection<PackageRowViewModel> _officialRows = new();
    private readonly ObservableCollection<PackageRowViewModel> _official20Rows = new();
    private readonly ObservableCollection<PackageRowViewModel> _communityRows = new();

    private Regex? _officialRegex;
    private Regex? _official20Regex;
    private Regex? _communityRegex;

    private DispatcherTimer? _statusTimer;
    private bool _pruningSelection;

    public MainWindow()
    {
        InitializeComponent();

        TrySetWindowIcon();

        _config = AppConfig.Load();
        _settings = AppSettingsStore.Load();
        _rulesPath = Path.Combine(AppContext.BaseDirectory, "rules.json");
        _rules = RulesStore.Load(_rulesPath);

        ApplyTheme();
        SetupFooter();
        PopulateFilterCombos();
        SetupViews();
        ApplyThumbnailVisibility();
        HideSimColumns();

        RestoreWindowState();
        StateChanged += OnWindowStateChanged;
        UpdateWindowLayoutForState();
        UpdateMaximizeGlyph();

        var versionLabel = BuildVersionLabel();
        TitleText.Text = $"MSFS2024 Content Wrangler {versionLabel}";

        _currentXml = ResolveInitialContentXml();
        RefreshPathLabel();

        if (!string.IsNullOrWhiteSpace(_currentXml))
        {
            _ = LoadContentFileAsync(initial: true);
        }
        else
        {
            _ = ShowMessageAsync("Content.xml not found",
                "No Content.xml detected under LocalCache.\nOpen one manually from File -> Open...");
        }

        Closed += OnWindowClosed;
    }

    private static string BuildVersionLabel()
    {
        try
        {
            var assembly = typeof(MainWindow).Assembly;
            var info = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>();
            if (!string.IsNullOrWhiteSpace(info?.InformationalVersion))
            {
                return info.InformationalVersion;
            }

            var version = assembly.GetName().Version;
            if (version is not null)
            {
                return $"v{version}";
            }
        }
        catch
        {
        }

        return "(dev)";
    }

    private void TrySetWindowIcon()
    {
        try
        {
            var iconPath = Path.Combine(AppContext.BaseDirectory, "icons", "app.ico");
            if (File.Exists(iconPath))
            {
                Icon = BitmapFrame.Create(new Uri(iconPath, UriKind.Absolute));
            }
        }
        catch
        {
            // ignore icon failures; do not crash app startup
        }
    }

    private void SetupViews()
    {
        OfficialGrid.ItemsSource = _officialRows;
        Official20Grid.ItemsSource = _official20Rows;
        CommunityGrid.ItemsSource = _communityRows;
    }

    private void PopulateFilterCombos()
    {
        var categories = new List<string> { "All" };
        foreach (var cat in _rules.Categories)
        {
            if (!string.IsNullOrWhiteSpace(cat.Name) && !categories.Contains(cat.Name))
            {
                categories.Add(cat.Name);
            }
        }
        if (!categories.Contains("Other"))
        {
            categories.Add("Other");
        }

        var statuses = new List<string>
        {
            "All",
            PackageStatus.Activated,
            PackageStatus.UserDisabled,
            PackageStatus.SystemDisabled
        };

        OfficialCategoryBox.ItemsSource = categories;
        Official20CategoryBox.ItemsSource = categories;
        CommunityCategoryBox.ItemsSource = categories;

        OfficialStatusBox.ItemsSource = statuses;
        Official20StatusBox.ItemsSource = statuses;
        CommunityStatusBox.ItemsSource = statuses;

        OfficialCategoryBox.SelectedIndex = 0;
        Official20CategoryBox.SelectedIndex = 0;
        CommunityCategoryBox.SelectedIndex = 0;

        OfficialStatusBox.SelectedIndex = 0;
        Official20StatusBox.SelectedIndex = 0;
        CommunityStatusBox.SelectedIndex = 0;
    }

    private void ApplyTheme()
    {
        var isLight = string.Equals(_config.Theme, "light", StringComparison.OrdinalIgnoreCase);
        var resources = Application.Current.Resources;

        if (isLight)
        {
            resources["BackgroundBrush"] = new SolidColorBrush(Color.FromRgb(244, 244, 248));
            resources["SurfaceBrush"] = new SolidColorBrush(Color.FromRgb(236, 236, 242));
            resources["SurfaceAltBrush"] = new SolidColorBrush(Color.FromRgb(230, 230, 238));
            resources["AccentBrush"] = new SolidColorBrush(Color.FromRgb(0, 180, 135));
            resources["DangerBrush"] = new SolidColorBrush(Color.FromRgb(220, 68, 68));
            resources["WarningBrush"] = new SolidColorBrush(Color.FromRgb(245, 158, 11));
            resources["TextPrimaryBrush"] = new SolidColorBrush(Colors.Black);
            resources["TextSecondaryBrush"] = new SolidColorBrush(Color.FromRgb(90, 90, 110));
            resources["BorderBrush"] = new SolidColorBrush(Color.FromRgb(200, 200, 215));
            resources["DividerBrush"] = new SolidColorBrush(Color.FromRgb(210, 210, 220));
            resources["HoverBrush"] = new SolidColorBrush(Color.FromRgb(225, 225, 235));
            resources["PressedBrush"] = new SolidColorBrush(Color.FromRgb(210, 210, 225));
            resources["RowHoverBrush"] = new SolidColorBrush(Color.FromRgb(230, 230, 240));
            resources["RowSelectedBrush"] = new SolidColorBrush(Color.FromRgb(215, 215, 235));
        }
        else
        {
            resources["BackgroundBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#1E1E2E"));
            resources["SurfaceBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#2A2A3A"));
            resources["SurfaceAltBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#242433"));
            resources["AccentBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D9A3"));
            resources["DangerBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#EF4444"));
            resources["WarningBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#F59E0B"));
            resources["TextPrimaryBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E4E4E7"));
            resources["TextSecondaryBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#A1A1AA"));
            resources["BorderBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#3A3A4A"));
            resources["DividerBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#2F2F3D"));
            resources["HoverBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#33334A"));
            resources["PressedBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#26263A"));
            resources["RowHoverBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#2F3246"));
            resources["RowSelectedBrush"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#3A3E5A"));
        }

        Background = (Brush)resources["BackgroundBrush"];
        Foreground = (Brush)resources["TextPrimaryBrush"];
    }

    private void SetupFooter()
    {
        FooterBrand.Text = "CraigyBabyJ #flywithcraig";
        var links = new List<LinkItem>();

        // Prefer a stable, intentional ordering (Dictionary order is not guaranteed).
        var preferredOrder = new[]
        {
            "Discord",
            "GitHub",
            "TikTok",
            "Website",
            "Donate",
        };

        foreach (var key in preferredOrder)
        {
            if (_config.Links.TryGetValue(key, out var url) && Uri.TryCreate(url, UriKind.Absolute, out var uri))
            {
                links.Add(new LinkItem(key, uri, IconForLabel(key)));
            }
        }

        foreach (var kv in _config.Links)
        {
            if (Uri.TryCreate(kv.Value, UriKind.Absolute, out var uri))
            {
                if (links.Any(l => string.Equals(l.Label, kv.Key, StringComparison.OrdinalIgnoreCase)))
                {
                    continue;
                }

                links.Add(new LinkItem(kv.Key, uri, IconForLabel(kv.Key)));
            }
        }
        FooterLinks.ItemsSource = links;
    }

    private static string IconForLabel(string label)
    {
        var l = (label ?? string.Empty).Trim().ToLowerInvariant();
        if (l.Contains("discord")) return "discord.svg";
        if (l.Contains("github")) return "github.svg";
        if (l.Contains("tiktok")) return "tiktok.svg";
        if (l.Contains("donate") || l.Contains("paypal")) return "donate.svg";
        if (l.Contains("website") || l.Contains("web") || l.Contains("itch")) return "website.svg";
        return "globe.svg";
    }

    private void ApplyThumbnailVisibility()
    {
        var show = _config.ShowThumbnails;
        var vis = show ? Visibility.Visible : Visibility.Collapsed;

        OfficialThumbColumn.Visibility = vis;
        CommunityThumbColumn.Visibility = vis;

        OfficialGrid.RowHeight = show ? 72 : 32;
        CommunityGrid.RowHeight = show ? 72 : 32;
    }

    private void OnMinimizeClicked(object sender, RoutedEventArgs e)
    {
        WindowState = WpfWindowState.Minimized;
    }

    private void OnMaximizeRestoreClicked(object sender, RoutedEventArgs e)
    {
        WindowState = WindowState == WpfWindowState.Maximized
            ? WpfWindowState.Normal
            : WpfWindowState.Maximized;
        UpdateMaximizeGlyph();
    }

    private void OnCloseClicked(object sender, RoutedEventArgs e)
    {
        Close();
    }

    private void OnWindowStateChanged(object? sender, EventArgs e)
    {
        UpdateWindowLayoutForState();
        UpdateMaximizeGlyph();
    }

    private void UpdateMaximizeGlyph()
    {
        if (MaximizeGlyph == null)
        {
            return;
        }

        MaximizeGlyph.Text = WindowState == WpfWindowState.Maximized ? "\uE923" : "\uE922";
    }

    private void UpdateWindowLayoutForState()
    {
        var isMaximized = WindowState == WpfWindowState.Maximized;
        if (WindowBorder != null)
        {
            WindowBorder.Margin = isMaximized ? new Thickness(0) : new Thickness(10);
            WindowBorder.CornerRadius = isMaximized ? new CornerRadius(0) : new CornerRadius(10);
        }

        var chrome = WindowChrome.GetWindowChrome(this);
        if (chrome != null)
        {
            chrome.CornerRadius = isMaximized ? new CornerRadius(0) : new CornerRadius(10);
        }
    }

    private void HideSimColumns()
    {
        HideSimColumn(OfficialGrid);
        HideSimColumn(CommunityGrid);
    }

    private static void HideSimColumn(DataGrid grid)
    {
        foreach (var col in grid.Columns)
        {
            if (col.Header?.ToString() == "Sim")
            {
                col.Visibility = Visibility.Collapsed;
                break;
            }
        }
    }

    private string? ResolveInitialContentXml()
    {
        if (!string.IsNullOrWhiteSpace(_settings.LastContentXml) && File.Exists(_settings.LastContentXml))
        {
            return _settings.LastContentXml;
        }

        if (!string.IsNullOrWhiteSpace(_config.ContentXmlPath) && File.Exists(_config.ContentXmlPath))
        {
            return _config.ContentXmlPath;
        }

        return ContentXmlService.BestContentXml();
    }

    private void RefreshPathLabel()
    {
        if (!string.IsNullOrWhiteSpace(_currentXml))
        {
            Title = $"{TitleText.Text} — {_currentXml}";
            PathText.Text = _currentXml;
        }
    }

    private async Task LoadContentFileAsync(bool initial)
    {
        if (string.IsNullOrWhiteSpace(_currentXml) || !File.Exists(_currentXml))
        {
            await ShowMessageAsync("Error", $"Content.xml not found at:\n{_currentXml}\nPlease select a valid file.");
            return;
        }

        var xmlPath = _currentXml!;
        _rules = RulesStore.Load(_rulesPath);
        var rows = ContentXmlService.LoadPackages(xmlPath, _rules);

        _thumbCache = new ThumbCache(xmlPath);
        _thumbLoader = new ThumbnailLoader(_thumbCache, Dispatcher);

        _rows.Clear();
        foreach (var row in rows)
        {
            _rows.Add(new PackageRowViewModel(row));
        }

        ApplyFilters();

        SetStatus($"Loaded {_rows.Count} packages.", 5000);

        if (_config.ShowThumbnails)
        {
            WarmInitialThumbnails();
        }
    }

    private void WarmInitialThumbnails()
    {
        if (_thumbLoader == null) return;
        var warm = _rows.Take(30).ToList();
        foreach (var row in warm)
        {
            _ = _thumbLoader.QueueAsync(row);
        }
    }

    private void ApplyFilters()
    {
        _officialRows.Clear();
        _official20Rows.Clear();
        _communityRows.Clear();

        var officialCategory = OfficialCategoryBox.SelectedItem as string;
        var officialStatus = OfficialStatusBox.SelectedItem as string;
        var official20Category = Official20CategoryBox.SelectedItem as string;
        var official20Status = Official20StatusBox.SelectedItem as string;
        var communityCategory = CommunityCategoryBox.SelectedItem as string;
        var communityStatus = CommunityStatusBox.SelectedItem as string;

        foreach (var row in _rows)
        {
            if (IsRowForTab(row, source: "official", sim: "fs24") &&
                ApplyCategoryAndStatusFilter(row, officialCategory, officialStatus) &&
                ApplySearchFilter(row, _officialRegex))
            {
                _officialRows.Add(row);
            }

            if (IsRowForTab(row, source: "official", sim: "fs20") &&
                ApplyCategoryAndStatusFilter(row, official20Category, official20Status) &&
                ApplySearchFilter(row, _official20Regex))
            {
                _official20Rows.Add(row);
            }

            if (IsRowForTab(row, source: "community", sim: "fs24") &&
                ApplyCategoryAndStatusFilter(row, communityCategory, communityStatus) &&
                ApplySearchFilter(row, _communityRegex))
            {
                _communityRows.Add(row);
            }
        }
    }

    private static bool IsRowForTab(PackageRowViewModel row, string source, string sim)
    {
        if (row.Source == "community" && row.Sim == "fs20") return false;
        if (row.Source != source) return false;
        if (row.Sim != sim) return false;
        return true;
    }

    private static bool ApplyCategoryAndStatusFilter(PackageRowViewModel row, string? category, string? status)
    {
        if (!string.IsNullOrWhiteSpace(category) && category != "All" && !string.Equals(row.Category, category, StringComparison.Ordinal))
        {
            return false;
        }
        if (!string.IsNullOrWhiteSpace(status) && status != "All" && !string.Equals(row.Status, status, StringComparison.Ordinal))
        {
            return false;
        }
        return true;
    }

    private static bool ApplySearchFilter(PackageRowViewModel row, Regex? regex)
    {
        if (regex == null) return true;
        var name = row.Name ?? string.Empty;
        var vendor = row.Vendor ?? string.Empty;
        return regex.IsMatch(name) || regex.IsMatch(vendor);
    }

    private void OnOfficialFilterChanged(object sender, RoutedEventArgs e)
    {
        _officialRegex = BuildRegex(OfficialSearchBox.Text);
        ApplyFilters();
        UpdateCountMessage("Official Store (FS2024)");
    }

    private void OnOfficial20FilterChanged(object sender, RoutedEventArgs e)
    {
        _official20Regex = BuildRegex(Official20SearchBox.Text);
        ApplyFilters();
        UpdateCountMessage("Official Store (FS2020)");
    }

    private void OnCommunityFilterChanged(object sender, RoutedEventArgs e)
    {
        _communityRegex = BuildRegex(CommunitySearchBox.Text);
        ApplyFilters();
        UpdateCountMessage("Community Folder (FS2024)");
    }

    private static Regex? BuildRegex(string? text)
    {
        if (string.IsNullOrWhiteSpace(text)) return null;
        try
        {
            return new Regex(text, RegexOptions.IgnoreCase);
        }
        catch
        {
            return new Regex(Regex.Escape(text), RegexOptions.IgnoreCase);
        }
    }

    private void UpdateCountMessage(string title)
    {
        int count;
        if (title.StartsWith("Community", StringComparison.OrdinalIgnoreCase))
        {
            count = _communityRows.Count;
        }
        else if (title.Contains("FS2020", StringComparison.OrdinalIgnoreCase))
        {
            count = _official20Rows.Count;
        }
        else
        {
            count = _officialRows.Count;
        }
        SetStatus($"{title}: showing {count} of {_rows.Count} total", 3000);
    }

    private void OnActivateSelected(object sender, RoutedEventArgs e)
    {
        BulkSetStatus(PackageStatus.Activated);
    }

    private void OnDisableSelected(object sender, RoutedEventArgs e)
    {
        BulkSetStatus(PackageStatus.UserDisabled);
    }

    private void BulkSetStatus(string status)
    {
        var grid = GetActiveGrid();
        var selected = grid.SelectedItems.Cast<PackageRowViewModel>().ToList();
        if (selected.Count == 0)
        {
            _ = ShowMessageAsync("No Selection", "Select one or more rows first.");
            return;
        }

        var changed = 0;
        foreach (var row in selected)
        {
            if (row.IsSystemDisabled) continue;
            row.Status = status;
            changed++;
        }

        if (changed > 0)
        {
            var tabTitle = GetActiveTabTitle();
            SetStatus($"{tabTitle}: updated {changed} entrie(s).", 4000);
            ApplyFilters();
        }
    }

    private DataGrid GetActiveGrid()
    {
        if (ReferenceEquals(MainTabs.SelectedItem, CommunityTab)) return CommunityGrid;
        if (ReferenceEquals(MainTabs.SelectedItem, Official20Tab)) return Official20Grid;
        return OfficialGrid;
    }

    private string GetActiveTabTitle()
    {
        if (ReferenceEquals(MainTabs.SelectedItem, CommunityTab)) return "Community Folder (FS2024)";
        if (ReferenceEquals(MainTabs.SelectedItem, Official20Tab)) return "Official Store (FS2020)";
        return "Official Store (FS2024)";
    }

    private async void OnSaveChanges(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(_currentXml)) return;

        var diffs = _rows.Where(r => r.Model.Status != r.Model.OriginalStatus).ToList();
        if (diffs.Count == 0)
        {
            await ShowMessageAsync("Nothing to save", "No changes detected.");
            return;
        }

        var preview = string.Join("\n", diffs.Take(30).Select(d => $"{d.Name}: -> {d.Status}"));
        var more = diffs.Count <= 30 ? string.Empty : $"\n... and {diffs.Count - 30} more.";
        var msg = $"This will create a backup and update Content.xml.\n\nPreview of changes:\n{preview}{more}\n\nContinue?";

        var ok = await ShowConfirmAsync("Apply changes?", msg);
        if (!ok) return;

        var backupPath = ContentXmlService.BackupContent(_currentXml);
        var removedCount = ContentXmlService.SavePackages(_currentXml, _rows.Select(r => r.Model), _config.CleanLegacyFs20);

        foreach (var row in _rows)
        {
            row.Model.OriginalStatus = row.Model.Status;
        }

        await ShowMessageAsync("Saved", $"Changes saved successfully.\nBackup created at: {backupPath}");

        if (removedCount > 0)
        {
            await ShowMessageAsync("Cleaned legacy FS20 mods",
                $"Removed {removedCount} legacy FS2020 community entries from Content.xml.\nYou can disable this in Settings -> Appearance.");
        }
    }

    private async void OnSettings(object sender, RoutedEventArgs e)
    {
        var dialog = new SettingsDialog(_rules, _config, _currentXml ?? string.Empty, this);
        dialog.RequestClearThumbCache += (_, _) => ClearThumbCache();

        var result = dialog.ShowDialog();
        if (result != true)
        {
            return;
        }

        var newRules = dialog.GetUpdatedRules();
        var newConfig = dialog.GetUpdatedConfig();

        var rulesChanged = !JsonEquals(_rules, newRules);
        var configChanged = !JsonEquals(_config, newConfig);

        if (rulesChanged)
        {
            _rules = newRules;
            RulesStore.Save(_rulesPath, _rules);
        }

        if (configChanged)
        {
            _config.ContentXmlPath = newConfig.ContentXmlPath;
            _config.Theme = newConfig.Theme;
            _config.ShowThumbnails = newConfig.ShowThumbnails;
            _config.CleanLegacyFs20 = newConfig.CleanLegacyFs20;
            _config.Links = newConfig.Links;
            _config.Save();
            ApplyTheme();
            ApplyThumbnailVisibility();
            SetupFooter();
        }

        if (rulesChanged || configChanged)
        {
            SetStatus("Settings updated. Reloading...", 3000);
            await LoadContentFileAsync(initial: true);
        }
    }

    private async void OnSwitchContentXml(object sender, RoutedEventArgs e)
    {
        var candidates = ContentXmlService.ListContentXmlCandidates().ToList();
        if (candidates.Count == 0)
        {
            await ShowMessageAsync("No files", "No Content.xml files found.");
            return;
        }

        var labels = candidates.Select(c => $"{c.Name} — {c.Path}").ToList();
        var dialog = new ContentXmlPickerDialog(labels)
        {
            Owner = this
        };

        var result = dialog.ShowDialog();
        if (result != true || dialog.SelectedIndex < 0)
        {
            return;
        }

        var idx = dialog.SelectedIndex;
        _currentXml = candidates[idx].Path;
        _settings.LastContentXml = _currentXml;
        _settings.Save();

        RefreshPathLabel();
        await LoadContentFileAsync(initial: false);

        if (candidates.Any(c => c.IsProfile) && !candidates[idx].IsProfile)
        {
            SetStatus("Heads up: a profile-scoped Content.xml also exists; the sim usually prefers that one.", 8000);
        }
    }

    private async void OnOpenContentXml(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "Open Content.xml",
            Filter = "Content.xml (*.xml)|*.xml|All files (*.*)|*.*"
        };

        if (dialog.ShowDialog(this) != true) return;

        _currentXml = dialog.FileName;
        _settings.LastContentXml = _currentXml;
        _settings.Save();

        RefreshPathLabel();
        await LoadContentFileAsync(initial: false);
    }

    private async void OnReload(object sender, RoutedEventArgs e)
    {
        await LoadContentFileAsync(initial: false);
    }

    private async void OnPreferCommunityAirports(object sender, RoutedEventArgs e)
    {
        if (_rows.Count == 0) return;

        var communityCodes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var row in _rows)
        {
            if (row.Category != "Airport") continue;
            if (row.Source != "community") continue;
            if (row.Sim != "fs24") continue;
            var code = AirportCodeParser.ParseAirportCodeFromName(row.Name);
            if (!string.IsNullOrWhiteSpace(code))
            {
                communityCodes.Add(code);
            }
        }

        if (communityCodes.Count == 0)
        {
            await ShowMessageAsync("Prefer Community Airports", "No Community (FS2024) airports detected.");
            return;
        }

        var toDisable = new List<(PackageRowViewModel Row, string Code)>();
        foreach (var row in _rows)
        {
            if (row.Category != "Airport") continue;
            if (row.Source != "official") continue;
            if (row.Sim is not ("fs24" or "fs20")) continue;
            if (row.Status is PackageStatus.SystemDisabled or PackageStatus.UserDisabled) continue;

            var code = AirportCodeParser.ParseAirportCodeFromName(row.Name);
            if (!string.IsNullOrWhiteSpace(code) && communityCodes.Contains(code) && row.Status == PackageStatus.Activated)
            {
                toDisable.Add((row, code));
            }
        }

        if (toDisable.Count == 0)
        {
            SetStatus("Prefer Community: nothing to do.", 4000);
            await ShowMessageAsync("Prefer Community Airports",
                "No new store duplicates to disable.\nEither none were found, or they are already disabled.");
            return;
        }

        var sample = string.Join("\n", toDisable.Take(12).Select(t => $"  - {t.Code} — {t.Row.Name}"));
        var more = toDisable.Count <= 12 ? string.Empty : $"\n  ... and {toDisable.Count - 12} more.";
        var msg =
            $"This will disable {toDisable.Count} Official Store airport(s) that also exists in your Community Folder.\n\n" +
            $"To be disabled:\n{sample}{more}\n\n" +
            "Community versions remain active.\n\nProceed?";

        var ok = await ShowConfirmAsync("Prefer Community Airports", msg);
        if (!ok)
        {
            SetStatus("Prefer Community: cancelled.", 3000);
            return;
        }

        foreach (var (row, _) in toDisable)
        {
            row.Status = PackageStatus.UserDisabled;
        }

        ApplyFilters();
        SetStatus($"Prefer Community: disabled {toDisable.Count} store duplicate(s). Remember to click Save to write Content.xml.", 7000);
    }

    private async void OnRefreshThumbnailsClicked(object sender, RoutedEventArgs e)
    {
        if (!_config.ShowThumbnails || _thumbLoader == null) return;

        var grid = GetActiveGrid();
        var selected = grid.SelectedItems.Cast<PackageRowViewModel>().ToList();
        if (selected.Count == 0)
        {
            SetStatus("No rows selected.", 2000);
            return;
        }

        foreach (var row in selected)
        {
            await _thumbLoader.RefreshAsync(row);
        }
        SetStatus($"Refreshing {selected.Count} thumbnail(s)...", 2500);
    }

    private void OnGridLoadingRow(object sender, DataGridRowEventArgs e)
    {
        if (e.Row.DataContext is not PackageRowViewModel row) return;

        if (row.IsSystemDisabled)
        {
            e.Row.Background = new SolidColorBrush(Color.FromArgb(60, 255, 99, 99));
            e.Row.Foreground = new SolidColorBrush(Color.FromArgb(255, 255, 220, 220));
        }
        else
        {
            e.Row.ClearValue(DataGridRow.BackgroundProperty);
            e.Row.ClearValue(DataGridRow.ForegroundProperty);
        }
    }

    private void OnGridSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_pruningSelection) return;
        _pruningSelection = true;
        try
        {
            var grid = (DataGrid)sender;
            var toRemove = grid.SelectedItems.Cast<PackageRowViewModel>().Where(r => r.IsSystemDisabled).ToList();
            foreach (var item in toRemove)
            {
                grid.SelectedItems.Remove(item);
            }
        }
        finally
        {
            _pruningSelection = false;
        }
    }

    private void OnStatusToggleClicked(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.DataContext is PackageRowViewModel row)
        {
            if (row.IsSystemDisabled) return;
            row.Status = row.Status == PackageStatus.Activated ? PackageStatus.UserDisabled : PackageStatus.Activated;
            var tabTitle = GetActiveTabTitle();
            ApplyFilters();
            UpdateCountMessage(tabTitle);
        }
    }

    private void OnTabSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateCountMessage(GetActiveTabTitle());
    }

    private void ClearThumbCache()
    {
        try
        {
            _thumbCache?.ClearAll();
        }
        catch
        {
            // ignore
        }

        foreach (var row in _rows)
        {
            row.ThumbnailImage = null;
            row.ThumbnailState = ThumbnailState.Unknown;
            row.ThumbnailToolTip = string.Empty;
        }

        SetStatus("Thumbnail cache cleared.", 3000);
    }

    private void SetStatus(string message, int durationMs)
    {
        StatusText.Text = message;
        if (_statusTimer == null)
        {
            _statusTimer = new DispatcherTimer();
            _statusTimer.Tick += (_, _) =>
            {
                StatusText.Text = string.Empty;
                _statusTimer?.Stop();
            };
        }
        _statusTimer.Stop();
        _statusTimer.Interval = TimeSpan.FromMilliseconds(durationMs);
        _statusTimer.Start();
    }

    private Task ShowMessageAsync(string title, string message)
    {
        var dialog = new PromptDialog(title, message, showInputBox: false, showCancelButton: false)
        {
            Owner = this
        };
        dialog.ShowDialog();
        return Task.CompletedTask;
    }

    private Task<bool> ShowConfirmAsync(string title, string message)
    {
        var dialog = new PromptDialog(title, message, showInputBox: false, showCancelButton: true)
        {
            Owner = this
        };
        var result = dialog.ShowDialog();
        return Task.FromResult(result == true);
    }

    private static bool JsonEquals<T>(T a, T b)
    {
        var jsonA = JsonSerializer.Serialize(a);
        var jsonB = JsonSerializer.Serialize(b);
        return string.Equals(jsonA, jsonB, StringComparison.Ordinal);
    }

    private void RestoreWindowState()
    {
        var state = _settings.Window;
        if (state == null)
        {
            Width = 1280;
            Height = 840;
            return;
        }

        Left = state.X;
        Top = state.Y;
        Width = state.Width;
        Height = state.Height;
        if (state.Maximized)
        {
            WindowState = WpfWindowState.Maximized;
        }
    }

    private void OnWindowClosed(object? sender, EventArgs args)
    {
        var state = new WindowState
        {
            X = (int)Left,
            Y = (int)Top,
            Width = (int)Width,
            Height = (int)Height,
            Maximized = WindowState == WpfWindowState.Maximized
        };

        _settings.Window = state;
        _settings.Save();
    }

    private void OnFooterLinkNavigate(object sender, RequestNavigateEventArgs e)
    {
        try
        {
            Process.Start(new ProcessStartInfo(e.Uri.AbsoluteUri) { UseShellExecute = true });
        }
        catch
        {
            // ignore
        }
        e.Handled = true;
    }

    private void OnFooterLinkClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            if (sender is Button btn && btn.Tag is Uri uri)
            {
                Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true });
            }
        }
        catch
        {
            // ignore
        }
    }
}
