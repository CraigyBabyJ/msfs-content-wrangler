using System.IO;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Threading;

namespace MSFS.ContentWrangler.App;

public partial class App : System.Windows.Application
{
    public static AppConfig Config { get; private set; } = AppConfig.Load();

    public App()
    {
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
        DispatcherUnhandledException += OnDispatcherUnhandledException;
        TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;

        InitializeComponent();

        // Force-load the theme dictionary at startup. WPF can defer merged-dictionary loading,
        // which can surface as missing StaticResource keys during StartupUri window load.
        EnsureThemeResourcesLoaded();
    }

    private void EnsureThemeResourcesLoaded()
    {
        try
        {
            // If this key exists, AppStyles.xaml is already available.
            _ = Resources["TitleBarButtonStyle"];
            return;
        }
        catch
        {
            // continue, we'll try to load it explicitly
        }

        try
        {
            var uri = new Uri("pack://application:,,,/MSFS.ContentWrangler.App;component/Themes/AppStyles.xaml", UriKind.Absolute);
            if (Resources.MergedDictionaries.Any(d => d.Source != null && d.Source.Equals(uri)))
            {
                return;
            }

            Resources.MergedDictionaries.Add(new ResourceDictionary { Source = uri });

            // Validate that key resources exist; otherwise fail fast with a useful report.
            _ = Resources["TitleBarButtonStyle"];
        }
        catch (Exception ex)
        {
            ShowFatal(ex, "ThemeResources");
        }
    }

    private static void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        ShowFatal(e.Exception, "Dispatcher");
        e.Handled = true;
        Current?.Shutdown(-1);
    }

    private static void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        if (e.ExceptionObject is Exception ex)
        {
            ShowFatal(ex, "AppDomain");
        }
        else
        {
            ShowFatal(new Exception("Unhandled non-exception object"), "AppDomain");
        }
    }

    private static void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        ShowFatal(e.Exception, "TaskScheduler");
        e.SetObserved();
        Current?.Shutdown(-1);
    }

    private static void ShowFatal(Exception exception, string source)
    {
        var logPath = TryWriteLog(exception, source);
        var message = new StringBuilder()
            .AppendLine("The app crashed during startup.")
            .AppendLine()
            .AppendLine($"Source: {source}")
            .AppendLine()
            .AppendLine(exception.Message)
            .AppendLine()
            .AppendLine(logPath is null ? "Log: (failed to write log file)" : $"Log: {logPath}")
            .ToString();

        MessageBox.Show(message, "MSFS Content Wrangler", MessageBoxButton.OK, MessageBoxImage.Error);
    }

    private static string? TryWriteLog(Exception exception, string source)
    {
        var content = new StringBuilder()
            .AppendLine("MSFS Content Wrangler crash report")
            .AppendLine($"Time (UTC): {DateTime.UtcNow:yyyy-MM-dd HH:mm:ss}")
            .AppendLine($"Source: {source}")
            .AppendLine()
            .AppendLine(exception.ToString())
            .ToString();

        var basePath = Path.Combine(AppContext.BaseDirectory, "msfs-content-wrangler.log");
        var tempPath = Path.Combine(Path.GetTempPath(), "msfs-content-wrangler.log");

        if (TryWrite(basePath, content))
        {
            return basePath;
        }

        if (TryWrite(tempPath, content))
        {
            return tempPath;
        }

        return null;
    }

    private static bool TryWrite(string path, string content)
    {
        try
        {
            File.WriteAllText(path, content);
            return true;
        }
        catch
        {
            return false;
        }
    }
}
