// static/js/nav_auth.js
(function () {
  "use strict";

  // ==========================================
  // CONFIG: ids esperados en tus templates
  // ==========================================
  const IDS = {
    login: "nav-login-link",
    signup: "nav-signup-link",
    account: "nav-account-link",
    logout: "nav-logout-link",
    usageBadgeNav: "usage-badge-nav",
    usageTextNav: "usage-text-nav",
  };

  // ==========================================
  // Helpers: storage
  // ==========================================
  function lsGet(key) {
    try {
      const v = localStorage.getItem(key);
      return v ? String(v).trim() : "";
    } catch {
      return "";
    }
  }

  function lsSet(key, value) {
    try {
      localStorage.setItem(key, String(value));
    } catch {}
  }

  function lsDel(key) {
    try {
      localStorage.removeItem(key);
    } catch {}
  }

  // ==========================================
  // USER ID resolve (solo como fallback)
  // data-user-id -> ?user_id -> localStorage
  // ==========================================
  function getUserIdFromDOM() {
    const uid = (document.body?.dataset?.userId || "").trim();
    return uid || "";
  }

  function getUserIdFromQuery() {
    try {
      const qs = new URLSearchParams(window.location.search);
      return (qs.get("user_id") || "").trim();
    } catch {
      return "";
    }
  }

  function resolveUserIdFallback() {
    let id = getUserIdFromDOM();
    const q = getUserIdFromQuery();
    if (q) id = q;
    if (!id) id = lsGet("user_id");
    if (id) lsSet("user_id", id);
    return id;
  }

  // ==========================================
  // Fuente REAL: backend session
  // ==========================================
  async function whoAmI() {
    // Si el endpoint no existe o falla, devolvemos "" (guest)
    try {
      const r = await fetch("/api/usage/whoami", { credentials: "same-origin" });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j && j.user_id) {
        const id = String(j.user_id).trim();
        if (id) {
          lsSet("user_id", id);
          return id;
        }
      }
      return "";
    } catch {
      return "";
    }
  }

  // ==========================================
  // UI toggles
  // ==========================================
  function el(id) {
    return document.getElementById(id);
  }

  function show(node, visible) {
    if (!node) return;
    node.style.display = visible ? "" : "none";
  }

  function setText(node, text) {
    if (!node) return;
    node.textContent = text;
  }

  function bindLogoutCleanup(userId) {
    const logout = el(IDS.logout);
    if (!logout) return;

    // Evita doble binding
    if (logout.dataset.bound === "1") return;
    logout.dataset.bound = "1";

    logout.addEventListener("click", () => {
      // Limpieza fuerte del estado “pegado”
      lsDel("user_id");
      lsDel("ps_last_job_id");

      // (Opcional) si guardas otros keys, límpialos aquí
      // lsDel("ps_lang");
    });
  }

  function applyAuthUI(isLogged, userId) {
    const login = el(IDS.login);
    const signup = el(IDS.signup);
    const account = el(IDS.account);
    const logout = el(IDS.logout);

    // Guest -> mostrar Entrar/Registro
    show(login, !isLogged);
    show(signup, !isLogged);

    // Logged -> mostrar Mi cuenta/Salir
    show(account, isLogged);
    show(logout, isLogged);

    if (isLogged) bindLogoutCleanup(userId);
  }

  // ==========================================
  // Usage badge (nav) usando tu formato REAL:
  // used_seconds / allowance_seconds
  // ==========================================
  async function fetchUsageBalance(userId) {
    const url = `/api/usage/balance?user_id=${encodeURIComponent(userId)}`;
    const r = await fetch(url, {
      method: "GET",
      headers: { "X-User-Id": userId },
      credentials: "same-origin",
    });

    if (!r.ok) {
      return null;
    }

    const j = await r.json().catch(() => null);
    return j || null;
  }

  function renderUsageBadgeNav(data) {
    const badge = el(IDS.usageBadgeNav);
    const text = el(IDS.usageTextNav);

    if (!badge || !text) return;

    if (!data) {
      // si no hay data, lo dejamos pero visible
      setText(text, "—/— min · libre —");
      return;
    }

    const usedSec = Number(data.used_seconds || 0);
    const allowSec = Number(data.allowance_seconds || 0);

    const usedMin = usedSec / 60;
    const allowMin = allowSec / 60;
    const remain = Math.max(0, allowMin - usedMin);

    setText(text, `${usedMin.toFixed(1)}/${allowMin.toFixed(0)} min · libre ${remain.toFixed(1)} min`);
  }

  // ==========================================
  // Boot
  // ==========================================
  async function boot() {
    // 1) primero intentamos sesión real
    let userId = await whoAmI();

    // 2) si no hay sesión real, NO asumimos localStorage como login
    //    (pero lo dejamos como fallback para compatibilidad vieja)
    if (!userId) {
      // Si quieres ser ESTRICTO 100% backend, comenta la línea de abajo:
      // userId = ""; // guest siempre si whoami no da user
      //
      // Compatibilidad: si ya estabas usando user_id param/localStorage en modo dev:
      userId = resolveUserIdFallback();
    }

    const isLogged = !!userId;

    applyAuthUI(isLogged, userId);

    // Badge solo si hay user_id
    if (isLogged) {
      const usage = await fetchUsageBalance(userId);
      renderUsageBadgeNav(usage);
    } else {
      renderUsageBadgeNav(null);
    }
  }

  document.addEventListener("DOMContentLoaded", boot);

  // Exponer helpers mínimos
  window.PolyScribeAuth = {
    boot,
  };
})();
