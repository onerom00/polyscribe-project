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

  function hideAlert() {
    if (!alertBox) return;
    alertBox.style.display = "none";
    alertBox.textContent = "";
  }

  function track(eventName, params) {
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", eventName, params || {});
      }
    } catch (_) {}
  }

  function isGuestUserId(uid) {
    const u = String(uid || "").trim().toLowerCase();
    return (
      !u ||
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

  // ============================
  // USER ID (alineado con Opción B)
  // body[data-user-id] -> ?user_id -> localStorage
  // NO forzamos "guest"
  // ============================
  function resolveUserIdFromFront() {
    let id = (document.body?.dataset?.userId || "").trim();

    const qs = new URLSearchParams(window.location.search);
    const qUser = (qs.get("user_id") || "").trim();
    if (qUser) id = qUser;

    if (!id) {
      try {
        id = (localStorage.getItem("user_id") || "").trim();
      } catch (_) {
        id = "";
      }
    }

    if (id) {
      try {
        localStorage.setItem("user_id", id);
      } catch (_) {}
    }

    return id;
  }

  async function getBackendUserId() {
    // Preferimos backend (sesión real). Si falla, fallback al front.
    try {
      const r = await fetch("/api/usage/whoami", { credentials: "same-origin" });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j && j.user_id) return String(j.user_id);
    } catch (_) {}

    return resolveUserIdFromFront();
  }

  function injectSdk(clientId, currency) {
    return new Promise((resolve, reject) => {
      if (window.paypal) return resolve();

      const cur = (currency || "USD").toUpperCase();
      const s = document.createElement("script");
      s.src =
        "https://www.paypal.com/sdk/js?client-id=" +
        encodeURIComponent(String(clientId).trim()) +
        "&currency=" +
        encodeURIComponent(cur) +
        "&intent=capture&enable-funding=card";

      s.onload = () => resolve();
      s.onerror = () => reject(new Error("No se pudo cargar el SDK de PayPal"));
      document.head.appendChild(s);
    });
  }

  function clearPayContainers() {
    plans.forEach(({ elId }) => {
      const el = document.getElementById(elId);
      if (el) el.innerHTML = "";
    });
  }

  function goLogin() {
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

    // Backend debe retornar { ok:true, status:"COMPLETED", ... }
    if (!r.ok || !j || !j.ok) throw new Error(j.error || "capture_failed");
    return j;
  }

  function requireCompletedStatus(captureResp) {
    // SOLO consideramos venta final cuando status es COMPLETED
    const s = String(
      (captureResp && (captureResp.status || captureResp.paypal_status)) || ""
    )
      .trim()
      .toUpperCase();

    if (!s) {
      // fallback seguro si backend no manda status
      return { ok: true, status: "UNKNOWN" };
    }
    return { ok: s === "COMPLETED", status: s };
  }

  async function renderButtons() {
    if (!window.paypal) {
      showAlert("SDK de PayPal no cargado.");
      return;
    }

    const userId = await getBackendUserId();

    // ✅ No renderizar PayPal si no hay login real
    if (isGuestUserId(userId)) {
      clearPayContainers();
      showAlert("🔒 Para comprar minutos debes iniciar sesión.");
      track("paywall_guest_blocked", { page: "pricing" });
      // No redirección agresiva: el pricing ya muestra CTA “Entrar/Registro”
      return;
    }

    hideAlert();

    plans.forEach(({ elId, planKey }) => {
      const el = document.getElementById(elId);
      if (!el) return;
      el.innerHTML = "";

      const priceAttr = el.getAttribute("data-price") || "";
      const minutesAttr = el.getAttribute("data-minutes") || "";

      window.paypal
        .Buttons({
          style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },

          createOrder: function () {
            track("begin_checkout", {
              method: "paypal",
              plan: planKey,
              price: priceAttr,
              minutes: minutesAttr,
            });

            return apiCreateOrder(planKey, userId).catch((err) => {
              if (String(err.message) === "login_required") {
                showAlert("Debes iniciar sesión para comprar.");
                track("paypal_login_required", { at: "createOrder", plan: planKey });
                goLogin();
                return;
              }
              track("paypal_create_order_error", {
                plan: planKey,
                message: String(err.message || err),
              });
              throw err;
            });
          },

          onApprove: function (data) {
            return apiCaptureOrder(data.orderID, userId)
              .then((resp) => {
                const check = requireCompletedStatus(resp);

                if (!check.ok) {
                  track("paypal_not_completed", {
                    plan: planKey,
                    status: check.status,
                    orderID: String(data.orderID || ""),
                  });
                  showAlert(
                    "Pago aprobado pero aún no está COMPLETADO. Si no se refleja en 2 minutos, contacta soporte."
                  );
                  window.location.href = "/history?paid=1";
                  return;
                }

                track("purchase", {
                  method: "paypal",
                  plan: planKey,
                  price: priceAttr,
                  minutes: minutesAttr,
                  orderID: String(data.orderID || ""),
                  status: check.status,
                });

                window.location.href = "/history?paid=1";
              })
              .catch((err) => {
                if (String(err.message) === "login_required") {
                  showAlert("Debes iniciar sesión para comprar.");
                  track("paypal_login_required", { at: "onApprove", plan: planKey });
                  goLogin();
                  return;
                }
                console.error("capture error:", err);
                track("paypal_capture_error", {
                  plan: planKey,
                  message: String(err.message || err),
                });
                showAlert("Pago aprobado pero no se pudo acreditar. Contacta soporte.");
              });
          },

          onError: function (err) {
            console.error("PayPal error:", err);
            track("paypal_sdk_error", {
              message: String(err && err.message ? err.message : err),
            });
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
      track("paypal_disabled", { page: "pricing" });
      clearPayContainers();
      return;
    }

    try {
      await injectSdk(cfg.client_id, cfg.currency);
      await renderButtons();
    } catch (err) {
      console.error(err);
      track("paypal_sdk_load_failed", {
        message: String(err && err.message ? err.message : err),
      });
      showAlert("No se pudo cargar el SDK de PayPal. Intenta más tarde.");
      clearPayContainers();
    }
  })();
})();
