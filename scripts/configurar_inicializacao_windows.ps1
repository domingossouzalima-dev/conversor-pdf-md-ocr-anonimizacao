<#
==============================================================================
 configurar_inicializacao_windows.ps1
 Configura o conversor para iniciar automaticamente com o Windows (sem Admin)
==============================================================================
#>

$userProfile = $env:USERPROFILE
$startupFolder = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs\Startup")
$batPath = Join-Path $userProfile "Gemini\12-conversoes-pdf-md\scripts\vigiar_conversor.bat"
$shortcutPath = Join-Path $startupFolder "Vigilancia_Conversor_Gemini.lnk"

Write-Host "=== Configuracao de Inicializacao Automatica no Windows ===" -ForegroundColor Cyan

if (-not (Test-Path $batPath)) {
    Write-Warning "Arquivo vigiar_conversor.bat nao encontrado em: $batPath"
    Write-Host "Certifique-se de que a pasta Gemini esta em $userProfile\Gemini"
    exit 1
}

$wscriptShell = New-Object -ComObject WScript.Shell
$shortcut = $wscriptShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "cmd.exe"
$shortcut.Arguments = "/c `"$batPath`""
$shortcut.WorkingDirectory = Join-Path $userProfile "Gemini\12-conversoes-pdf-md\scripts"
$shortcut.WindowStyle = 7 # 7 = Minimizada (inicia discretamente na barra)
$shortcut.Description = "Conversor Automatico de Documentos Gemini (Watch Mode)"
$shortcut.Save()

Write-Host "-> Atalho de inicializacao criado com sucesso em:" -ForegroundColor Green
Write-Host "   $shortcutPath" -ForegroundColor White
Write-Host ""
Write-Host "O conversor iniciara minimizado sempre que voce fizer login no Windows." -ForegroundColor Green
Write-Host "Nao sao necessarios privilegios de administrador." -ForegroundColor Yellow
