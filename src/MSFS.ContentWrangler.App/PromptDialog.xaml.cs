using System.Windows;

namespace MSFS.ContentWrangler.App;

public sealed partial class PromptDialog : Window
{
    public PromptDialog(string title, string message)
        : this(title, message, showInputBox: true, showCancelButton: true)
    {
    }

    public PromptDialog(string title, string message, bool showInputBox, bool showCancelButton)
    {
        InitializeComponent();
        Title = title;
        TitleText.Text = title;
        MessageText.Text = message;
        InputBox.Visibility = showInputBox ? Visibility.Visible : Visibility.Collapsed;
        CancelButton.Visibility = showCancelButton ? Visibility.Visible : Visibility.Collapsed;

        if (showInputBox)
        {
            InputBox.Focus();
        }
        else
        {
            OkButton.Focus();
        }
    }

    public string ResponseText => InputBox.Text?.Trim() ?? string.Empty;

    private void OnOkClick(object sender, RoutedEventArgs e)
    {
        DialogResult = true;
        Close();
    }

    private void OnCancelClick(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
        Close();
    }
}
