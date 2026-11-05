$ErrorActionPreference = 'Stop'
$stateFile = 'C:\Users\emanu\apps\.railwaylocale\state.json'
$root = 'C:\Users\emanu\apps\.railwaylocale\snapshots\wefix-prices'
$env:WEFIX_AGENT_ENV = 'C:\Users\emanu\apps\secrets\wefix-prices.env'
$env:WEFIX_RELEASE_STATE = $stateFile
$python = 'C:\Users\emanu\apps\data\wefix-prices\agent-venv\Scripts\python.exe'
while ($true) {
    try {
        $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        $sha = [string]$state.'wefix-prices'.deployed
        if ($sha -notmatch '^[a-f0-9]{40}$') { throw 'Nessun commit distribuito' }
        $script = Join-Path (Join-Path $root $sha) 'windows_agent.py'
        if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'Agente non presente nel commit distribuito' }
        $env:WEFIX_RELEASE_SHA = $sha
        & $python $script
    } catch { }
    Start-Sleep -Seconds 5
}
