// static/js/nav_auth.js
(function () {
  "use strict";

  // =========================================================
  // NAV + Auth (PROD)
  // - En producción: SOLO consideramos "logged" si el backend confirma sesión
  //   via /api/usage/whoami  -> { user_id: "..." }
  // - Si whoami no existe o falla, fallback a Opción B (URL/localStorage)
  // =========================================================

  const STRICT_SESSION = true; // ✅ true = producción (recomendado)
  const WHOAMI_URL = "/api/usage/whoami";

  // -------------------------
  // Storage helpers
  // -------------------------
  function lsGet(key) {
    try {
      const v = localStorage.getItem(key);
      return v && v.trim() ? v.trim() : null;
    } catch (_) {
      return null;
    }
  }

  function lsSet(key, value) {
    try {
      if (value && String(value).trim()) localStorage.setItem(key, String(value).trim());
    } catch (_) {}
  }

  function lsDel(key) {
    try {
      localStorage.removeItem(key);
    } catch (_) {}
  }

  // -------------------------
  // Opción B (fallback)
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

  function resolveUserIdFallback() {
    const fromBody = getUserIdFromBody();
    if (fromBody) {
      lsSet("user_id", fromBody);
      return fromBody;
    }

    const fromQuery = getUserIdFromQuery();
    if (fromQuery) {
      lsSet("user_id", fromQuery);
      return fromQuery;
    }

    return lsGet("user_id");
  }

  // -------------------------
  // Session (whoami)
  // -------------------------
  async function tryWhoAmI() {
    try {
      const r = await fetch(WHOAMI_URL, { credentials: "same-origin" });
      if (!r.ok) return null;
      const j = await r.json().catch(() => ({}));
      const uid = (j && j.user_id ? String(j.user_id) : "").trim();
      return uid || null;
    } catch (_) {
      return null;
    }
  }

  // UID final (cache)
  let SESSION_UID = null;

  function resolveUserId() {
    // Si ya tenemos UID de sesión (confirmada por backend), usamos eso.
    if (SESSION_UID) return SESSION_UID;

    // Si estamos en modo estricto, NO confiamos en query/localStorage.
    if (STRICT_SESSION) return null;

    // Fallback a Opción B
    return resolveUserIdFallback();
  }

  function isLoggedIn() {
    return !!resolveUserId();
  }

  // -------------------------
  // NAV: link activo
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

  function setVisible(el, visible) {
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  // -------------------------
  // Botones Mi cuenta / Salir
  // -------------------------
  function ensureAccountButtons() {
    const right = document.querySelector(".ps-nav .inner .right");
    if (!right) return;

    let btnAccount = document.getElementById("nav-account-link");
    if (!btnAccount) {
      btnAccount = document.createElement("a");
      btnAccount.id = "nav-account-link";
      btnAccount.href = "/history";
      btnAccount.className = "a11y-btn";
      btnAccount.textContent = "Mi cuenta";
      btnAccount.style.display = "none";
      right.appendChild(btnAccount);
    }

    let btnLogout = document.getElementById("nav-logout-link");
    if (!btnLogout) {
      btnLogout = document.createElement("button");
      btnLogout.id = "nav-logout-link";
      btnLogout.type = "button";
      btnLogout.className = "a11y-btn";
      btnLogout.textContent = "Salir";
      btnLogout.style.display = "none";
      btnLogout.style.background = "#ffe5e5";
      btnLogout.style.borderColor = "#f3abab";
      btnLogout.style.color = "#8a1c1c";
      btnLogout.style.fontWeight = "800";
      right.appendChild(btnLogout);
    }

    btnLogout.addEventListener("click", async () => {
      // Limpieza frontend
      lsDel("user_id");
      SESSION_UID = null;

      // Intentar logout backend (si existe)
      try {
        await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
      } catch (_) {}

      // Redirigir limpio (sin user_id)
      window.location.href = "/";
    });
  }

  function updateAuthButtons() {
    ensureAccountButtons();

    const uid = resolveUserId();

    const loginLink = document.getElementById("nav-login-link");
    const signupLink = document.getElementById("nav-signup-link");
    const accountLink = document.getElementById("nav-account-link");
    const logoutLink = document.getElementById("nav-logout-link");

    if (uid) {
      // LOGGED
      setVisible(loginLink, false);
      setVisible(signupLink, false);
      setVisible(accountLink, true);
      setVisible(logoutLink, true);
    } else {
      // GUEST
      setVisible(loginLink, true);
      setVisible(signupLink, true);
      setVisible(accountLink, false);
      setVisible(logoutLink, false);
    }
  }

  // -------------------------
  // Boot
  // -------------------------
  async function boot() {
    setActiveNavLink();

    // Si modo estricto: el backend manda
    const who = await tryWhoAmI();

    if (who) {
      SESSION_UID = who;
      lsSet("user_id", who); // opcional, por compat
    } else {
      SESSION_UID = null;
      if (STRICT_SESSION) {
        // En modo estricto, ignoramos ?user_id y localStorage si no hay sesión
        // (Esto evita "login falso" por URL)
        // Puedes comentar estas dos líneas si quieres conservarlo para dev.
        lsDel("user_id");
      } else {
        // fallback
        resolveUserIdFallback();
      }
    }

    updateAuthButtons();
  }

  document.addEventListener("DOMContentLoaded", boot);

  // Sync si cambia user_id en otra pestaña (modo no estricto)
  window.addEventListener("storage", (ev) => {
    if (ev && ev.key === "user_id") updateAuthButtons();
  });

  window.PolyScribeAuth = {
    resolveUserId,
    isLoggedIn,
    tryWhoAmI,
  };
})();
