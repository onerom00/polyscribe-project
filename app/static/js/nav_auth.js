// static/js/nav_auth.js
(function () {
  const $ = (s) => document.querySelector(s);

  const LS_KEY = "user_id";

  async function fetchJSON(url) {
    try {
      const res = await fetch(url, { method: "GET", credentials: "include" });
      const txt = await res.text();
      let data = {};
      try { data = JSON.parse(txt); } catch { data = {}; }
      if (!res.ok) return { ok: false, status: res.status, data: {} };
      return { ok: true, status: res.status, data: data || {} };
    } catch {
      return { ok: false, status: 0, data: {} };
    }
  }

  async function fetchMe() {
    const r = await fetchJSON("/api/auth/me");
    if (!r.ok) return { authenticated: false };
    return r.data || { authenticated: false };
  }

  function safeSetLS(key, val) {
    try {
      if (val === null || val === undefined) {
        localStorage.removeItem(key);
      } else {
        localStorage.setItem(key, String(val));
      }
    } catch {}
  }

  function safeGetLS(key) {
    try {
      return (localStorage.getItem(key) || "").trim();
    } catch {
      return "";
    }
  }

  function purgeGuestLikeValues() {
    // Limpia basura típica
    const v = safeGetLS(LS_KEY);
    if (!v || v.toLowerCase() === "guest" || v.toLowerCase() === "null" || v.toLowerCase() === "undefined") {
      safeSetLS(LS_KEY, null);
    }
  }

  function ensureLogoutLink() {
    // Si existe, lo devolvemos.
    let logout = $("#nav-logout-link");
    if (logout) return logout;

    // Intento: algunos headers usan .right
    const right = document.querySelector("header .right") || document.querySelector(".ps-nav .right") || document.body;

    // Creamos un botón estilo similar a tus a11y-btn
    logout = document.createElement("a");
    logout.id = "nav-logout-link";
    logout.href = "/auth/logout";
    logout.className = "a11y-btn";
    logout.textContent = "Salir";
    logout.style.display = "none";

    // Insertarlo al final del bloque derecho
    try {
      if (right && right.appendChild) right.appendChild(logout);
      else document.body.appendChild(logout);
    } catch {}

    return logout;
  }

  function setNavAuthUI(isLogged) {
    // IDs principales
    const loginLink  = $("#nav-login-link");
    const signupLink = $("#nav-signup-link");

    // alternos
    const loginAlt  = $("#btn-login") || $("#login-link");
    const signupAlt = $("#btn-register") || $("#register-link");

    const logoutLink = ensureLogoutLink();

    const show = (el) => { if (el) el.style.display = "inline-flex"; };
    const hide = (el) => { if (el) el.style.display = "none"; };

    if (isLogged) {
      hide(loginLink); hide(signupLink);
      hide(loginAlt);  hide(signupAlt);
      show(logoutLink);
    } else {
      show(loginLink); show(signupLink);
      show(loginAlt);  show(signupAlt);
      hide(logoutLink);
    }
  }

  function setUsageBadgesVisible(visible) {
    const b1 = $("#usage-badge");
    const b2 = $("#usage-badge-nav");
    if (b1) b1.style.display = visible ? "inline-flex" : "none";
    if (b2) b2.style.display = visible ? "inline-flex" : "none";
  }

  function setUsageText(text) {
    const t1 = $("#usage-text");
    const t2 = $("#usage-text-nav");
    if (t1) t1.textContent = text;
    if (t2) t2.textContent = text;
    setUsageBadgesVisible(true);
  }

  async function refreshUsageIfLogged() {
    // Este endpoint ya respeta cookie (no dependemos de query/localStorage)
    const r = await fetchJSON("/api/usage/balance");
    if (!r.ok) return;

    const data = r.data || {};
    const usedMin  = Number(data.used_seconds || 0) / 60;
    const allowMin = Number(data.allowance_seconds || 0) / 60;
    const remain   = Math.max(0, allowMin - usedMin);

    setUsageText(`${usedMin.toFixed(1)}/${allowMin.toFixed(0)} min · libre ${remain.toFixed(1)} min`);
  }

  function syncUserIdEverywhere(userId) {
    // 1) dataset para tus templates/scripts
    try {
      document.body.dataset.userId = String(userId || "");
      document.body.dataset.auth = userId ? "1" : "0";
    } catch {}

    // 2) localStorage para compatibilidad con tus páginas (Opción B)
    // ⚠️ clave: aquí NO guardamos guest, solo id real
    if (userId) safeSetLS(LS_KEY, String(userId));
    else safeSetLS(LS_KEY, null);

    // 3) evento para que pricing/index/history puedan reaccionar sin loops
    try {
      window.dispatchEvent(new CustomEvent("ps:auth", { detail: { user_id: userId || "" } }));
    } catch {}
  }

  async function boot() {
    // Limpia “guest” previo antes de empezar
    purgeGuestLikeValues();

    const me = await fetchMe();
    const isLogged = !!(me && me.authenticated && me.user_id);

    if (isLogged) {
      // ✅ Autoridad: manda el server
      const uid = String(me.user_id);

      setNavAuthUI(true);
      syncUserIdEverywhere(uid);

      // Badge saldo
      await refreshUsageIfLogged();
    } else {
      // ✅ Si no hay sesión real, borramos todo rastro local
      setNavAuthUI(false);
      syncUserIdEverywhere("");

      // Oculta badges para no dar info falsa
      setUsageBadgesVisible(false);
    }
  }

  // Correr después del DOM
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
