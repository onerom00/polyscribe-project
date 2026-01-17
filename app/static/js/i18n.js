/* static/js/i18n.js */
/** Cambia los textos de la UI según el idioma seleccionado (es/en/pt/fr). */
(() => {
  const DICT = {
    es: {
      "status.completed": "Completado",
      "btn.transcribe": "Transcribir",
      "btn.copy_text": "Copiar texto",
      "btn.download_txt": "Descargar TXT",
      "btn.srt": "SRT",
      "btn.vtt": "VTT",
      "btn.docx": "DOCX",
      "btn.pdf": "PDF",
      "btn.download_summary": "Descargar Resumen",
      "btn.download_json": "Descargar JSON",
      "label.language": "Idioma",
      "label.force_iso": "Forzar código ISO-639-1 (opcional)",
      "hint.drop": "Arrastra tu archivo aquí o haz clic para seleccionar",
      "hint.formats": "Formatos: mp3, wav, m4a, ogg, webm… Máx. 25 MB",
      "ph.transcript": "Aquí aparecerá la transcripción...",
      "ph.summary": "Aquí aparecerá el resumen...",
      "footer.file": "Archivo:",
      "footer.lang_selected": "Idioma elegido:",
      "footer.lang_detected": "Idioma detectado:",
      "footer.job_id": "Job ID:"
    },
    en: {
      "status.completed": "Completed",
      "btn.transcribe": "Transcribe",
      "btn.copy_text": "Copy text",
      "btn.download_txt": "Download TXT",
      "btn.srt": "SRT",
      "btn.vtt": "VTT",
      "btn.docx": "DOCX",
      "btn.pdf": "PDF",
      "btn.download_summary": "Download Summary",
      "btn.download_json": "Download JSON",
      "label.language": "Language",
      "label.force_iso": "Force ISO-639-1 code (optional)",
      "hint.drop": "Drag your file here or click to select",
      "hint.formats": "Formats: mp3, wav, m4a, ogg, webm… Max 25 MB",
      "ph.transcript": "The transcript will appear here...",
      "ph.summary": "The summary will appear here...",
      "footer.file": "File:",
      "footer.lang_selected": "Chosen language:",
      "footer.lang_detected": "Detected language:",
      "footer.job_id": "Job ID:"
    },
    pt: {
      "status.completed": "Concluído",
      "btn.transcribe": "Transcrever",
      "btn.copy_text": "Copiar texto",
      "btn.download_txt": "Baixar TXT",
      "btn.srt": "SRT",
      "btn.vtt": "VTT",
      "btn.docx": "DOCX",
      "btn.pdf": "PDF",
      "btn.download_summary": "Baixar Resumo",
      "btn.download_json": "Baixar JSON",
      "label.language": "Idioma",
      "label.force_iso": "Forçar código ISO-639-1 (opcional)",
      "hint.drop": "Arraste o arquivo aqui ou clique para selecionar",
      "hint.formats": "Formatos: mp3, wav, m4a, ogg, webm… Máx. 25 MB",
      "ph.transcript": "A transcrição aparecerá aqui...",
      "ph.summary": "O resumo aparecerá aqui...",
      "footer.file": "Arquivo:",
      "footer.lang_selected": "Idioma escolhido:",
      "footer.lang_detected": "Idioma detectado:",
      "footer.job_id": "Job ID:"
    },
    fr: {
      "status.completed": "Terminé",
      "btn.transcribe": "Transcrire",
      "btn.copy_text": "Copier le texte",
      "btn.download_txt": "Télécharger TXT",
      "btn.srt": "SRT",
      "btn.vtt": "VTT",
      "btn.docx": "DOCX",
      "btn.pdf": "PDF",
      "btn.download_summary": "Télécharger le résumé",
      "btn.download_json": "Télécharger JSON",
      "label.language": "Langue",
      "label.force_iso": "Forcer le code ISO-639-1 (facultatif)",
      "hint.drop": "Glissez votre fichier ici ou cliquez pour sélectionner",
      "hint.formats": "Formats : mp3, wav, m4a, ogg, webm… Max 25 Mo",
      "ph.transcript": "La transcription apparaîtra ici...",
      "ph.summary": "Le résumé apparaîtra ici...",
      "footer.file": "Fichier :",
      "footer.lang_selected": "Langue choisie :",
      "footer.lang_detected": "Langue détectée :",
      "footer.job_id": "Job ID :"
    }
  };

  const normalize = (v) => {
    v = (v || "").toLowerCase();
    if (v.startsWith("es")) return "es";
    if (v.startsWith("en")) return "en";
    if (v.startsWith("pt")) return "pt";
    if (v.startsWith("fr")) return "fr";
    return "en";
  };

  function applyI18n(lang) {
    const L = DICT[normalize(lang)] || DICT.en;

    // data-i18n -> texto
    document.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;
      const val = L[key];
      if (val !== undefined) el.innerText = val;
    });

    // data-i18n-placeholder -> placeholder
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
      const key = el.getAttribute("data-i18n-placeholder");
      const val = L[key];
      if (val !== undefined) el.setAttribute("placeholder", val);
    });

    try { localStorage.setItem("ui_lang", normalize(lang)); } catch {}
  }

  window.UII18N = {
    setLanguage: applyI18n,
    getLanguage: () => {
      const fromLS = (()=>{ try{return localStorage.getItem("ui_lang")||"";}catch{ return ""; } })();
      return normalize(fromLS || (document.documentElement.lang || "en"));
    },
  };

  document.addEventListener("DOMContentLoaded", () => {
    applyI18n(UII18N.getLanguage());
  });
})();
