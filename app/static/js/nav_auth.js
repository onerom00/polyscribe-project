// static/js/nav_auth.js
(function () {
  "use strict";

  // =========================
  // Helpers: USER_ID robusto
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

  // Regla final:
  // 1) data-user-id (backend) manda
  // 2) ?user_id
  // 3) localStorage
  function resolveUserIdFront() {
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
  // Backend whoami (verdad)
  // =========================
  async function resolveUserIdBackend() {
    try {
      const r = await fetch("/api/usage/whoami", { credentials: "same-origin" });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j && j.user_id) {
        const uid = String(j.user_id).trim();
        if (uid) {
          setUserIdToLocalStorage(uid);
          return uid;
        }
      }
    } catch {}
    return null;
  }

  async function resolveUserId() {
    // Preferimos backend. Si no hay sesión real, usamos front.
    const b = await resolveUserIdBackend();
    if (b) return b;
    return resolveUserIdFront();
  }

  // =========================
  // UI helpers
  // =========================
  function qs(sel) {
    return document.querySelector(sel);
  }

  function ensureNavRightUI() {
    // Soportamos 2 layouts:
    // A) header.ps-nav .inner (nuevo)
    // B) header simple con nav/topbar (history viejo)
    // Objetivo: que SIEMPRE haya botones.

    const psInner = qs("header.ps-nav .inner");

    // ---- Caso A: nuevo header (ideal)
    if (psInner) {
      let right = psInner.querySelector(".right");
      if (!right) {
        right = document.createElement("div");
        right.className = "right";
        psInner.appendChild(right);
      }

      // Badge
      if (!right.querySelector("#usage-badge-nav")) {
        const badge = document.createElement("span");
        badge.id = "usage-badge-nav";
        badge.className = "badge-usage";
        badge.style.display = "inline-flex";
        badge.innerHTML = `<span id="usage-text-nav">—/— min · libre —</span>`;
        right.appendChild(badge);
      }

      // Entrar
      if (!right.querySelector("#nav-login-link")) {
        const a = document.createElement("a");
        a.id = "nav-login-link";
        a.href = "/auth/login";
        a.className = "a11y-btn";
        a.textContent = "Entrar";
        right.appendChild(a);
      }

      // Registro
      if (!right.querySelector("#nav-signup-link")) {
        const a = document.createElement("a");
        a.id = "nav-signup-link";
        a.href = "/auth/register";
        a.className = "a11y-btn";
        a.textContent = "Registro";
        // estilo tipo index
        a.style.background = "#22c55e";
        a.style.borderColor = "#16a34a";
        a.style.color = "#0b111d";
        right.appendChild(a);
      }

      // Mi cuenta
      if (!right.querySelector("#nav-account-link")) {
        const a = document.createElement("a");
        a.id = "nav-account-link";
        a.href = "/account";
        a.className = "a11y-btn";
        a.textContent = "Mi cuenta";
        a.style.display = "none";
        right.appendChild(a);
      }

      // Salir
      if (!right.querySelector("#nav-logout-link")) {
        const a = document.createElement("a");
        a.id = "nav-logout-link";
        a.href = "/auth/logout";
        a.className = "a11y-btn";
        a.textContent = "Salir";
        a.style.display = "none";
        // pequeño tono rojo como lo veías en pantalla
        a.style.borderColor = "#f3abab";
        a.style.background = "#fde2e2";
        a.style.color = "#8a1c1c";
        right.appendChild(a);
      }

      return { mode: "ps-nav" };
    }

    // ---- Caso B: header viejo (history/pricing viejos)
    // Intentamos agregar un mini bloque a la derecha del header
    const legacyHeader = qs("body > .container header");
    if (legacyHeader) {
      let topbar = legacyHeader.querySelector(".topbar");
      if (!topbar) {
        topbar = document.createElement("div");
        topbar.className = "topbar";
        legacyHeader.appendChild(topbar);
      }

      if (!topbar.querySelector("#legacy-auth-wrap")) {
        const wrap = document.createElement("div");
        wrap.id = "legacy-auth-wrap";
        wrap.style.display = "inline-flex";
        wrap.style.gap = "8px";
        wrap.style.alignItems = "center";
        wrap.style.flexWrap = "wrap";

        // Entrar / Registro (legacy)
        const login = document.createElement("a");
        login.id = "nav-login-link";
        login.href = "/auth/login";
        login.className = "btn btn-secondary";
        login.textContent = "Entrar";

        const reg = document.createElement("a");
        reg.id = "nav-signup-link";
        reg.href = "/auth/register";
        reg.className = "btn";
        reg.textContent = "Registro";

        const acc = document.createElement("a");
        acc.id = "nav-account-link";
        acc.href = "/account";
        acc.className = "btn btn-secondary";
        acc.textContent = "Mi cuenta";
        acc.style.display = "none";

        const out = document.createElement("a");
        out.id = "nav-logout-link";
        out.href = "/auth/logout";
        out.className = "btn btn-secondary";
        out.textContent = "Salir";
        out.style.display = "none";

        wrap.appendChild(login);
        wrap.appendChild(reg);
        wrap.appendChild(acc);
        wrap.appendChild(out);

        topbar.appendChild(wrap);
      }

      return { mode: "legacy" };
    }

    return { mode: "none" };
  }

  // =========================
  // Fetch: usage balance
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

  function applyUsageTextToUI(data) {
    // Tu backend actual (por tus templates) maneja seconds.
    // Si te devuelve minutes, igual lo soportamos.
    let usedMin, allowMin, remainMin;

    if (data && (data.used_seconds != null || data.allowance_seconds != null)) {
      const usedSec = Number(data.used_seconds || 0);
      const allowSec = Number(data.allowance_seconds || 0);
      usedMin = usedSec / 60;
      allowMin = allowSec / 60;
      remainMin = Math.max(0, allowMin - usedMin);
    } else {
      // fallback por si devuelve minutes
      usedMin = Number(data.used_minutes || 0);
      allowMin = Number(data.limit_minutes || data.monthly_limit_minutes || 0);
      remainMin = Math.max(0, Number(data.remaining_minutes || 0));
      if (!allowMin && usedMin + remainMin > 0) allowMin = usedMin + remainMin;
    }

    const txt = `${usedMin.toFixed(1)}/${allowMin.toFixed(0)} min · libre ${remainMin.toFixed(1)} min`;

    const a = document.getElementById("usage-text-nav");
    if (a) a.textContent = txt;

    const b = document.getElementById("usage-text");
    if (b) b.textContent = txt;
  }

  async function refreshUsageUI(userId) {
    if (!userId) return;
    try {
      const data = await fetchUsageBalance(userId);
      applyUsageTextToUI(data);
    } catch (err) {
      // silencioso: no rompemos UI por esto
      console.warn("refreshUsageUI:", err?.message || err);
    }
  }

  function setAuthState(loggedIn) {
    const login = document.getElementById("nav-login-link");
    const signup = document.getElementById("nav-signup-link");
    const account = document.getElementById("nav-account-link");
    const logout = document.getElementById("nav-logout-link");

    if (loggedIn) {
      if (login) login.style.display = "none";
      if (signup) signup.style.display = "none";
      if (account) account.style.display = "";
      if (logout) logout.style.display = "";
    } else {
      if (login) login.style.display = "";
      if (signup) signup.style.display = "";
      if (account) account.style.display = "none";
      if (logout) logout.style.display = "none";
    }
  }

  async function boot() {
    // 1) Garantiza que existan botones (aunque el template haya quedado viejo)
    ensureNavRightUI();

    // 2) Decide sesión real
    const uid = await resolveUserId();
    setAuthState(!!uid);

    // 3) Si hay usuario, refresca saldo
    if (uid) {
      refreshUsageUI(uid);
    }
  }

  document.addEventListener("DOMContentLoaded", boot);

  // Exponemos por si otros scripts lo necesitan
  window.PolyScribeAuth = {
    resolveUserId,
    refreshUsageUI,
  };
})();
