# app/paypal_sdk.py
from __future__ import annotations

import httpx
from flask import current_app


class PayPalSDK:
    """
    Pequeño wrapper para la API REST de PayPal (suscripciones).
    Usa las credenciales configuradas en current_app.config.
    """

    def __init__(self) -> None:
        cfg = current_app.config
        self.base_url: str = cfg["PAYPAL_BASE_URL"].rstrip("/")
        self.client_id: str = cfg["PAYPAL_CLIENT_ID"]
        self.client_secret: str = cfg["PAYPAL_CLIENT_SECRET"]

    # -------------------------------------------------
    # Utilidades internas
    # -------------------------------------------------
    def _get_access_token(self) -> str:
        url = f"{self.base_url}/v1/oauth2/token"
        resp = httpx.post(
            url,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]

    def _auth_headers(self) -> dict[str, str]:
        token = self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # -------------------------------------------------
    # Suscripciones
    # -------------------------------------------------
    def create_subscription(
        self, *, plan_id: str, return_url: str, cancel_url: str, user_id: str
    ) -> dict:
        """
        Crea una suscripción a un plan de PayPal.
        Devuelve el JSON completo que incluye links[approve].
        """
        url = f"{self.base_url}/v1/billing/subscriptions"

        payload = {
            "plan_id": plan_id,
            "custom_id": user_id,  # <- luego nos llega en el webhook
            "application_context": {
                "brand_name": "PolyScribe",
                "shipping_preference": "NO_SHIPPING",
                "user_action": "SUBSCRIBE_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }

        resp = httpx.post(url, headers=self._auth_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_subscription(self, subscription_id: str) -> dict:
        """
        Trae los datos de una suscripción.
        """
        url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}"
        resp = httpx.get(url, headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()
