using System.Collections.Generic;
using System.Windows;

namespace MSFS.ContentWrangler.App;

public sealed partial class ContentXmlPickerDialog : Window
{
    public ContentXmlPickerDialog(IReadOnlyList<string> items)
    {
        InitializeComponent();
        PickerBox.ItemsSource = items;
        if (items.Count > 0)
        {
            PickerBox.SelectedIndex = 0;
        }
    }

    public int SelectedIndex => PickerBox.SelectedIndex;

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
