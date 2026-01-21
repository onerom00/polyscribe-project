# scripts/smoke.ps1
# Uso:  pwsh -File scripts\smoke.ps1   (o desde PowerShell normal)

# 1) preparar un audio pequeño
Copy-Item -Path "C:\Windows\Media\ding.wav" -Destination ".\test.wav" -Force

# 2) crear job
$resp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/jobs" `
  -Form @{ audio = Get-Item ".\test.wav"; idioma = "es" }

if (-not $resp.job_id) {
  Write-Host "Fallo al crear job:" -ForegroundColor Red
  $resp | ConvertTo-Json -Depth 5
  exit 1
}
$job = $resp.job_id
Write-Host "JOB=$job" -ForegroundColor Cyan

# 3) poll 10 veces
for ($i=1; $i -le 10; $i++) {
  Start-Sleep -Seconds 2
  try {
    $s = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:5000/jobs/{0}" -f $job)
    Write-Host ("[{0}/10] status={1}" -f $i, $s.status)
    if ($s.status -eq "done" -or $s.status -eq "error") {
      $s | ConvertTo-Json -Depth 6
      break
    }
  } catch {
    Write-Host "Error consultando job: $_" -ForegroundColor Yellow
  }
}
