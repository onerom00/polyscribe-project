# e2e_paypal.ps1 (simple, sin param)
$ErrorActionPreference = "Stop"

# ===== Config r?pida =====
$BaseUrl = "http://127.0.0.1:8000"
$Plan    = "starter_60"   # starter_60 | pro_300 | biz_1200
$Email   = "tu@correo.com"
$Password= "Secreta123!"
# Si pasas un argumento, lo uso como plan:
if ($args.Length -ge 1) { $Plan = $args[0] }

function Step([string]$t){ Write-Host "`n== $t ==" -ForegroundColor Cyan }
function Fail([string]$m){ Write-Host $m -ForegroundColor Red; exit 1 }

function PostJson([string]$url, $obj, $sess){
  try{
    $json = $obj | ConvertTo-Json
    return Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $json -WebSession $sess
  }catch{
    $resp = $_.Exception.Response
    if ($resp) {
      $status = [int]$resp.StatusCode
      $reader = New-Object IO.StreamReader($resp.GetResponseStream())
      $text = $reader.ReadToEnd()
      Write-Host "HTTP $status" -ForegroundColor Red
      Write-Host $text
    } else { Write-Host $_ }
    return $null
  }
}
function GetApi([string]$url, $sess){
  try { return Invoke-RestMethod -Uri $url -WebSession $sess }
  catch {
    $resp = $_.Exception.Response
    if ($resp) {
      $status = [int]$resp.StatusCode
      $reader = New-Object IO.StreamReader($resp.GetResponseStream())
      $text = $reader.ReadToEnd()
      Write-Host "HTTP $status" -ForegroundColor Red
      Write-Host $text
    } else { Write-Host $_ }
    return $null
  }
}

Step "Diag"
$auth = Invoke-RestMethod -Uri "$BaseUrl/auth/diag"
$pp   = Invoke-RestMethod -Uri "$BaseUrl/api/paypal/diag"
if(-not $auth.ok -or -not $auth.diag.has_secret_key){ Fail "Auth no OK (secret_key=false)" }
if(-not $pp.ok -or -not $pp.has_client_id -or -not $pp.has_secret -or -not $pp.token_check_ok){ Fail "PayPal no OK" }

Step "Login"
$sess = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod -Uri "$BaseUrl/auth/login" -Method POST -ContentType "application/x-www-form-urlencoded" -Body "email=$Email&password=$Password" -WebSession $sess | Out-Null
$me = GetApi "$BaseUrl/auth/me" $sess
if(-not $me -or -not $me.authenticated){ Fail "No autenticado" }

Step "Saldo antes"
$bal1 = GetApi "$BaseUrl/api/usage/balance" $sess
$before = [int]$bal1.allowance_seconds

Step "Crear orden ($Plan)"
$o = PostJson "$BaseUrl/api/paypal/create_order" @{ plan_id = $Plan } $sess
if(-not $o -or -not $o.ok){ Fail "No se pudo crear la orden" }
$orderId = $o.order.id
$approve = $o.order.approve_url
if(-not $orderId -or -not $approve){ Fail "Respuesta sin order.id o approve_url" }

Write-Host "`nAbriendo PayPal para aprobaci?n (sandbox buyer)..." -ForegroundColor Yellow
Start-Process $approve
[void](Read-Host "Pulsa ENTER cuando termines la aprobaci?n en PayPal")

Step "Capturar"
$cap = PostJson "$BaseUrl/api/paypal/capture" @{ order_id = $orderId } $sess
if(-not $cap -or -not $cap.ok){ Fail "Captura fallida" }

Step "Saldo despu?s"
$bal2 = GetApi "$BaseUrl/api/usage/balance" $sess
$after = [int]$bal2.allowance_seconds
$deltaMin = [math]::Round(($after-$before)/60,2)
Write-Host "`n$([char]0x2714) ?xito: saldo +$deltaMin min (de $([math]::Round($before/60,2)) a $([math]::Round($after/60,2)))" -ForegroundColor Green
