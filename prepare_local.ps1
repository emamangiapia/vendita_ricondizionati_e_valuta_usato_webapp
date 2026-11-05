$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$head = (git -C $repo rev-parse HEAD).Trim()
$published = ((git -C $repo ls-remote origin refs/heads/local) -split '\s+')[0]
if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[a-f0-9]{40}$' -or $head -ne $published) { throw 'Preparazione consentita solo per il commit local pubblicato' }
git -C $repo diff --quiet HEAD -- migration_export.py
if ($LASTEXITCODE -ne 0) { throw 'Lo strumento di migrazione differisce dal commit pubblicato' }
$runtime = 'C:\Users\emanu\apps'
$secret = Join-Path $runtime 'secrets\wefix-prices.env'
$incoming = Join-Path $runtime 'data\wefix-prices\incoming'
$source = Join-Path $repo 'data\wefix_prices.sqlite3'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw 'Archivio SQLite esistente non trovato' }
if (Test-Path -LiteralPath (Join-Path $incoming 'wefix_prices.sqlite3')) { throw 'Una copia di migrazione esiste gia: non viene sovrascritta' }
New-Item -ItemType Directory -Force -Path $incoming | Out-Null
& python (Join-Path $repo 'migration_export.py') $source $incoming
if ($LASTEXITCODE -ne 0) { throw 'Copia SQLite non riuscita' }
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
Write-Output 'Archivio copiato e configurazione privata pronta.'
