// app/static/js/payments.js
(function(){
  const plans = [
    { id: "pp-60",   minutes: 60,   price: "9.00",  sku: "starter_60"  },
    { id: "pp-300",  minutes: 300,  price: "29.00", sku: "pro_300"     },
    { id: "pp-1200", minutes: 1200, price: "89.00", sku: "biz_1200"    },
  ];

  const alertBox = document.getElementById("pay-alert");

  function showAlert(msg){
    if (!alertBox) return;
    alertBox.textContent = msg;
    alertBox.style.display = "block";
  }

  async function getConfig(){
    try{
      const r = await fetch("/api/paypal/config");
      if (!r.ok) return null;
      return await r.json();
    }catch(_){ return null; }
  }

  function injectSdk(clientId, currency){
    return new Promise((resolve, reject)=>{
      if (window.paypal) return resolve();
      const s = document.createElement("script");
      s.src =
        "https://www.paypal.com/sdk/js?client-id=" +
        encodeURIComponent(clientId) +
        "&currency=" + (currency || "USD") +
        "&intent=capture";
      s.onload = resolve;
      s.onerror = () => reject(new Error("NO se pudo cargar el SDK de PayPal"));
      document.head.appendChild(s);
    });
  }

  function renderButtons(){
    if (!window.paypal){
      showAlert("SDK de PayPal no disponible.");
      return;
    }

    plans.forEach(plan=>{
      const el = document.getElementById(plan.id);
      if (!el) return;
      el.innerHTML = "";

      window.paypal.Buttons({
        style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },

        createOrder: (data, actions) => {
          return actions.order.create({
            purchase_units: [{
              reference_id: plan.sku,
              description: `${plan.minutes} minutos PolyScribe`,
              amount: { currency_code:"USD", value: plan.price }
            }]
          });
        },

        onApprove: (data, actions) => {
          return actions.order.capture().then(details => {
            fetch("/api/paypal/capture", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                order_id: details.id,
                sku: plan.sku,
                minutes: plan.minutes,
                amount: plan.price
              })
            });

            alert("Pago aprobado. Los minutos serán acreditados.");
          });
        },

        onError: err => {
          console.error("PayPal error:", err);
          showAlert("Hubo un problema al conectar con PayPal. Intenta de nuevo.");
        }
      }).render("#" + plan.id);
    });
  }

  (async function init(){
    const cfg = await getConfig();
    if (!cfg || !cfg.client_id){
      showAlert("PayPal no está configurado.");
      return;
    }

    await injectSdk(cfg.client_id, cfg.currency);
    renderButtons();
  })();
})();
