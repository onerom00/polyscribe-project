// static/js/usage_badge.js
async function refreshUsageBadge(){
  const el = document.getElementById('usageBadge');
  if(!el) return;
  try{
    const r = await fetch('/usage', {cache:'no-store'});
    if(!r.ok) throw new Error('usage http ' + r.status);
    const j = await r.json();

    const usedMin = Math.round(j.used_seconds/60);
    const capMin  = j.cap_minutes;
    const restMin = Math.max(0, Math.floor(j.remaining_seconds/60));

    el.innerHTML = `<span class="dot"></span> ${usedMin}/${capMin} min · libre ${restMin} min`;
    el.title = `Mes ${j.month_key} · usados ${usedMin} min de ${capMin}`;
    el.style.display = 'inline-flex';
  }catch(e){
    console.warn('No se pudo leer /usage', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  refreshUsageBadge();
  setInterval(refreshUsageBadge, 60_000);
});
