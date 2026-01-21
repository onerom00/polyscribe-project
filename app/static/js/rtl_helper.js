// static/js/rtl_helper.js
// Utilidad pequeña para alternar la dirección del texto (LTR/RTL)
// en los <textarea> de transcripción/resumen y justificar visualmente.
// Expone window.applyTextDirection(langCode, { ids?: string[] })

(function (w, d) {
  "use strict";

  const RTL_LANGS = ["ar", "fa", "he", "ur", "ps"]; // árabe, persa, hebreo, urdu, pastún

  function isRTL(langCode) {
    if (!langCode) return false;
    const code = String(langCode).trim().toLowerCase().slice(0, 2);
    return RTL_LANGS.includes(code);
  }

  function applyTextDirection(langCode, opts) {
    const rtl = isRTL(langCode);
    const ids = (opts && opts.ids) || ["transcript", "summary"];

    ids.forEach((id) => {
      const el = d.getElementById(id);
      if (!el) return;

      // Alterna clases (asegúrate de tener .rtl/.ltr en tu CSS)
      el.classList.toggle("rtl", rtl);
      el.classList.toggle("ltr", !rtl);

      // Refuerza la dirección para el cursor/selección
      el.setAttribute("dir", rtl ? "rtl" : "ltr");
    });

    // Si tienes una insignia opcional para mostrar LTR/RTL
    const badge = d.getElementById("lang_badge_dir");
    if (badge) badge.textContent = rtl ? "RTL" : "LTR";
  }

  // Exporta a global
  w.applyTextDirection = applyTextDirection;

  // Arranque automático: si ya hay idioma detectado/seleccionado al cargar
  d.addEventListener("DOMContentLoaded", () => {
    const langEl = d.getElementById("lang_detected") || d.getElementById("lang_selected");
    const lang =
      (langEl && (langEl.value || langEl.textContent || "") || "").trim();
    if (lang) applyTextDirection(lang);
  });
})(window, document);
