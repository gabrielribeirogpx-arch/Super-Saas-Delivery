param(
    [string[]]$Lojas = @('meuburger'),
    [ValidateRange(1,100)][int]$Pedidos = 10,
    [ValidateRange(1,20)][int]$Fluxos = 2,
    [switch]$Sustentado,
    [switch]$CredencialUnica
)
$ErrorActionPreference = 'Stop'
$effectiveOrders = $Pedidos
$effectiveVUs = $Fluxos
if ($Sustentado) {
    if ($Lojas.Count -lt 5) { throw 'Modo sustentado exige pelo menos 5 lojas de teste.' }
    $effectiveOrders = 600
    $effectiveVUs = 10
}
if ($effectiveVUs -gt $effectiveOrders) { throw 'Fluxos nao pode exceder Pedidos.' }
if (-not (Get-Command k6 -ErrorAction SilentlyContinue)) { throw 'Instale Grafana.k6 pelo winget primeiro.' }
$scriptFile = Join-Path $PSScriptRoot 'orders-kitchen.js'
if (-not (Test-Path $scriptFile)) { throw 'Baixe orders-kitchen.js para a mesma pasta deste arquivo.' }
if ($Sustentado) {
    Write-Host "STAGING SUSTENTADO: ate $effectiveOrders pedidos de teste em $($Lojas -join ', ')."
} else {
    Write-Host "STAGING: ate $effectiveOrders pedidos de teste em $($Lojas -join ', '), com $effectiveVUs fluxos."
}
if ($Sustentado) { Write-Host '1 novo pedido por segundo NO TOTAL durante 10 minutos, ate 20 VUs e 2 minutos para concluir os ultimos pedidos.' }
Write-Host 'As lojas precisam ser exclusivas para testes e estar sem integracoes externas.'
Write-Host 'Os pedidos ficam PRONTO no painel e consomem a cota da loja. Nao serao apagados.'
$entries = @()
$code = 1
try {
    foreach ($slug in $Lojas) {
        if ($CredencialUnica -and $entries.Count -gt 0) {
            $entries += @{slug=$slug; email=$entries[0].email; password=$entries[0].password}
            continue
        }
        $email = Read-Host "E-mail do administrador de $slug"
        $secret = Read-Host "Senha de $slug (oculta)" -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
        try {
            $entries += @{slug=$slug; email=$email; password=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)}
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
            $secret.Dispose()
        }
    }
    $env:LOADTEST_SUSTAINED = if ($Sustentado) { '1' } else { '0' }
    $env:LOADTEST_STORES = ConvertTo-Json -InputObject $entries -Compress
    $env:LOADTEST_ORDERS = [string]$effectiveOrders
    $env:LOADTEST_VUS = [string]$effectiveVUs
    $env:LOADTEST_ISOLATED = 'SIM'
    $report = Join-Path $PSScriptRoot ('resultado-pedidos-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
    & k6 run "--summary-export=$report" $scriptFile
    $code = $LASTEXITCODE
    Write-Host "Relatorio: $report"
} finally {
    foreach ($entry in $entries) { $entry.password = $null }
    Remove-Item Env:LOADTEST_STORES,Env:LOADTEST_ORDERS,Env:LOADTEST_VUS,Env:LOADTEST_ISOLATED,Env:LOADTEST_SUSTAINED -ErrorAction SilentlyContinue
}
exit $code
