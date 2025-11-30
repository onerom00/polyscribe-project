# test_paypal_oauth.py
import os, json, requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def base():
    return "https://api-m.paypal.com" if (os.getenv("PAYPAL_ENV","sandbox").lower() == "live") else "https://api-m.sandbox.paypal.com"

cid = os.getenv("PAYPAL_CLIENT_ID")
sec = os.getenv("PAYPAL_SECRET") or os.getenv("PAYPAL_CLIENT_SECRET")
env = os.getenv("PAYPAL_ENV", "sandbox")

print("ENV:", env)
print("CLIENT_ID:", (cid[:6] + "…" + cid[-6:]) if cid else None)
print("SECRET:   ", (sec[:4] + "…" + sec[-4:]) if sec else None)
print("BASE:", base())

if not cid or not sec:
    print("❌ Faltan PAYPAL_CLIENT_ID o PAYPAL_SECRET / PAYPAL_CLIENT_SECRET")
    raise SystemExit(1)

r = requests.post(
    f"{base()}/v1/oauth2/token",
    data={"grant_type":"client_credentials"},
    auth=(cid, sec),
    headers={"Accept":"application/json","Accept-Language":"en_US"},
    timeout=20,
)
print("STATUS:", r.status_code)
try:
    data = r.json()
except Exception:
    data = r.text
print("BODY:", json.dumps(data, indent=2)[:800] if isinstance(data, dict) else str(data)[:800])

