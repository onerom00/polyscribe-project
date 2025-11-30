import json
import httpx
from flask import current_app

class PayPalError(Exception):
    pass

def _base():
    return current_app.config['PAYPAL_BASE_URL']

def get_paypal_access_token():
    cid = current_app.config['PAYPAL_CLIENT_ID']
    sec = current_app.config['PAYPAL_SECRET']
    if not (cid and sec):
        raise PayPalError("Faltan PAYPAL_CLIENT_ID/PAYPAL_SECRET")
    r = httpx.post(
        f"{_base()}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        auth=(cid, sec),
        timeout=20.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]

def get_subscription(sub_id: str):
    token = get_paypal_access_token()
    r = httpx.get(
        f"{_base()}/v1/billing/subscriptions/{sub_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    r.raise_for_status()
    return r.json()

def verify_webhook_signature(raw_body: bytes, headers: dict) -> bool:
    token = get_paypal_access_token()
    payload = {
        "transmission_id": headers.get("PayPal-Transmission-Id"),
        "transmission_time": headers.get("PayPal-Transmission-Time"),
        "cert_url": headers.get("PayPal-Cert-Url"),
        "auth_algo": headers.get("PayPal-Auth-Algo"),
        "transmission_sig": headers.get("PayPal-Transmission-Sig"),
        "webhook_id": current_app.config["PAYPAL_WEBHOOK_ID"],
        "webhook_event": json.loads(raw_body.decode("utf-8")),
    }
    r = httpx.post(
        f"{_base()}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=20.0,
    )
    r.raise_for_status()
    return r.json().get("verification_status") == "SUCCESS"
