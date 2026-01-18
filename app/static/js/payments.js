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

  async function getConfig() {
    try {
      const r = await fetch("/api/paypal/config", { credentials: "same-origin" });
      if (!r.ok) return null;
      return await r.json();
    } catch (_) {
      return null;
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

  function ensureUser() {
    let userId = localStorage.getItem("user_id");
    if (!userId) {
      userId = "guest-" + Math.random().toString(36).slice(2);
      localStorage.setItem("user_id", userId);
    }
    return userId;
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
    if (!r.ok || !j.ok) throw new Error(j.error || "capture_failed");
    return j;
  }

  function renderButtons() {
    if (!window.paypal) {
      showAlert("SDK de PayPal no cargado.");
      return;
    }

    const userId = ensureUser();

    plans.forEach(({ elId, planKey }) => {
      const el = document.getElementById(elId);
      if (!el) return;
      el.innerHTML = "";

      window.paypal
        .Buttons({
          style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },

          createOrder: function () {
            return apiCreateOrder(planKey, userId);
          },

          onApprove: function (data) {
            return apiCaptureOrder(data.orderID, userId)
              .then(() => {
                alert("Pago aprobado. ¡Gracias! Tus minutos fueron acreditados.");
                window.location.reload();
              })
              .catch((err) => {
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
      renderButtons();
    } catch (err) {
      console.error(err);
      showAlert("No se pudo cargar el SDK de PayPal. Intenta más tarde.");
    }
  })();
})();
