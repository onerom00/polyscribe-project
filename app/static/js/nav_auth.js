// static/js/nav_auth.js
(function () {
  const $ = (s) => document.querySelector(s);

  async function fetchMe() {
    try {
      const res = await fetch("/api/auth/me", { method: "GET", credentials: "include" });
      const txt = await res.text();
      let data = {};
      try { data = JSON.parse(txt); } catch { data = {}; }
      if (!res.ok) return { authenticated: false };
      return data || { authenticated: false };
    } catch {
      return { authenticated: false };
    }
  }

  function setNavAuthUI(authenticated) {
    const loginLink  = $("#nav-login-link");
    const signupLink = $("#nav-signup-link");
    const logoutLink = $("#nav-logout-link");
    const accountLink = $("#nav-account-link");

    const loginAlt  = $("#btn-login") || $("#login-link");
    const signupAlt = $("#btn-register") || $("#register-link");

    const show = (el) => { if (el) el.style.display = "inline-flex"; };
    const hide = (el) => { if (el) el.style.display = "none"; };

    if (authenticated) {
      hide(loginLink); hide(signupLink);
      hide(loginAlt);  hide(signupAlt);
      show(logoutLink);
      show(accountLink);
    } else {
      show(loginLink); show(signupLink);
      show(loginAlt);  show(signupAlt);
      hide(logoutLink);
      hide(accountLink);
    }
  }

  function setUsageText(text) {
    const t1 = document.getElementById("usage-text");
    const t2 = document.getElementById("usage-text-nav");
    if (t1) t1.textContent = text;
    if (t2) t2.textContent = text;

    const b1 = document.getElementById("usage-badge");
    const b2 = document.getElementById("usage-badge-nav");
    if (b1) b1.style.display = "inline-flex";
    if (b2) b2.style.display = "inline-flex";
  }

  function hideUsageUI() {
    const b1 = document.getElementById("usage-badge");
    const b2 = document.getElementById("usage-badge-nav");
    if (b1) b1.style.display = "none";
    if (b2) b2.style.display = "none";

    const panel = document.getElementById("usage-panel");
    if (panel) panel.style.display = "none";
  }

  async function boot() {
    const me = await fetchMe();
    const isLogged = !!(me && me.authenticated);

    setNavAuthUI(isLogged);

    try {
      document.body.dataset.auth = isLogged ? "1" : "0";
      if (isLogged && me.user_id) document.body.dataset.userId = String(me.user_id);
      else document.body.dataset.userId = "";
    } catch {}

    // Si NO hay sesión => ocultar badges/panel (nada de “muñequito” vacío)
    if (!isLogged) {
      hideUsageUI();
      return;
    }

    // Badge de uso solo si hay sesión
    try {
      const res = await fetch("/api/usage/balance", { method: "GET", credentials: "include" });
      const txt = await res.text();
      let data = {};
      try { data = JSON.parse(txt); } catch { data = {}; }

      if (res.ok) {
        const usedMin = Number(data.used_seconds || 0) / 60;
        const allowMin = Number(data.allowance_seconds || 0) / 60;
        const remain = Math.max(0, allowMin - usedMin);
        setUsageText(`${usedMin.toFixed(1)}/${allowMin.toFixed(0)} min · libre ${remain.toFixed(1)} min`);
      }
    } catch {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
