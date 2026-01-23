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
    // Soportamos IDs usados en tus páginas
    const loginLink  = $("#nav-login-link");
    const signupLink = $("#nav-signup-link");
    const logoutLink = $("#nav-logout-link");

    // algunas pantallas pueden usar estos ids alternos
    const loginAlt  = $("#btn-login") || $("#login-link");
    const signupAlt = $("#btn-register") || $("#register-link");

    const show = (el) => { if (el) el.style.display = "inline-flex"; };
    const hide = (el) => { if (el) el.style.display = "none"; };

    if (authenticated) {
      hide(loginLink); hide(signupLink);
      hide(loginAlt);  hide(signupAlt);
      show(logoutLink);
    } else {
      show(loginLink); show(signupLink);
      show(loginAlt);  show(signupAlt);
      hide(logoutLink);
    }
  }

  // Opcional: actualizar badges si existen (sin romper nada)
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

  async function boot() {
    const me = await fetchMe();
    const isLogged = !!(me && me.authenticated);

    // ✅ UI auth consistente
    setNavAuthUI(isLogged);

    // ✅ Si el servidor sabe tu user_id, lo ponemos en body dataset (para scripts existentes)
    try {
      if (isLogged && me.user_id) {
        document.body.dataset.userId = String(me.user_id);
      }
      document.body.dataset.auth = isLogged ? "1" : "0";
    } catch {}

    // ✅ (Opcional) Badge de uso solo si logueado
    // OJO: aquí no usamos localStorage ni querystring.
    if (isLogged) {
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
  }

  // ✅ correr después del DOM
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
