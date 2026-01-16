// static/js/payments.js
(function () {
  function setBanner(type, msg) {
    const ok = document.getElementById("banner-ok");
    const warn = document.getElementById("banner-warn");
    const err = document.getElementById("banner-err");
    if (ok) ok.style.display = "none";
    if (warn) warn.style.display = "none";
    if (err) err.style.display = "none";

    const map = { ok, warn, err };
    const el = map[type];
    if (el) {
      el.textContent = msg;
      el.style.display = "block";
    }
  }

  function getOrCreateUserId() {
    const keys = ["ps_user_id", "user_id", "uid", "ps_uid", "dev_user_id"];
    for (const k of keys) {
      const v = (localStorage.getItem(k) || "").trim();
      if (v) return v;
    }
    let id;
    if (window.crypto && crypto.randomUUID) id = "ps_" + crypto.randomUUID();
    else id = "ps_" + Math.random().toString(16).slice(2) + "_" + Date.now();
    localStorage.setItem("ps_user_id", id);
    return id;
  }

  async function postCapture(payload, userId) {
    const r = await fetch("/api/paypal/capture", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-User-Id": userId },
      body: JSON.stringify({ ...payload, user_id: userId }),
    });

    let data = null;
    try { data = await r.json(); } catch (e) {}

    if (!r.ok) {
      const err = (data && (data.error || data.message)) || ("http_" + r.status);
      throw new Error(err);
    }
    return data;
  }

  const PLANS = [
    { sku: "starter_60", minutes: 60, amount: "9.99", currency: "USD", selector: "#paypal-button-starter" },
    { sku: "pro_300", minutes: 300, amount: "19.99", currency: "USD", selector: "#paypal-button-pro" },
    { sku: "business_1200", minutes: 1200, amount: "49.99", currency: "USD", selector: "#paypal-button-business" },
  ];

  function ensureMountsExist() {
    // Si por error no están en el HTML, al menos dejamos un aviso claro
    let missing = 0;
    PLANS.forEach(p => { if (!document.querySelector(p.selector)) missing++; });
    if (missing) {
      setBanner("err", "Faltan contenedores de PayPal en pricing.html (paypal-button-starter/pro/business).");
      return false;
    }
    return true;
  }

  function renderButtons() {
    if (!window.paypal || !paypal.Buttons) {
      setBanner("err", "PayPal SDK no está disponible (paypal.Buttons).");
      return;
    }

    if (!ensureMountsExist()) return;

    const userId = getOrCreateUserId();
    console.log("[payments] userId =", userId);

    setBanner("ok", "PayPal está configurado. Puedes comprar cualquier plan y tu saldo se activará automáticamente después del pago.");

    PLANS.forEach((plan) => {
      const mount = document.querySelector(plan.selector);
      if (!mount) return;

      // Limpia el contenedor por si hay re-render
      mount.innerHTML = "";

      paypal.Buttons({
        style: { layout: "vertical", label: "paypal" },

        createOrder: function (data, actions) {
          return actions.order.create({
            intent: "CAPTURE",
            purchase_units: [{
              reference_id: plan.sku,
              amount: { value: plan.amount, currency_code: plan.currency },
              custom_id: userId,
              description: `PolyScribe ${plan.sku} (${plan.minutes} minutes)`
            }]
          });
        },

        onApprove: async function (data, actions) {
          try {
            const details = await actions.order.capture();

            const result = await postCapture({
              order_id: details.id,
              sku: plan.sku,
              minutes: plan.minutes,
              amount: plan.amount
            }, userId);

            setBanner("ok", `Pago aprobado ✅ Minutos acreditados: ${result.credited_minutes}`);
            console.log("[payments] capture result", result);
          } catch (e) {
            console.error("[payments] capture error:", e);
            setBanner("warn", `Pago aprobado, pero falló el registro de minutos: ${String(e.message || e)}`);
          }
        },

        onError: function (err) {
          console.error("[payments] onError:", err);
          setBanner("err", "Error de PayPal: " + (err && err.message ? err.message : String(err)));
        }
      }).render(mount);
    });
  }

  try {
    renderButtons();
  } catch (e) {
    console.error("[payments] fatal:", e);
    setBanner("err", "No se pudieron renderizar los botones: " + (e.message || String(e)));
  }
})();
