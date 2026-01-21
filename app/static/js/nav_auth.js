// static/js/nav_auth.js
(function () {
  "use strict";

  // =========================================================
  // PolyScribe NAV + Auth helper (Opción B)
  // - resolveUserId: body[data-user-id] -> ?user_id -> localStorage
  // - NO bindea botones (para evitar doble listener con scripts de cada página)
  // - Ajusta links del nav (active)
  // - Alterna botones Entrar/Registro si hay sesión/uid
  // - Expone helpers para otros scripts (payments.js, etc.)
  // =========================================================

  // -------------------------
  // USER ID helpers
  // -------------------------
  function getUserIdFromBody() {
    const id = (document.body?.dataset?.userId || "").trim();
    return id || null;
  }

  function getUserIdFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const uid = (params.get("user_id") || "").trim();
    return uid || null;
  }

  function getUserIdFromLocalStorage() {
    try {
      const uid = (localStorage.getItem("user_id") || "").trim();
      return uid || null;
    } catch (_) {
      return null;
    }
  }

  function setUserIdToLocalStorage(userId) {
    try {
      if (userId && String(userId).trim()) localStorage.setItem("user_id", String(userId).trim());
    } catch (_) {}
  }

  // Regla final:
  // 1) data-user-id (backend) manda
  // 2) ?user_id
  // 3) localStorage
  function resolveUserId() {
    const fromBody = getUserIdFromBody();
    if (fromBody) {
      setUserIdToLocalStorage(fromBody);
      return fromBody;
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

  // -------------------------
  // NAV: active link
  // -------------------------
  function setActiveNavLink() {
    const path = (window.location.pathname || "/").replace(/\/+$/, "") || "/";
    const links = document.querySelectorAll(".ps-nav-links a[data-path]");
    links.forEach((a) => {
      const p = (a.getAttribute("data-path") || "").trim() || "/";
      const norm = p.replace(/\/+$/, "") || "/";
      if (norm === path) a.classList.add("active");
      else a.classList.remove("active");
    });
  }

  // -------------------------
  // UI: login/register toggles
  // -------------------------
  function setVisible(el, visible) {
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  function updateAuthButtons() {
    const uid = resolveUserId();
    const loginLink = document.getElementById("nav-login-link");
    const signupLink = document.getElementById("nav-signup-link");

    // Si está logueado, ocultamos Entrar/Registro (tu web puede mostrar perfil luego)
    if (uid) {
      setVisible(loginLink, false);
      setVisible(signupLink, false);
    } else {
      setVisible(loginLink, true);
      setVisible(signupLink, true);
    }
  }

  // -------------------------
  // Optional: Sync con backend (si existe /api/usage/whoami)
  // - Si backend confirma sesión, guardamos user_id en localStorage
  // - No rompe si endpoint no existe
  // -------------------------
  async function trySyncWhoAmI() {
    try {
      const r = await fetch("/api/usage/whoami", { credentials: "same-origin" });
      if (!r.ok) return null;
      const j = await r.json().catch(() => ({}));
      const uid = (j && j.user_id ? String(j.user_id) : "").trim();
      if (uid) {
        setUserIdToLocalStorage(uid);
        return uid;
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  // -------------------------
  // Optional: refresh usage badge (helpers)
  // NO lo ejecutamos automáticamente para no duplicar fetch en páginas
  // -------------------------
  async function fetchUsageBalanceRobust(userId) {
    // 1) query + header
    if (userId) {
      const r1 = await fetch(`/api/usage/balance?user_id=${encodeURIComponent(userId)}`, {
        method: "GET",
        headers: { "X-User-Id": userId },
        credentials: "same-origin",
      });
      if (r1.ok) return await r1.json();
    }

    // 2) fallback sin query (por si backend usa sesión/header)
    const r2 = await fetch(`/api/usage/balance`, {
      method: "GET",
      headers: userId ? { "X-User-Id": userId } : {},
      credentials: "same-origin",
    });
    if (!r2.ok) {
      const t = await r2.text().catch(() => "");
      throw new Error(`balance_failed_${r2.status}:${t}`);
    }
    return await r2.json();
  }

  function fmtBadgeText(data) {
    // Esperado: { used_seconds, allowance_seconds, file_limit_bytes }
    const usedSec = Number(data?.used_seconds || 0);
    const allowSec = Number(data?.allowance_seconds || 0);

    const usedMin = usedSec / 60;
    const allowMin = allowSec / 60;
    const remain = Math.max(0, allowMin - usedMin);

    // usado/limite (limite lo mostramos entero)
    return `${usedMin.toFixed(1)}/${allowMin.toFixed(0)} min · libre ${remain.toFixed(1)} min`;
  }

  async function refreshUsageBadge(options) {
    const opts = options || {};
    const silent = !!opts.silent;

    // Re-resolver por si cambió localStorage en caliente
    let uid = resolveUserId();

    // Si no hay uid, intentamos backend whoami (sesión)
    if (!uid) {
      const synced = await trySyncWhoAmI();
      if (synced) uid = synced;
    }

    // Si sigue vacío, ocultamos badges si existen
    const badge = document.getElementById("usage-badge");
    const badgeNav = document.getElementById("usage-badge-nav");
    if (!uid) {
      if (badge) badge.style.display = "none";
      if (badgeNav) badgeNav.style.display = "none";
      if (!silent) console.warn("[nav_auth] No user_id. Badges ocultos.");
      updateAuthButtons();
      return { ok: false, user_id: "" };
    }

    try {
      const data = await fetchUsageBalanceRobust(uid);
      const text = fmtBadgeText(data);

      const t1 = document.getElementById("usage-text");
      const t2 = document.getElementById("usage-text-nav");
      if (t1) t1.textContent = text;
      if (t2) t2.textContent = text;

      if (badge) badge.style.display = "inline-flex";
      if (badgeNav) badgeNav.style.display = "inline-flex";

      updateAuthButtons();
      return { ok: true, user_id: uid, data };
    } catch (e) {
      if (!silent) console.warn("[nav_auth] refreshUsageBadge error:", e);
      updateAuthButtons();
      return { ok: false, user_id: uid, error: String(e?.message || e) };
    }
  }

  // -------------------------
  // Boot
  // -------------------------
  async function boot() {
    setActiveNavLink();

    // Si backend puso data-user-id, ya quedará en localStorage por resolveUserId()
    resolveUserId();

    // Sincroniza sesión si existe endpoint (no rompe)
    await trySyncWhoAmI();

    updateAuthButtons();

    // Nota: NO llamamos refreshUsageBadge() aquí para evitar duplicar fetch.
    // Cada página (index/history/pricing) ya maneja su propio refresh.
  }

  document.addEventListener("DOMContentLoaded", boot);

  // Mantener en sync si user_id cambia desde otra pestaña (login/register)
  window.addEventListener("storage", (ev) => {
    if (ev && ev.key === "user_id") {
      updateAuthButtons();
      // NO hacemos refresh automático aquí para evitar doble fetch;
      // La página principal ya escucha storage y refresca su UI.
    }
  });

  // Exponemos helpers (payments.js y otros)
  window.PolyScribeAuth = {
    resolveUserId,
    isLoggedIn,
    trySyncWhoAmI,
    refreshUsageBadge, // opcional para páginas que quieran usarlo
  };
})();
