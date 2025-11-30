// frontend/src/components/SubscribeButton.jsx
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:5000";

export default function SubscribeButton() {
  const [loading, setLoading] = useState(false);

  async function subscribeBasic() {
    try {
      setLoading(true);
      const r = await fetch(`${API_BASE}/billing/create-checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Si más adelante tienes planes distintos, cambia "basic" por el que toque:
        body: JSON.stringify({ plan: "basic" }),
      });
      const j = await r.json();
      if (j.checkout_url) {
        window.location.href = j.checkout_url;
      } else {
        alert(j.error || "No se pudo iniciar el checkout");
      }
    } catch (err) {
      console.error(err);
      alert("Error de red iniciando el checkout");
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={subscribeBasic}
      disabled={loading}
      className="px-4 py-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-60"
      title="Suscripción plan Básico"
    >
      {loading ? "Redirigiendo…" : "Suscribirme"}
    </button>
  );
}
