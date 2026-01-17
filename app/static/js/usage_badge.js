// static/js/usage_badge.js
async function refreshUsageBadge() {
  // Aceptamos tanto usage-badge (nuevo) como usageBadge (por compatibilidad)
  const container =
    document.getElementById('usage-badge') ||
    document.getElementById('usageBadge');

  if (!container) {
    console.warn('usage_badge: no se encontró el contenedor del badge');
    return;
  }

  // Span de texto interno (si existe)
  const textEl =
    document.getElementById('usage-text') ||
    container;

  try {
    // Llamamos al endpoint real de uso
    const r = await fetch('/api/usage/balance', { cache: 'no-store' });
    if (!r.ok) throw new Error('usage http ' + r.status);
    const j = await r.json();

    const usedSec = j.used_seconds || 0;
    const allowanceSec = j.allowance_seconds || 0;

    const usedMin = usedSec / 60;
    const allowanceMin = allowanceSec / 60;
    const remainingMin = allowanceMin - usedMin;

    // 1 decimal para usados / libres, entero para total
    const usedLabel = usedMin.toFixed(1);
    const allowanceLabel = allowanceMin.toFixed(0);
    const remainingLabel = Math.max(0, remainingMin).toFixed(1);

    const text = `${usedLabel}/${allowanceLabel} min · libre ${remainingLabel} min`;

    if (textEl) {
      textEl.textContent = text;
    } else {
      container.textContent = text;
    }

    container.title = `Usados: ${usedLabel} min de ${allowanceLabel} min totales`;
    container.style.display = 'inline-flex';
  } catch (e) {
    console.warn('No se pudo leer /api/usage/balance', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  refreshUsageBadge();
  // Refrescar cada minuto
  setInterval(refreshUsageBadge, 60_000);
});
