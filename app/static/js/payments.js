// static/js/payments.js
(function () {
  const plans = [
    { elId: "pp-60", planKey: "starter" },
    { elId: "pp-300", planKey: "pro" },
    { elId: "pp-1200", planKey: "business" },
  ];

  const alertBox = document.getElementById("pay-alert");

  function showAlert(msg) {
    if (!alertBox) return;
    alertBox.textContent = msg;
    alertBox.style.display = "block";
  }

  function isGuestUserId(uid) {
    const u = String(uid || "").trim().toLowerCase();
    return (
      u === "guest" ||
      u.startsWith("guest-") ||
      u === "id-guest" ||
      u.startsWith("id-guest-")
    );
  }

  async function getConfig() {
    try {
      const r = await fetch("/api/paypal/config", { credentials: "same-origin" });
      if (!r.ok) return null;
      return await r.json();
    } catch (_) {
      return null;
    }
  }

  async function getBackendUserId() {
    try {
      const r = await fetch("/api/usage/whoami", { credentials: "same-origin" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.user_id) return "guest";
      return String(j.user_id);
    } catch (_) {
      return "guest";
    }
  }

  function injectSdk(clientId, currency) {
    return new Promise((resolve, reject) => {
      if (window.paypal) return resolve();

      const cur = (currency || "USD").toUpperCase();
      const s = document.createElement("script");
      s.src =
        "https://www.paypal.com/sdk/js?client-id=" +
        encodeURIComponent(clientId) +
        "&currency=" +
        cur +
        "&intent=capture&enable-funding=card";

      s.onload = () => resolve();
      s.onerror = () => reject(new Error("No se pudo cargar el SDK de PayPal"));
      document.head.appendChild(s);
    });
  }

  function goLogin() {
    // Ajusta esta ruta si tu login vive en otro endpoint
    window.location.href = "/auth/login";
  }

  async function apiCreateOrder(planKey, userId) {
    const r = await fetch("/api/paypal/create-order", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": userId,
      },
      credentials: "same-origin",
      body: JSON.stringify({ plan: planKey, user_id: userId }),
    });

    const j = await r.json().catch(() => ({}));

    if (r.status === 401 && j && j.error === "login_required") {
      throw new Error("login_required");
    }

    if (!r.ok || !j.orderID) throw new Error(j.error || "create_order_failed");
    return j.orderID;
  }

  async function apiCaptureOrder(orderID, userId) {
    const r = await fetch("/api/paypal/capture-order", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": userId,
      },
      credentials: "same-origin",
      body: JSON.stringify({ orderID, user_id: userId }),
    });

    const j = await r.json().catch(() => ({}));

    if (r.status === 401 && j && j.error === "login_required") {
      throw new Error("login_required");
    }

    if (!r.ok || !j.ok) throw new Error(j.error || "capture_failed");
    return j;
  }

  async function renderButtons() {
    if (!window.paypal) {
      showAlert("SDK de PayPal no cargado.");
      return;
    }

    const userId = await getBackendUserId();

    // ✅ 1) Ocultar guest en producción: no renderizar PayPal si no hay login
    if (isGuestUserId(userId)) {
      showAlert("Para comprar minutos debes iniciar sesión. Luego vuelve a Planes y Precios.");
      // Limpia contenedores de botones para que no quede UI rara
      plans.forEach(({ elId }) => {
        const el = document.getElementById(elId);
        if (el) el.innerHTML = "";
      });
      return;
    }

    plans.forEach(({ elId, planKey }) => {
      const el = document.getElementById(elId);
      if (!el) return;
      el.innerHTML = "";

      window.paypal
        .Buttons({
          style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },

          createOrder: function () {
            return apiCreateOrder(planKey, userId).catch((err) => {
              if (String(err.message) === "login_required") {
                showAlert("Debes iniciar sesión para comprar.");
                goLogin();
                return;
              }
              throw err;
            });
          },

          onApprove: function (data) {
            return apiCaptureOrder(data.orderID, userId)
              .then(() => {
                // ✅ 3) Post-pago: redirigir a /history y refrescar balance
                window.location.href = "/history?paid=1";
              })
              .catch((err) => {
                if (String(err.message) === "login_required") {
                  showAlert("Debes iniciar sesión para comprar.");
                  goLogin();
                  return;
                }
                console.error("capture error:", err);
                showAlert("Pago aprobado pero no se pudo acreditar. Contacta soporte.");
              });
          },

          onError: function (err) {
            console.error("PayPal error:", err);
            showAlert("Hubo un problema con PayPal. Intenta de nuevo.");
          },
        })
        .render("#" + elId);
    });
  }

  (async function init() {
    const cfg = await getConfig();
    if (!cfg || !cfg.enabled || !cfg.client_id) {
      showAlert("PayPal no está configurado por el momento. Puedes continuar con el plan Free.");
      return;
    }

    try {
      await injectSdk(cfg.client_id, cfg.currency);
      await renderButtons();
    } catch (err) {
      console.error(err);
      showAlert("No se pudo cargar el SDK de PayPal. Intenta más tarde.");
    }
  })();
})();
