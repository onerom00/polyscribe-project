# app/paypal_client.py
from __future__ import annotations

import base64
from typing import Dict, Any, Optional

import httpx
from flask import current_app


class PayPalError(RuntimeError):
    pass


class PayPalClient:
    """
    Cliente sencillo para la API REST de PayPal (v1 OAuth2 + Subscriptions).
    Usa configuración desde current_app.config.
    """

    def __init__(self) -> None:
        cfg = current_app.config
        self.base_url: str = cfg.get("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
        self.client_id: str = cfg["PAYPAL_CLIENT_ID"]
        self.client_secret: str = cfg["PAYPAL_CLIENT_SECRET"]
        self.skip_verify: bool = cfg.get("PAYPAL_SKIP_VERIFY", False)

    # ───────────────────────────────
    # TOKEN
    # ───────────────────────────────
    def _get_access_token(self) -> str:
        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")

        data = {"grant_type": "client_credentials"}

        with httpx.Client(verify=not self.skip_verify) as client:
            resp = client.post(
                f"{self.base_url}/v1/oauth2/token",
                data=data,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

        if resp.status_code >= 400:
            raise PayPalError(
                f"Error obteniendo token PayPal: {resp.status_code} {resp.text}"
            )

        token = resp.json().get("access_token")
        if not token:
            raise PayPalError("No se recibió access_token desde PayPal")

        return token

    # ───────────────────────────────
    # SUBSCRIPTION
    # ───────────────────────────────
    def create_subscription(
        self,
        plan_id: str,
        custom_id: str,
        return_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """
        Crea una suscripción y devuelve el JSON completo.
        El frontend debe redirigir al enlace "approve" devuelto.
        """
        access_token = self._get_access_token()

        payload = {
            "plan_id": plan_id,
            "custom_id": custom_id,
            "application_context": {
                "brand_name": "PolyScribe",
                "locale": "es-ES",
                "shipping_preference": "NO_SHIPPING",
                "user_action": "SUBSCRIBE_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }

        with httpx.Client(verify=not self.skip_verify) as client:
            resp = client.post(
                f"{self.base_url}/v1/billing/subscriptions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code >= 400:
            raise PayPalError(
                f"Error creando suscripción: {resp.status_code} {resp.text}"
            )

        return resp.json()

    # (Opcional) obtención de detalles de suscripción
    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        access_token = self._get_access_token()

        with httpx.Client(verify=not self.skip_verify) as client:
            resp = client.get(
                f"{self.base_url}/v1/billing/subscriptions/{subscription_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if resp.status_code >= 400:
            raise PayPalError(
                f"Error obteniendo suscripción: {resp.status_code} {resp.text}"
            )

        return resp.json()
