// static/js/payments.js
(function () {
  // ---------- Helpers UI ----------
  function $(id) { return document.getElementById(id); }

  function setBanner(type, msg) {
    const ok = $("banner-ok");
    const warn = $("banner-warn");
    const err = $("banner-err");
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

  // ---------- User ID (anon) ----------
  function getOrCreateUserId() {
    // Intentamos varias keys por compatibilidad
    const keys = ["user_id", "uid", "ps_uid", "ps_user_id", "dev_user_id"];
    for (const k of keys) {
      const v = (localStorage.getItem(k) || "").trim();
      if (v) return v;
    }

    // Creamos uno nuevo (anónimo)
    let id;
    if (window.crypto && crypto.randomUUID) {
      id = "ps_" + crypto.randomUUID();
    } else {
      id = "ps_" + Math.random().toString(16).slice(2) + "_" + Date.now();
    }

    // Guardamos en una key estable para PolyScribe
    localStorage.setItem("ps_user_id", id);
    return id;
  }

  async function getConfig() {
    const r = await fetch("/api/paypal/config", { cache: "no-store" });
    if (!r.ok) throw new Error("paypal_config_failed");
    return r.json();
  }

  async function postCapture(payload, userId) {
    const r = await fetch("/api/paypal/capture", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": userId,
      },
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

  // ---------- Plans ----------
  // IMPORTANTE: que sku/minutes/amount coincidan con lo que pintas en pricing.html
  const PLANS = [
    { sku: "starter_60", minutes: 60, amount: "9.99", currency: "USD", selector: "#paypal-button-starter" },
    { sku: "pro_300", minutes: 300, amount: "19.99", currency: "USD", selector: "#paypal-button-pro" },
    { sku: "business_1200", minutes: 1200, amount: "49.99", currency: "USD", selector: "#paypal-button-business" },
  ];

  async function renderButtons() {
    const cfg = await getConfig();
    if (!cfg.enabled || !cfg.client_id) {
      setBanner("warn", "PayPal no está habilitado o falta Client ID.");
      return;
    }

    const userId = getOrCreateUserId();
    console.log("[payments] userId =", userId);

    // El SDK normalmente se carga en el HTML; aquí solo validamos
    if (!window.paypal || !paypal.Buttons) {
      setBanner("err", "PayPal SDK no cargó (paypal.Buttons no disponible).");
      return;
    }

    setBanner("ok", "PayPal está configurado. Puedes comprar cualquier plan y tu saldo se activará automáticamente después del pago.");

    PLANS.forEach((plan) => {
      const mount = document.querySelector(plan.selector);
      if (!mount) return;

      paypal.Buttons({
        style: { layout: "vertical", label: "paypal" },

        // Creamos la orden del lado del cliente (rápido).
        // Luego verificamos y guardamos en /capture usando PayPal como fuente de verdad.
        createOrder: function (data, actions) {
          return actions.order.create({
            intent: "CAPTURE",
            purchase_units: [{
              reference_id: plan.sku,
              amount: { value: plan.amount, currency_code: plan.currency || (cfg.currency || "USD") },
              custom_id: userId, // útil para trazabilidad
              description: `PolyScribe ${plan.sku} (${plan.minutes} minutes)`
            }]
          });
        },

        onApprove: async function (data, actions) {
          try {
            // Captura en PayPal (esto hace que la orden quede COMPLETED)
            const details = await actions.order.capture();

            // Luego avisamos a nuestro backend para registrar y acreditar
            const result = await postCapture({
              order_id: details.id,
              sku: plan.sku,
              minutes: plan.minutes,
              amount: plan.amount
            }, userId);

            setBanner("ok", `Pago aprobado ✅ Minutos acreditados: ${result.credited_minutes}`);
            console.log("[payments] capture result", result);

            // opcional: refrescar balance si tienes UI que lo muestra
            // location.reload();
          } catch (e) {
            console.error("[payments] PayPal error:", e);
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

  // Init
  renderButtons().catch((e) => {
    console.error("[payments] init failed:", e);
    setBanner("err", "No se pudo inicializar PayPal: " + (e.message || String(e)));
  });
})();
