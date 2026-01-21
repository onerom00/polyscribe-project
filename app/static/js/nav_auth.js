// static/js/nav_auth.js
(function () {
  "use strict";

  // =========================
  // Helpers: USER_ID robusto
  // =========================
  function getUserIdFromDOM() {
    const el = document.querySelector("[data-user-id]");
    const uid = el?.getAttribute("data-user-id");
    return uid && uid.trim() !== "" ? uid.trim() : null;
  }

  function getUserIdFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const uid = params.get("user_id");
    return uid && uid.trim() !== "" ? uid.trim() : null;
  }

  function getUserIdFromLocalStorage() {
    try {
      const uid = localStorage.getItem("user_id");
      return uid && uid.trim() !== "" ? uid.trim() : null;
    } catch {
      return null;
    }
  }

  function setUserIdToLocalStorage(userId) {
    try {
      localStorage.setItem("user_id", userId);
    } catch {}
  }

  // Regla final:
  // 1) data-user-id (backend) manda
  // 2) ?user_id
  // 3) localStorage
  function resolveUserId() {
    const fromDOM = getUserIdFromDOM();
    if (fromDOM) {
      setUserIdToLocalStorage(fromDOM);
      return fromDOM;
    }

    const fromQuery = getUserIdFromQuery();
    if (fromQuery) {
      setUserIdToLocalStorage(fromQuery);
      return fromQuery;
    }

    return getUserIdFromLocalStorage();
  }

  function isLoggedIn() {
    return !!resolveUserId();
  }

  // =========================
  // UI: actualizar badge/panel
  // =========================
  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function setHTML(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  function setVisible(id, visible) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  function setDisabled(id, disabled) {
    const el = document.getElementById(id);
    if (!el) return;
    el.disabled = !!disabled;
  }

  function showRefreshStatus(type, msg) {
    // Si existe un contenedor tipo "toast/status", lo usamos.
    // Si no existe, no rompemos nada.
    const el = document.getElementById("refresh-status");
    if (!el) return;

    el.className = ""; // reset
    el.classList.add("refresh-status", `status-${type}`);
    el.textContent = msg;
    el.style.display = "block";
  }

  function hideRefreshStatus() {
    const el = document.getElementById("refresh-status");
    if (!el) return;
    el.style.display = "none";
  }

  // =========================
  // Fetch: usage balance
  // =========================
  async function fetchUsageBalance(userId) {
    // IMPORTANTE:
    // Tu backend ya acepta X-User-Id o user_id (según tu config)
    // Vamos con querystring por seguridad, y header como extra.
    const url = `/api/usage/balance?user_id=${encodeURIComponent(userId)}`;

    const res = await fetch(url, {
      method: "GET",
      headers: {
        "X-User-Id": userId,
      },
      credentials: "same-origin",
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Error ${res.status}: ${text || "No response body"}`);
    }

    return await res.json();
  }

  function applyUsageToUI(data) {
    // Esperamos un JSON tipo:
    // { used_minutes, remaining_minutes, limit_minutes, max_file_mb, plan }
    // Si tu backend devuelve nombres distintos, me lo dices y lo ajusto.

    const used = Number(data.used_minutes ?? 0);
    const remaining = Number(data.remaining_minutes ?? 0);
    const limit = Number(data.limit_minutes ?? data.monthly_limit_minutes ?? 0);
    const maxFile = Number(data.max_file_mb ?? 25);

    // Badge mini (si existe)
    setText("usage-badge-used", `${used}`);
    setText("usage-badge-remaining", `${remaining}`);

    // Panel detallado (si existe)
    setText("usage-used-minutes", `${used}`);
    setText("usage-remaining-minutes", `${remaining}`);
    setText("usage-limit-minutes", `${limit}`);
    setText("usage-max-file", `${maxFile} MB`);

    // Banner bajo saldo (si existe)
    // Regla: si remaining <= 0 => mostrar banner crítico
    if (remaining <= 0) {
      setVisible("usage-banner-zero", true);
      setVisible("usage-banner-low", false);
    } else if (remaining <= 2) {
      setVisible("usage-banner-zero", false);
      setVisible("usage-banner-low", true);
    } else {
      setVisible("usage-banner-zero", false);
      setVisible("usage-banner-low", false);
    }
  }

  // =========================
  // Refrescar usage (botón)
  // =========================
  async function refreshUsageUI() {
    const userId = resolveUserId();

    if (!userId) {
      // No está logueado: ocultamos panel si aplica
      showRefreshStatus("warn", "Debes iniciar sesión para ver tu saldo.");
      setVisible("usage-panel", false);
      return;
    }

    hideRefreshStatus();
    setDisabled("btn-refresh", true);

    // Si tienes un spinner o texto del botón, lo manejamos sin romper
    const btn = document.getElementById("btn-refresh");
    const originalText = btn ? btn.textContent : null;
    if (btn) btn.textContent = "Refrescando...";

    try {
      const data = await fetchUsageBalance(userId);
      applyUsageToUI(data);
      setVisible("usage-panel", true);
      showRefreshStatus("ok", "Saldo actualizado ✅");
    } catch (err) {
      console.error("refreshUsageUI error:", err);
      showRefreshStatus("error", "No se pudo refrescar el saldo. Intenta de nuevo.");
    } finally {
      setDisabled("btn-refresh", false);
      if (btn && originalText) btn.textContent = originalText;
    }
  }

  // =========================
  // Inicialización
  // =========================
  function bindRefreshButton() {
    const btn = document.getElementById("btn-refresh");
    if (!btn) return;

    btn.addEventListener("click", function (e) {
      e.preventDefault();
      refreshUsageUI();
    });
  }

  function boot() {
    // Si está logueado, intentamos cargar el saldo una vez al entrar
    // (pero sin obligar nada si falla)
    bindRefreshButton();

    const uid = resolveUserId();
    if (uid) {
      // Intento inicial silencioso
      refreshUsageUI();
    } else {
      // Guest: ocultar panel si existe
      setVisible("usage-panel", false);
    }
  }

  document.addEventListener("DOMContentLoaded", boot);

  // Exponemos por si otros scripts lo necesitan (payments.js)
  window.PolyScribeAuth = {
    resolveUserId,
    isLoggedIn,
    refreshUsageUI,
  };
})();
