param([string]$CaseName, [string]$Capture)
$ErrorActionPreference = 'Stop'
if ($CaseName) {
    # Child process exercises the actual launcher without HTTP, k6 or real secrets.
    function global:Read-Host {
        param([string]$Prompt, [switch]$AsSecureString)
        if ($AsSecureString) { return ConvertTo-SecureString 'synthetic-password-only' -AsPlainText -Force }
        return 'carga@example.com'
    }
    function global:k6 {
        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
        $parsedStores = ConvertFrom-Json $env:LOADTEST_STORES
        @{
            orders = $env:LOADTEST_ORDERS
            vus = $env:LOADTEST_VUS
            sustained = $env:LOADTEST_SUSTAINED
            stores = @($parsedStores).Count
        } | ConvertTo-Json | Set-Content -Encoding UTF8 $Capture
        $global:LASTEXITCODE = 0
    }
    $launcher = Join-Path $PSScriptRoot 'Start-OrdersKitchen.ps1'
    switch ($CaseName) {
        'sustained' { & $launcher -Lojas carga-01,carga-02,carga-03,carga-04,carga-05 -Sustentado -CredencialUnica }
        'batch' { & $launcher -Pedidos 100 -Fluxos 20 }
        'invalid-batch' { & $launcher -Pedidos 101 }
        'invalid-stores' { & $launcher -Sustentado }
        default { throw 'Unknown test case' }
    }
    exit $LASTEXITCODE
}
$executable = (Get-Process -Id $PID).Path
$temp = Join-Path ([IO.Path]::GetTempPath()) ('fomizero-launcher-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
try {
    foreach ($case in @('sustained','batch','invalid-batch','invalid-stores')) {
        $captureFile = Join-Path $temp ($case + '.json')
        & $executable -NoProfile -File $PSCommandPath -CaseName $case -Capture $captureFile
        $resultCode = $LASTEXITCODE
        if ($case -like 'invalid-*') {
            if ($resultCode -eq 0 -or (Test-Path $captureFile)) { throw "$case did not reject before k6" }
        } else {
            if ($resultCode -ne 0 -or -not (Test-Path $captureFile)) { throw "$case failed to launch k6" }
            $data = Get-Content $captureFile -Raw | ConvertFrom-Json
            if ($case -eq 'sustained') {
                if ($data.orders -ne '600' -or $data.vus -ne '10' -or $data.sustained -ne '1' -or $data.stores -ne 5) {
                    throw ('Sustained configuration incorrect: ' + ($data | ConvertTo-Json -Compress))
                }
            } elseif ($data.orders -ne '100' -or $data.vus -ne '20' -or $data.sustained -ne '0' -or $data.stores -ne 1) {
                throw ('Batch configuration incorrect: ' + ($data | ConvertTo-Json -Compress))
            }
        }
        Write-Host "PASS: $case"
    }
} finally { Remove-Item $temp -Recurse -Force }
exit 0
