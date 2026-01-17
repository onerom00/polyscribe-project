// static/js/exports_buttons.js

(function () {
  const $ = (s) => document.querySelector(s);

  function buildPayload() {
    const transcript = ($("#transcript")?.value || "").trim();
    const summary = ($("#summary")?.value || "").trim();
    const language = ($("#lang_detected")?.innerText || $("#lang_selected")?.value || "auto").trim().toLowerCase();
    const jobId = ($("#job_id")?.innerText || "").replace(/[^\d]/g, "");
    const filename = ($("#file_name")?.innerText || $("#file_name")?.value || "polyscribe").trim();

    const payload = { transcript, summary, language, filename };
    if (jobId) payload.job_id = jobId;
    return payload;
  }

  async function postExport(url) {
    const payload = buildPayload();
    const qs = new URLSearchParams(location.search);
    const user_id = qs.get("user_id") || window.user_id || "";

    const res = await fetch(`${url}?user_id=${encodeURIComponent(user_id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Error: ${err.error || res.statusText}`);
      return;
    }

    // Descargar
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const match = /filename="?([^"]+)"?/i.exec(cd);
    const filename = match ? match[1] : "polyscribe.bin";

    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }

  // Botones
  $("#btn_export_pdf")?.addEventListener("click", () => postExport("/api/exports/pdf"));
  $("#btn_export_docx")?.addEventListener("click", () => postExport("/api/exports/docx"));
  $("#btn_export_srt")?.addEventListener("click", () => postExport("/api/exports/srt"));
})();
