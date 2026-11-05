$ErrorActionPreference = 'Stop'
$runtimeRoot = 'C:\Users\emanu\apps'
$taskName = 'WeFixPricesAgent'
$secret = Join-Path $runtimeRoot 'secrets\wefix-prices.env'
$agentDir = Join-Path $runtimeRoot 'data\wefix-prices'
$controllerState = Join-Path $runtimeRoot '.railwaylocale\state.json'
$state = Get-Content -LiteralPath $controllerState -Raw | ConvertFrom-Json
$sha = [string]$state.'wefix-prices'.deployed
if ($sha -notmatch '^[a-f0-9]{40}$' -or $sha -ne (git -C $PSScriptRoot rev-parse HEAD)) { throw 'Eseguire solo dal commit WeFix attualmente distribuito' }
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Attivita agente gia presente: verificare prima di sostituirla' }
New-Item -ItemType Directory -Force -Path $agentDir | Out-Null
if (-not (Test-Path -LiteralPath $secret)) {
    function New-WeFixToken {
        $bytes=New-Object byte[] 32
        $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create(); try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        return [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
    }
    $webToken=New-WeFixToken; $ingestToken=New-WeFixToken; $agentToken=New-WeFixToken
    $text="WEFIX_API_TOKEN=$webToken`nWEFIX_DB_API_TOKEN=$ingestToken`nWEFIX_AGENT_TOKEN=$agentToken`nWEFIX_DB_API_URL=http://127.0.0.1:8766`nWEFIX_SALES_REPO=C:/Users/emanu/Documents/GitHub/calcola_acquista_usato/calcola_acquista_usato`nWEFIX_TRADE_REPO=C:/Users/emanu/Documents/GitHub/valuta_usato_platform`nWEFIX_GOOGLE_CREDENTIALS=C:/Users/emanu/Documents/GitHub/valuta_usato_platform/constants/valutausato-f3fbfb65ccc3.json`n"
    [IO.File]::WriteAllText($secret,$text,[Text.UTF8Encoding]::new($false))
}
$venv=Join-Path $agentDir 'agent-venv'
if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts\python.exe'))) {
    & python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Creazione ambiente agente fallita' }
}
& (Join-Path $venv 'Scripts\python.exe') -m pip install -r (Join-Path $PSScriptRoot 'requirements-container.txt')
if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze agente fallita' }
$bootstrap=Join-Path $agentDir 'agent_bootstrap.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'agent_bootstrap.ps1') -Destination $bootstrap
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $bootstrap + '"')
$principal=New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
$trigger=New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Trigger $trigger -Settings $settings | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output 'Agente configurato e avviato.'
