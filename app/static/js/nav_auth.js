// static/js/nav_auth.js
(function () {
  const $ = (s) => document.querySelector(s);

  // ---------- helpers ----------
  function safeGetLS(k) {
    try { return (localStorage.getItem(k) || "").trim(); } catch { return ""; }
  }
  function safeSetLS(k, v) {
    try { localStorage.setItem(k, v); } catch {}
  }

  // ---------- resolve user ----------
  function resolveUserId() {
    // 1) server-rendered
    let id = ((document.body && document.body.dataset && document.body.dataset.userId) ? document.body.dataset.userId : "").trim();

    // 2) querystring
    const qs = new URLSearchParams(window.location.search);
    const qUser = (qs.get("user_id") || "").trim();
    if (qUser) id = qUser;

    // 3) localStorage
    if (!id) id = safeGetLS("user_id");

    // Normaliza: guest NO es login real
    if ((id || "").toLowerCase() === "guest") id = "";

    // Persist
    if (id) safeSetLS("user_id", id);

    return id; // "" => anonymous
  }

  let USER_ID = resolveUserId();
  const IS_LOGGED = !!USER_ID;

  // ---------- active nav link ----------
  (function setActiveNav() {
    const path = window.location.pathname || "/";
    const links = document.querySelectorAll(".ps-nav-links a[data-path]");
    links.forEach(a => {
      const p = a.getAttribute("data-path");
      if (!p) return;
      if (p === path) a.classList.add("active");
      else a.classList.remove("active");
    });
  })();

  // ---------- toggle auth buttons ----------
  // Opcionales (si existen, los usa)
  const loginLink = $("#nav-login-link");
  const signupLink = $("#nav-signup-link");
  const accountLink = $("#nav-account-link");
  const logoutLink = $("#nav-logout-link");

  // Si no existen, no rompe.
  function show(el, yes) {
    if (!el) return;
    el.style.display = yes ? "inline-flex" : "none";
  }

  // Reglas:
  // - Anonymous: Entrar + Registro visibles
  // - Logged: Mi cuenta + Salir visibles
  show(loginLink, !IS_LOGGED);
  show(signupLink, !IS_LOGGED);
  show(accountLink, IS_LOGGED);
  show(logoutLink, IS_LOGGED);

  // ---------- optional: expose user in window ----------
  window.PS_USER_ID = USER_ID || "";
  window.PS_IS_LOGGED = IS_LOGGED;

  // ---------- storage sync (otra pestaña) ----------
  window.addEventListener("storage", (ev) => {
    if (!ev || ev.key !== "user_id") return;
    const newId = resolveUserId();
    const newLogged = !!newId;

    show(loginLink, !newLogged);
    show(signupLink, !newLogged);
    show(accountLink, newLogged);
    show(logoutLink, newLogged);

    window.PS_USER_ID = newId || "";
    window.PS_IS_LOGGED = newLogged;
  });
})();
