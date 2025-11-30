# quick_test.ps1 — Login + saldo + simulación de compras

# 0) Sanity check
try {
  $pong = Invoke-RestMethod -Uri "http://127.0.0.1:8000/auth/ping" -TimeoutSec 5
  "PING => $($pong.msg) (ok=$($pong.ok))"
} catch {
  Write-Host "❌ Server no responde en 127.0.0.1:8000" -ForegroundColor Red
  exit 1
}

# 1) Sesión + Login
$sess = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginBody = @{ email = "tu@correo.com"; password = "Secreta123!" }

function PostJson([string]$url, $obj) {
  try {
    $json = $obj | ConvertTo-Json
    return Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $json -WebSession $sess
  } catch {
    $resp = $_.Exception.Response
    if ($resp) {
      $status = [int]$resp.StatusCode
      $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
      $text = $reader.ReadToEnd()
      Write-Host "HTTP $status" -ForegroundColor Red
      Write-Host $text
    } else {
      Write-Host $_
    }
    return $null
  }
}

function GetApi([string]$url) {
  try {
    return Invoke-RestMethod -Uri $url -WebSession $sess
  } catch {
    $resp = $_.Exception.Response
    if ($resp) {
      $status = [int]$resp.StatusCode
      $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
      $text = $reader.ReadToEnd()
      Write-Host "HTTP $status" -ForegroundColor Red
      Write-Host $text
    } else { Write-Host $_ }
    return $null
  }
}

"== LOGIN =="
$login = PostJson "http://127.0.0.1:8000/auth/login" $loginBody
$login | ConvertTo-Json -Depth 5

"== ME =="
$me = GetApi "http://127.0.0.1:8000/auth/me"
$me | ConvertTo-Json -Depth 5

"== SALDO ANTES =="
$bal1 = GetApi "http://127.0.0.1:8000/api/usage/balance"
$bal1 | ConvertTo-Json -Depth 5

# 2) Simular compras (Starter / Pro / Business)
$plans = @(
  @{ id = "starter_60";  minutes = 60 },
  @{ id = "pro_300";     minutes = 300 },
  @{ id = "biz_1200";    minutes = 1200 }
)
foreach ($p in $plans) {
  "`n== SIMULATE $($p.id) ($($p.minutes) min) =="
  $res = PostJson "http://127.0.0.1:8000/api/paypal/simulate_capture" @{ plan_id = $p.id }
  $res | ConvertTo-Json -Depth 5
  "== SALDO =="
  (GetApi "http://127.0.0.1:8000/api/usage/balance") | ConvertTo-Json -Depth 5
}

"== FIN =="
