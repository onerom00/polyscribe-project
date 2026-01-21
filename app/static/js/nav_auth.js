// static/js/nav_auth.js
(function () {
  "use strict";

  // =========================================================
  // PolyScribe NAV + Auth helper (Opción B)
  // - resolveUserId: body[data-user-id] -> ?user_id -> localStorage
  // - NO bindea botones de refresh (evita doble listener)
  // - Marca link activo
  // - Muestra Entrar/Registro si guest
  // - Muestra Mi cuenta/Salir si logged
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
      if (userId && String(userId).trim()) {
        localStorage.setItem("user_id", String(userId).trim());
      }
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
  // Helpers UI
  // -------------------------
  function setVisible(el, visible) {
    if (!el) return;
    el.style.display = visible ? "" : "none";
  }

  // -------------------------
  // Crear botones "Mi cuenta" y "Salir" si no existen
  // -------------------------
  function ensureAccountButtons() {
    const right = document.querySelector(".ps-nav .inner .right");
    if (!right) return;

    // Botón Mi cuenta
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

    // Botón Salir
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

    // Acción logout (frontend safe)
    btnLogout.addEventListener("click", async () => {
      try {
        // 1) borrar localStorage
        try {
          localStorage.removeItem("user_id");
        } catch (_) {}

        // 2) intentar cerrar sesión backend si existe
        // (si no existe, no pasa nada)
        try {
          await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
        } catch (_) {}

        // 3) volver a home limpio
        window.location.href = "/";
      } catch (_) {
        window.location.href = "/";
      }
    });
  }

  // -------------------------
  // UI: login/register vs account/logout
  // -------------------------
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
  // Optional: Sync con backend (si existe /api/usage/whoami)
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
  // Boot
  // -------------------------
  async function boot() {
    setActiveNavLink();

    // Guardar user_id si backend lo mandó en data-user-id
    resolveUserId();

    // Intentar sincronizar sesión real (si existe endpoint)
    await trySyncWhoAmI();

    updateAuthButtons();
  }

  document.addEventListener("DOMContentLoaded", boot);

  // Sync si cambia user_id en otra pestaña
  window.addEventListener("storage", (ev) => {
    if (ev && ev.key === "user_id") {
      updateAuthButtons();
    }
  });

  // Exponemos helpers para otros scripts
  window.PolyScribeAuth = {
    resolveUserId,
    isLoggedIn,
    trySyncWhoAmI,
  };
})();
