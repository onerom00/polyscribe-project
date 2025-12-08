// app/static/js/payments.js
(function () {
  const plans = [
    { id: "pp-60",   minutes: 60,   price: "9.00",  sku: "starter_60"  },
    { id: "pp-300",  minutes: 300,  price: "29.00", sku: "pro_300"     },
    { id: "pp-1200", minutes: 1200, price: "89.00", sku: "biz_1200"    },
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
    let userId = localStorage.getItem("ps_user_id");
    if (!userId) {
      // En tu app real puedes tener /dev-login; aquí solo generamos uno random si falta
      userId = "guest-" + Math.random().toString(36).slice(2);
      localStorage.setItem("ps_user_id", userId);
    }
    return userId;
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
                  reference_id: plan.sku,
                  description: plan.minutes + " minutos PolyScribe (prepago)",
                  amount: { currency_code: "USD", value: plan.price },
                },
              ],
            });
          },
          onApprove: function (data, actions) {
            return actions.order.capture().then(function (details) {
              fetch("/api/paypal/capture", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-User-Id": userId,
                },
                credentials: "same-origin",
                body: JSON.stringify({
                  order_id: details.id,
                  sku: plan.sku,
                  minutes: plan.minutes,
                  amount: plan.price,
                  user_id: userId,
                }),
              }).catch(() => {});

              alert("Pago aprobado. ¡Gracias! Los minutos se abonarán en tu cuenta.");
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
      showAlert("PayPal no está configurado por el momento. Puedes continuar usando el plan Free.");
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
