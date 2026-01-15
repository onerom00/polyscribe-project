// app/static/js/payments.js
(function () {
  // Definición de planes de prepago
  // Estos valores SON los que se cobran en PayPal
  const plans = [
    { id: "pp-60",   minutes: 60,   price: "9.99",  sku: "starter_60"  },  // Starter
    { id: "pp-300",  minutes: 300,  price: "19.99", sku: "pro_300"     },  // Pro
    { id: "pp-1200", minutes: 1200, price: "49.99", sku: "biz_1200"    },  // Business
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
      return await r.json(); // { enabled, client_id, currency, env }
    } catch (_) {
      return null;
    }
  }

  function injectSdk(clientId, currency) {
    return new Promise((resolve, reject) => {
      if (window.paypal) return resolve();
      const s = document.createElement("script");
      const cur = (currency || "USD").toUpperCase();
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
    // Si tu backend usa sesión real, igual funciona porque el server dará prioridad a session.
    // Esto sirve para custom_id y para modo dev.
    let userId = localStorage.getItem("user_id");
    if (!userId) {
      userId = "guest-" + Math.random().toString(36).slice(2);
      localStorage.setItem("user_id", userId);
    }
    return userId;
  }

  async function postCapture({ userId, orderId, sku, minutes, amount }) {
    const r = await fetch("/api/paypal/capture", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": userId, // útil en dev; en prod el server prioriza session si existe
      },
      credentials: "same-origin",
      body: JSON.stringify({
        order_id: orderId,
        sku,
        minutes,
        amount,
        user_id: userId,
      }),
    });

    let data = null;
    try { data = await r.json(); } catch (_) {}

    if (!r.ok) {
      const msg = (data && data.error) ? data.error : ("HTTP " + r.status);
      throw new Error(msg);
    }
    return data;
  }

  function renderButtons() {
    if (!window.paypal) {
      showAlert("SDK de PayPal no cargado.");
      return;
    }

    const userId = ensureUser();

    plans.forEach((plan) => {
      const el = document.getElementById(plan.id);
      if (!el) return;
      el.innerHTML = "";

      window.paypal
        .Buttons({
          style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },

          createOrder: function (data, actions) {
            return actions.order.create({
              purchase_units: [
                {
                  // ✅ reference_id lo usamos como sku
                  reference_id: plan.sku,

                  // ✅ custom_id lo usamos para mapear user en webhook y server
                  custom_id: userId,

                  description: plan.minutes + " minutos PolyScribe (prepago)",
                  amount: { currency_code: "USD", value: plan.price },
                },
              ],
            });
          },

          onApprove: function (data, actions) {
            return actions.order.capture().then(async function (details) {
              try {
                await postCapture({
                  userId,
                  orderId: details.id,
                  sku: plan.sku,
                  minutes: plan.minutes,
                  amount: plan.price,
                });

                alert("Pago aprobado. ¡Gracias! Los minutos se abonaron a tu cuenta.");
                // Recargar para refrescar balance/minutos en pantalla
                location.reload();
              } catch (err) {
                console.error("Capture backend error:", err);
                showAlert("Pago aprobado, pero falló el registro de minutos: " + err.message);
              }
            });
          },

          onError: function (err) {
            console.error("PayPal error:", err);
            showAlert("Hubo un problema con PayPal. Intenta de nuevo.");
          },
        })
        .render("#" + plan.id);
    });
  }

  (async function init() {
    const cfg = await getConfig();
    if (!cfg || !cfg.enabled || !cfg.client_id) {
      showAlert(
        "PayPal no está configurado por el momento. " +
        "Puedes continuar usando el plan Free."
      );
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
