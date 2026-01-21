// static/js/nav_auth.js
(function () {
  "use strict";

  /**
   * ✅ OBJETIVO (PRODUCCIÓN):
   * - La UI de auth (Entrar/Registro vs Mi cuenta/Salir) NO debe depender de:
   *   - ?user_id=...
   *   - localStorage user_id
   * Porque eso "simula" login y oculta Entrar/Registro.
   *
   * - La UI debe depender SOLO de sesión real (cookies) -> /api/usage/whoami
   *
   * DEV MODE opcional:
   * - Si quieres permitir el flujo viejo (header/localStorage/query) en DEV,
   *   activa: window.PS_ALLOW_DEV_USER_ID = true; (antes de cargar este script)
   */

  const ALLOW_DEV_USER_ID = !!window.PS_ALLOW_DEV_USER_ID;

  // =========================
  // Helpers DOM
  // =========================
  function $(sel) {
    return document.querySelector(sel);
  }

  function setVisible(elOrId, visible) {
    const el = typeof elOrId === "string" ? document.getElementById(elOrId) : elOrId;
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  // =========================
  // DEV fallback (NO PRODUCCIÓN)
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

  function clearLocalUserId() {
    try {
      localStorage.removeItem("user_id");
    } catch {}
  }

  function resolveDevUserId() {
    // Regla DEV:
    // 1) data-user-id
    // 2) ?user_id
    // 3) localStorage
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

  // =========================
  // ✅ PRODUCCIÓN: backend whoami
  // =========================
  async function fetchWhoAmI() {
    try {
      const r = await fetch("/api/usage/whoami", {
        method: "GET",
        credentials: "same-origin",
        headers: { "Accept": "application/json" },
      });

      // Si no hay sesión real, normalmente será 401/403 o ok:false
      if (!r.ok) return null;

      const j = await r.json().catch(() => ({}));
      if (j && j.user_id) return String(j.user_id).trim();
      return null;
    } catch {
      return null;
    }
  }

  // =========================
  // UI Auth Toggle (Entrar/Registro vs Mi cuenta/Salir)
  // =========================
  function applyAuthUI(isLogged) {
    // IDs típicos en tu index.html:
    const loginLink = document.getElementById("nav-login-link");
    const signupLink = document.getElementById("nav-signup-link");

    // Por si tienes botones alternativos (según tu navbar desplegada en prod):
    const accountLink = document.getElementById("nav-account-link"); // opcional
    const logoutLink = document.getElementById("nav-logout-link");   // opcional

    // Si existen los links de Entrar/Registro:
    if (loginLink) setVisible(loginLink, !isLogged);
    if (signupLink) setVisible(signupLink, !isLogged);

    // Si existen los links Mi cuenta/Salir:
    if (accountLink) setVisible(accountLink, isLogged);
    if (logoutLink) setVisible(logoutLink, isLogged);
  }

  // =========================
  // Usage balance (para badge/panel si quieres)
  // =========================
  async function fetchUsageBalance(userId) {
    const url = `/api/usage/balance?user_id=${encodeURIComponent(userId)}`;

    const res = await fetch(url, {
      method: "GET",
      headers: { "X-User-Id": userId },
      credentials: "same-origin",
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Error ${res.status}: ${text || "No response body"}`);
    }

    return await res.json();
  }

  function applyUsageToUI(data) {
    // Tu frontend nuevo usa: used_seconds, allowance_seconds, file_limit_bytes
    // pero este archivo viejo tenía used_minutes/remaining_minutes etc.
    // Entonces soportamos ambos formatos.

    // Formato nuevo:
    const usedSec = data.used_seconds != null ? Number(data.used_seconds || 0) : null;
    const allowSec = data.allowance_seconds != null ? Number(data.allowance_seconds || 0) : null;

    let usedMin, remainingMin, limitMin;

    if (usedSec != null && allowSec != null) {
      usedMin = usedSec / 60;
      limitMin = allowSec / 60;
      remainingMin = Math.max(0, limitMin - usedMin);
    } else {
      // Formato viejo:
      usedMin = Number(data.used_minutes ?? 0);
      remainingMin = Number(data.remaining_minutes ?? 0);
      limitMin = Number(data.limit_minutes ?? data.monthly_limit_minutes ?? 0);
    }

    // Badge mini (si existe)
    // (estos IDs tal vez no existan en tu UI actual, pero no rompe)
    setText("usage-badge-used", `${Math.round(usedMin)}`);
    setText("usage-badge-remaining", `${Math.round(remainingMin)}`);

    // Panel detallado (si existe)
    setText("usage-used-minutes", `${Math.round(usedMin)}`);
    setText("usage-remaining-minutes", `${Math.round(remainingMin)}`);
    setText("usage-limit-minutes", `${Math.round(limitMin)}`);

    // Max file
    const maxFileMB =
      data.file_limit_bytes != null
        ? Math.round(Number(data.file_limit_bytes || 0) / (1024 * 1024))
        : Number(data.max_file_mb ?? 25);

    setText("usage-max-file", `${maxFileMB} MB`);
  }

  async function refreshUsageUI(userId) {
    if (!userId) {
      // No logueado => ocultar panel si existe
      setVisible("usage-panel", false);
      return;
    }

    try {
      const data = await fetchUsageBalance(userId);
      applyUsageToUI(data);
      setVisible("usage-panel", true);
    } catch (err) {
      console.error("refreshUsageUI error:", err);
      // Si falla, no escondemos auth, solo el panel
      setVisible("usage-panel", false);
    }
  }

  // =========================
  // Boot
  // =========================
  async function boot() {
    // 1) Confirmar sesión real
    const whoamiId = await fetchWhoAmI();

    if (whoamiId) {
      // ✅ Logueado real
      applyAuthUI(true);

      // (Opcional) guardar para tu historial/dev
      setUserIdToLocalStorage(whoamiId);

      // refrescar panel/badges si aplica
      refreshUsageUI(whoamiId);
      return;
    }

    // 2) No hay sesión real
    applyAuthUI(false);

    // ✅ IMPORTANTÍSIMO:
    // Si no hay sesión real, limpiamos localStorage para que no "pegue" login falso.
    clearLocalUserId();

    // 3) DEV fallback (solo si lo activas explícitamente)
    if (ALLOW_DEV_USER_ID) {
      const devId = resolveDevUserId();
      if (devId) {
        // En DEV puedes querer ver usage aunque no haya sesión real
        refreshUsageUI(devId);
      }
    } else {
      // En producción, no mostrar panel para guest
      setVisible("usage-panel", false);
    }
  }

  document.addEventListener("DOMContentLoaded", boot);

  // Exponemos utilidades
  window.PolyScribeAuth = {
    // En prod, resolveUserId solo debe devolver sesión real.
    // Si necesitas dev fallback, activa window.PS_ALLOW_DEV_USER_ID = true.
    getSessionUserId: fetchWhoAmI,
  };
})();
