# scripts/doctor.py
import os, sys
from dotenv import load_dotenv

def fail(msg, code=1):
    print(f"[X] {msg}")
    sys.exit(code)

def main():
    load_dotenv()  # carga .env en dev

    required = ["OPENAI_API_KEY", "S3_BUCKET", "AWS_DEFAULT_REGION", "FLASK_SECRET_KEY"]
    ok = True
    for k in required:
        v = os.getenv(k)
        print(f"{k:>20}: {'OK' if v else 'MISSING'}")
        ok &= bool(v)
    if not ok:
        fail("Faltan variables en .env")

    # Comprobar AWS identidad y bucket
    try:
        import boto3
        sts = boto3.client("sts", region_name=os.getenv("AWS_DEFAULT_REGION"))
        who = sts.get_caller_identity()
        print(f"STS identity: Account={who.get('Account')}")
    except Exception as e:
        fail(f"STS error: {e}")

    try:
        s3 = boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION"))
        bucket = os.getenv("S3_BUCKET")
        s3.head_bucket(Bucket=bucket)
        print(f"S3 bucket visible: {bucket}")
    except Exception as e:
        fail(f"S3 error: {e}")

    print("Doctor: OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
