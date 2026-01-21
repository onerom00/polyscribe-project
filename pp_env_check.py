import os, base64, requests

BASE = "https://api-m.sandbox.paypal.com"
cid = os.getenv("PAYPAL_CLIENT_ID", "")
sec = os.getenv("PAYPAL_CLIENT_SECRET", "")

print("CID_LEN", len(cid), "HEAD", cid[:6], "TAIL", cid[-4:])
print("SEC_LEN", len(sec), "HEAD", sec[:4], "TAIL", sec[-4:])

if not cid or not sec:
    print("FALTAN variables PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET")
    raise SystemExit(1)

auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
r = requests.post(
    BASE + "/v1/oauth2/token",
    headers={"Authorization": "Basic " + auth, "Accept":"application/json"},
    data={"grant_type":"client_credentials"},
    timeout=30
)
print("STATUS", r.status_code)
print("BODY", r.text[:400])
