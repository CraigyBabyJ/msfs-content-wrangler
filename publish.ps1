$ErrorActionPreference = "Stop"

Write-Host "Publishing single-file executable..."
dotnet publish src\MSFS.ContentWrangler.App\MSFS.ContentWrangler.App.csproj -c Release -o dist /p:DebugType=embedded

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Success! ✈️"
    Write-Host "Your single-file executable is ready at:"
    Write-Host "  $(Resolve-Path dist\MSFS.ContentWrangler.App.exe)"
} else {
    Write-Host "Build failed."
    exit 1
}
