@echo off
setlocal
dotnet publish src\MSFS.ContentWrangler.App\MSFS.ContentWrangler.App.csproj -c Release -r win-x64 --self-contained true /p:PublishSingleFile=true /p:IncludeNativeLibrariesForSelfExtract=true
echo Built to .\src\MSFS.ContentWrangler.App\bin\Release\net8.0-windows\win-x64\publish\MSFS.ContentWrangler.App.exe
endlocal
