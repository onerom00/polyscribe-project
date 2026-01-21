// static/js/nav_auth.js
(function () {
  "use strict";

  const $ = (s) => document.querySelector(s);

  // -----------------------------
  // Resolve user_id (robusto)
  // -----------------------------
  function resolveUserId() {
    let id = "";

    // 1) server rendered (data-user-id)
    try {
      id = (document.body?.dataset?.userId || "").trim();
    } catch (_) {}

    // 2) querystring ?user_id=
    try {
      const qs = new URLSearchParams(window.location.search);
      const q = (qs.get("user_id") || "").trim();
      if (q) id = q;
    } catch (_) {}

    // 3) localStorage
    if (!id) {
      try {
        id = (localStorage.getItem("user_id") || "").trim();
      } catch (_) {
        id = "";
      }
    }

    // persist
    if (id) {
      try {
        localStorage.setItem("user_id", id);
      } catch (_) {}
    }

    return id; // puede ser ""
  }

  function setUserId(id) {
    try {
      if (id) localStorage.setItem("user_id", id);
      else localStorage.removeItem("user_id");
    } catch (_) {}
  }

  // -----------------------------
  // DOM targets (si existen)
  // -----------------------------
  const navLogin = $("#nav-login-link");
  const navSignup = $("#nav-signup-link");
  const navAccount = $("#nav-account-link");
  const navLogout = $("#nav-logout-link");

  const usageBadgeNav = $("#usage-badge-nav");
  const usageTextNav = $("#usage-text-nav");

  // -----------------------------
  // Helpers UI
  // -----------------------------
  function show(el) {
    if (!el) return;
    el.style.display = "";
  }
  function hide(el) {
    if (!el) return;
    el.style.display = "none";
  }

  function setAuthUI(userId) {
    // Guest
    if (!userId) {
      show(navLogin);
      show(navSignup);
      hide(navAccount);
      hide(navLogout);

      if (usageBadgeNav) hide(usageBadgeNav);
      return;
    }

    // Logged
    hide(navLogin);
    hide(navSignup);
    show(navAccount);
    show(navLogout);

    if (usageBadgeNav) show(usageBadgeNav);
    if (usageTextNav && !usageTextNav.textContent.trim()) {
      usageTextNav.textContent = "—/— min · libre —";
    }
  }

  // -----------------------------
  // Append user_id to internal links (solo si hay user)
  // -----------------------------
  function withUserId(url, userId) {
    try {
      if (!userId) return url;

      // no tocar anchors / externos / mailto / tel
      if (!url || url.startsWith("http") || url.startsWith("mailto:") || url.startsWith("tel:") || url.startsWith("#")) {
        return url;
      }

      const u = new URL(url, window.location.origin);
      if (!u.searchParams.get("user_id")) u.searchParams.set("user_id", userId);
      return u.pathname + u.search + u.hash;
    } catch (_) {
      return url;
    }
  }

  function patchLinks(userId) {
    if (!userId) return;

    // Ajustamos links clave para que mantengan user_id
    const links = document.querySelectorAll('a[href^="/"]:not([href^="//"])');
    links.forEach((a) => {
      const href = (a.getAttribute("href") || "").trim();
      if (!href) return;

      // No tocar logout
      if (href.startsWith("/auth/logout")) return;

      // Ajustar solo ciertas rutas para no ensuciar todo
      const keep = ["/", "/history", "/pricing", "/ayuda", "/account"];
      const isKeep = keep.some((p) => href === p || href.startsWith(p + "?") || href.startsWith(p + "#"));

      if (!isKeep) return;

      const newHref = withUserId(href, userId);
      a.setAttribute("href", newHref);
    });
  }

  // -----------------------------
  // Active nav highlighting (data-path)
  // -----------------------------
  function markActiveNav() {
    const path = window.location.pathname || "/";
    const items = document.querySelectorAll(".ps-nav-links a[data-path]");
    items.forEach((a) => {
      const p = a.getAttribute("data-path");
      if (!p) return;
      if (p === path) a.classList.add("active");
      else a.classList.remove("active");
    });
  }

  // -----------------------------
  // Logout behavior
  // -----------------------------
  function wireLogout() {
    if (!navLogout) return;

    navLogout.addEventListener("click", (e) => {
      // dejamos que backend haga logout si existe endpoint
      // pero limpiamos localStorage SIEMPRE para evitar estados raros.
      setUserId("");
      try {
        localStorage.removeItem("ps_last_job_id");
      } catch (_) {}

      // Si el backend no existe o falla, igual te sacamos
      // (no bloqueamos navegación)
    });
  }

  // -----------------------------
  // Init
  // -----------------------------
  const USER_ID = resolveUserId();
  setAuthUI(USER_ID);
  patchLinks(USER_ID);
  markActiveNav();
  wireLogout();

  // Sync si cambia en otra pestaña
  window.addEventListener("storage", (ev) => {
    if (!ev) return;
    if (ev.key === "user_id") {
      const id = resolveUserId();
      setAuthUI(id);
      patchLinks(id);
    }
  });
})();
