# test_plans.ps1
# 1) Login manteniendo cookies en sesión
$sess = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginForm = "email=tu@correo.com&password=Secreta123!"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/auth/login" -Method POST -ContentType "application/x-www-form-urlencoded" -Body $loginForm -WebSession $sess | Out-Null

function Get-Balance {
  $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/usage/balance" -WebSession $sess
  return [int]([math]::Round(($r.allowance_seconds - $r.used_seconds)/60.0))
}

function Simulate-Purchase([string]$sku, [int]$minutes, [string]$amount){
  $body = @{ sku=$sku; minutes=$minutes; amount=$amount } | ConvertTo-Json
  return Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/paypal/simulate_capture" -Method POST -ContentType "application/json" -Body $body -WebSession $sess
}

Write-Host "Saldo inicial (min): " (Get-Balance)

$plans = @(
  @{sku="starter_60"; minutes=60; amount="9.00"},
  @{sku="pro_300"; minutes=300; amount="29.00"},
  @{sku="biz_1200"; minutes=1200; amount="89.00"}
)

foreach($p in $plans){
  Write-Host "Comprando (simulado) $($p.sku) -> $($p.minutes) min..."
  $res = Simulate-Purchase $p.sku $p.minutes $p.amount
  Write-Host "  OK=$($res.ok) minutes=$($res.minutes)"
  Start-Sleep -Seconds 1
  Write-Host "  Saldo ahora (min): " (Get-Balance)
}

Write-Host "✅ Prueba de planes (simulada) completada."
