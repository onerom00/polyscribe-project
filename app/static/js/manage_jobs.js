// static/js/manage_jobs.js

// Detecta user_id desde ?user_id=…
function getUserId() {
  const m = new URLSearchParams(location.search).get("user_id");
  return m ? m : "";
}

// Guarda el job id activo para que los botones funcionen
window.currentJobId = null;
window.userId = getUserId();

// LTR / RTL + justificado
function applyTextDirection(langCode) {
  const rtlLangs = ["ar","fa","he","ur","ps"];
  const rtl = rtlLangs.includes((langCode || "").slice(0,2).toLowerCase());
  ["transcript","summary"].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle("rtl", rtl);
    el.classList.toggle("ltr", !rtl);
    el.style.textAlign = "justify";
  });
}
window.applyTextDirection = applyTextDirection;

// Helpers HTTP
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}
async function del(url) {
  const r = await fetch(url, { method: "DELETE" });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}

// Acciones
async function renameJob() {
  if (!window.currentJobId) return alert("No hay Job activo.");
  const newName = prompt("Nuevo nombre visible del archivo:");
  if (!newName) return;
  try {
    const j = await postJSON(`/jobs/${window.currentJobId}/rename?user_id=${window.userId}`, { new_name: newName });
    const lbl = document.getElementById("filename_label");
    if (lbl) lbl.textContent = j.filename;
  } catch (e) {
    alert("No se pudo renombrar: " + e.message);
  }
}

async function resummarize(lang) {
  if (!window.currentJobId) return alert("No hay Job activo.");
  try {
    const j = await postJSON(`/jobs/${window.currentJobId}/resummarize?user_id=${window.userId}`, { lang });
    const sum = document.getElementById("summary");
    if (sum) sum.value = j.summary || "";
    applyTextDirection(j.language_used || lang);
  } catch (e) {
    alert("No se pudo re-resumir: " + e.message);
  }
}

async function deleteJob() {
  if (!window.currentJobId) return alert("No hay Job activo.");
  if (!confirm("¿Eliminar este job? Esta acción no se puede deshacer.")) return;
  try {
    await del(`/jobs/${window.currentJobId}?user_id=${window.userId}`);
    const tr = document.getElementById("transcript");
    const su = document.getElementById("summary");
    const jid = document.getElementById("job_id");
    if (tr) tr.value = "";
    if (su) su.value = "";
    if (jid) jid.textContent = "";
    window.currentJobId = null;
  } catch (e) {
    alert("No se pudo eliminar: " + e.message);
  }
}

// Wire-up si existen los botones
window.addEventListener("DOMContentLoaded", () => {
  const bRename = document.getElementById("btn-rename");
  const bDelete = document.getElementById("btn-delete");
  const bResumSel = document.getElementById("btn-resummarize");
  if (bRename) bRename.addEventListener("click", renameJob);
  if (bDelete) bDelete.addEventListener("click", deleteJob);
  if (bResumSel) {
    bResumSel.addEventListener("change", (e) => {
      const lang = (e.target.value || "").trim();
      if (lang) resummarize(lang);
      e.target.selectedIndex = 0; // vuelve al placeholder
    });
  }
});

// Exponer setter para cuando recibes el job_id en tu flujo actual
window.setCurrentJob = function(jobId, langCode) {
  window.currentJobId = jobId;
  if (langCode) applyTextDirection(langCode);
};
