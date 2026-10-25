param(
    [string[]]$Lojas = @('meuburger'),
    [ValidateRange(1,100)][int]$Pedidos = 10,
    [ValidateRange(1,20)][int]$Fluxos = 2
)
$ErrorActionPreference = 'Stop'
if ($Fluxos -gt $Pedidos) { throw 'Fluxos nao pode exceder Pedidos.' }
if (-not (Get-Command k6 -ErrorAction SilentlyContinue)) { throw 'Instale Grafana.k6 pelo winget primeiro.' }
$scriptFile = Join-Path $PSScriptRoot 'orders-kitchen.js'
if (-not (Test-Path $scriptFile)) { throw 'Baixe orders-kitchen.js para a mesma pasta deste arquivo.' }
Write-Host "STAGING: ate $Pedidos pedidos de teste em $($Lojas -join ', '), com $Fluxos fluxos."
Write-Host 'As lojas precisam ser exclusivas para testes e estar sem integracoes externas.'
Write-Host 'Os pedidos ficam PRONTO no painel e consomem a cota da loja. Nao serao apagados.'
$entries = @()
$code = 1
try {
    foreach ($slug in $Lojas) {
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
    $env:LOADTEST_STORES = ConvertTo-Json -InputObject $entries -Compress
    $env:LOADTEST_ORDERS = [string]$Pedidos
    $env:LOADTEST_VUS = [string]$Fluxos
    $env:LOADTEST_ISOLATED = 'SIM'
    $report = Join-Path $PSScriptRoot ('resultado-pedidos-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
    & k6 run "--summary-export=$report" $scriptFile
    $code = $LASTEXITCODE
    Write-Host "Relatorio: $report"
} finally {
    foreach ($entry in $entries) { $entry.password = $null }
    Remove-Item Env:LOADTEST_STORES,Env:LOADTEST_ORDERS,Env:LOADTEST_VUS,Env:LOADTEST_ISOLATED -ErrorAction SilentlyContinue
}
exit $code
