// static/js/exports_v2.js
// Maneja las descargas SRT / VTT / DOCX / PDF contra /api/exports/<fmt>

function ps_getTranscriptText() {
  const t = document.getElementById("transcript");
  if (!t) return "";
  // Puede ser <textarea> o <div>
  return (t.value !== undefined ? t.value : t.textContent) || "";
}

function ps_getSummaryText() {
  // Intentamos varios ids posibles
  const candIds = ["summary", "summary-text", "summary-box"];
  for (const id of candIds) {
    const el = document.getElementById(id);
    if (el) {
      return (el.value !== undefined ? el.value : el.textContent) || "";
    }
  }
  return "";
}

async function ps_export(fmt) {
  try {
    const transcript = ps_getTranscriptText();
    const summary = ps_getSummaryText();

    if (!transcript.trim()) {
      alert("No hay transcripción para exportar todavía.");
      return;
    }

    const payload = {
      transcript: transcript,
      summary: summary,
      filename: "polyscribe_resultado"
    };

    const resp = await fetch(`/api/exports/${fmt}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!resp.ok) {
      const text = await resp.text();
      console.error("Error exportando:", resp.status, text);
      alert("No se pudo exportar el archivo (" + resp.status + ").");
      return;
    }

    const blob = await resp.blob();

    // Intentar leer nombre desde Content-Disposition
    let filename = "resultado." + fmt;
    const cd = resp.headers.get("Content-Disposition");
    if (cd) {
      const match = cd.match(/filename="?([^"]+)"?/i);
      if (match && match[1]) {
        filename = match[1];
      }
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Excepción en ps_export:", err);
    alert("Ocurrió un error al preparar la descarga.");
  }
}

function ps_bindExportButton(fmt) {
  // Aceptamos id="download-srt-btn" o id="download-srt"
  const btn =
    document.getElementById(`download-${fmt}-btn`) ||
    document.getElementById(`download-${fmt}`);
  if (!btn) return;

  btn.addEventListener("click", function (ev) {
    ev.preventDefault();
    ps_export(fmt);
  });
}

// Ejecutar cuando el DOM esté listo
document.addEventListener("DOMContentLoaded", function () {
  ["srt", "vtt", "docx", "pdf"].forEach(ps_bindExportButton);
});
