// static/js/nav_auth.js
(function () {
  "use strict";

  // =========================
  // USER_ID robusto (body[data-user-id] -> ?user_id -> localStorage)
  // =========================
  function getUserIdFromBody() {
    try {
      const uid = (document.body && document.body.dataset && document.body.dataset.userId) ? document.body.dataset.userId : "";
      const v = String(uid || "").trim();
      return v ? v : "";
    } catch {
      return "";
    }
  }

  function getUserIdFromQuery() {
    try {
      const params = new URLSearchParams(window.location.search);
      const uid = String(params.get("user_id") || "").trim();
      return uid ? uid : "";
    } catch {
      return "";
    }
  }

  function getUserIdFromLocalStorage() {
    try {
      const uid = String(localStorage.getItem("user_id") || "").trim();
      return uid ? uid : "";
    } catch {
      return "";
    }
  }

  function setUserIdToLocalStorage(userId) {
    try {
      if (userId) localStorage.setItem("user_id", userId);
    } catch {}
  }

  function resolveUserId() {
    // 1) backend -> data-user-id
    let id = getUserIdFromBody();

    // 2) querystring user_id (si viene, manda)
    const q = getUserIdFromQuery();
    if (q) id = q;

    // 3) localStorage
    if (!id) id = getUserIdFromLocalStorage();

    // persistimos si hay
    if (id) setUserIdToLocalStorage(id);

    // ✅ IMPORTANTE: NO forzar "guest"
    return id; // "" si no hay
  }

  function isLoggedIn() {
    return !!resolveUserId();
  }

  // =========================
  // UI helpers
  // =========================
  function show(el, visible) {
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  // =========================
  // NAV: link activo
  // =========================
  function setActiveNav() {
    const path = window.location.pathname || "/";
    const links = document.querySelectorAll(".ps-nav-links a[data-path]");
    if (!links || !links.length) return;

    links.forEach(a => {
      const p = a.getAttribute("data-path") || "";
      if (!p) return;
      if (p === path) a.classList.add("active");
      else a.classList.remove("active");
    });
  }

  // =========================
  // Auth UI: Entrar/Registro vs Badge
  // =========================
  function syncAuthUI() {
    const uid = resolveUserId();

    // Elementos que ya tienes en index.html
    const loginLink  = document.getElementById("nav-login-link");
    const signupLink = document.getElementById("nav-signup-link");
    const usageNav   = document.getElementById("usage-badge-nav"); // badge del header

    // Si NO hay usuario: mostrar Entrar/Registro, ocultar badge nav
    if (!uid) {
      show(loginLink, true);
      show(signupLink, true);
      show(usageNav, false);
      return;
    }

    // Si SÍ hay usuario: ocultar Entrar/Registro, mostrar badge nav
    show(loginLink, false);
    show(signupLink, false);
    show(usageNav, true);
  }

  // =========================
  // (Opcional) refrescar saldo NAV 1 sola vez (sin loops)
  // =========================
  async function refreshNavBalanceOnce() {
    const uid = resolveUserId();
    if (!uid) return;

    const el = document.getElementById("usage-text-nav");
    if (!el) return; // si no existe, no hacemos nada

    try {
      const url = `/api/usage/balance?user_id=${encodeURIComponent(uid)}`;
      const res = await fetch(url, { method: "GET", headers: { "X-User-Id": uid } });
      if (!res.ok) return;

      const data = await res.json().catch(() => ({}));
      const usedSec = Number(data.used_seconds || 0);
      const allowSec = Number(data.allowance_seconds || 0);

      const usedMin = usedSec / 60;
      const allowMin = allowSec / 60;
      const remain = Math.max(0, allowMin - usedMin);

      el.textContent = `${usedMin.toFixed(1)}/${allowMin.toFixed(0)} min · libre ${remain.toFixed(1)} min`;
    } catch {
      // silencioso
    }
  }

  // =========================
  // Boot
  // =========================
  function boot() {
    setActiveNav();
    syncAuthUI();
    refreshNavBalanceOnce();

    // Si en otra pestaña cambia user_id (login/logout), sincroniza sin romper
    window.addEventListener("storage", (ev) => {
      if (ev && ev.key === "user_id") {
        syncAuthUI();
        refreshNavBalanceOnce();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  // Exponemos por si lo necesitas en payments.js o debugging
  window.PolyScribeAuth = {
    resolveUserId,
    isLoggedIn,
    syncAuthUI,
    refreshNavBalanceOnce,
  };
})();
