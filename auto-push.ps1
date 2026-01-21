# auto-push.ps1
# Revisa el repo cada X segundos y, si hay cambios, hace git add/commit/push.

$repoPath = "C:\Users\Casa\Documents\polyScribe-project"
$branch   = "main"

# Cada cuántos segundos revisar
$intervalSeconds = 20

Write-Host "AutoPush (modo sencillo) iniciado en: $repoPath" -ForegroundColor Green
Write-Host "Rama destino: $branch"
Write-Host "Revisando cambios cada $intervalSeconds segundos..." -ForegroundColor Yellow

Set-Location $repoPath

while ($true) {
    # Revisa si hay cambios pendientes
    $status = git status --porcelain

    if ($status) {
        $msg = "auto-push $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        Write-Host "Cambios detectados. Haciendo commit y push: $msg" -ForegroundColor Cyan

        git add .
        git commit -m $msg
        git push origin $branch
    }

    Start-Sleep -Seconds $intervalSeconds
}
