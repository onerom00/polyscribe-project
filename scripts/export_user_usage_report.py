# scripts/export_user_usage_report.py
from __future__ import annotations

import csv
import os
from datetime import datetime
from collections import defaultdict
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def _safe_float(value, default=0.0) -> float:
    try:
        return float(value or 0)
    except Exception:
        return default


def _safe_int(value, default=0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _minutes(seconds) -> float:
    try:
        return round(float(seconds or 0) / 60.0, 2)
    except Exception:
        return 0.0


def _get_free_tier_minutes(app) -> int:
    raw = os.getenv("FREE_TIER_MINUTES", app.config.get("FREE_TIER_MINUTES", 5))
    try:
        return int(raw or 5)
    except Exception:
        return 5


def _segment_user(
    *,
    is_verified: bool,
    jobs_done: int,
    minutes_consumed: float,
    remaining_minutes: float,
    paid_minutes: int,
    amount_paid_usd: float,
) -> str:
    if amount_paid_usd > 0 or paid_minutes > 0:
        return "paid_customer"

    if not is_verified:
        return "registered_not_verified"

    if jobs_done <= 0 or minutes_consumed <= 0:
        return "verified_no_usage"

    if remaining_minutes <= 0:
        return "free_minutes_exhausted"

    if remaining_minutes <= 1:
        return "hot_lead_low_balance"

    if minutes_consumed >= 3:
        return "engaged_free_user"

    if minutes_consumed > 0:
        return "trial_user"

    return "unknown"


def main() -> None:
    """
    Exporta un reporte CSV de consumo por usuario.

    Usa los modelos actuales:
    - app.models_user.User
    - app.models.AudioJob
    - app.models_payment.Payment

    El reporte se guarda en:
    reports/user_usage_report_YYYYMMDD_HHMMSS.csv
    """
    try:
        from app import create_app
    except Exception as e:
        raise RuntimeError(
            "No pude importar create_app desde app. "
            "Si tu proyecto usa otra forma de crear la app Flask, "
            "pásame el contenido de app/__init__.py para adaptarlo."
        ) from e

    from app.extensions import db
    from app.models_user import User
    from app.models import AudioJob
    from app.models_payment import Payment

    app = create_app()

    with app.app_context():
        free_minutes = _get_free_tier_minutes(app)

        users = db.session.query(User).order_by(User.created_at.asc()).all()
        jobs = db.session.query(AudioJob).all()
        payments = db.session.query(Payment).all()

        jobs_by_user = defaultdict(list)
        for job in jobs:
            jobs_by_user[str(job.user_id)].append(job)

        payments_by_user = defaultdict(list)
        for payment in payments:
            payments_by_user[str(payment.user_id)].append(payment)

        rows = []

        for user in users:
            uid = str(user.id)
            user_jobs = jobs_by_user.get(uid, [])
            user_payments = payments_by_user.get(uid, [])

            jobs_total = len(user_jobs)
            jobs_done = sum(1 for j in user_jobs if (j.status or "").lower() == "done")
            jobs_error = sum(1 for j in user_jobs if (j.status or "").lower() == "error")
            jobs_other = jobs_total - jobs_done - jobs_error

            consumed_seconds = sum(
                float(j.duration_seconds or 0)
                for j in user_jobs
                if (j.status or "").lower() == "done"
            )
            minutes_consumed = _minutes(consumed_seconds)

            captured_payments = [
                p for p in user_payments
                if (p.status or "").lower() == "captured"
            ]

            paid_minutes = sum(_safe_int(p.minutes) for p in captured_payments)
            amount_paid_usd = round(
                sum(_safe_float(p.amount_usd) for p in captured_payments),
                2,
            )

            allowance_minutes = free_minutes + paid_minutes
            remaining_minutes = round(max(0.0, allowance_minutes - minutes_consumed), 2)

            last_job_at = None
            if user_jobs:
                valid_dates = [j.created_at for j in user_jobs if j.created_at]
                if valid_dates:
                    last_job_at = max(valid_dates)

            is_verified = bool(getattr(user, "is_verified", False))
            is_active = bool(getattr(user, "is_active", True))

            segment = _segment_user(
                is_verified=is_verified,
                jobs_done=jobs_done,
                minutes_consumed=minutes_consumed,
                remaining_minutes=remaining_minutes,
                paid_minutes=paid_minutes,
                amount_paid_usd=amount_paid_usd,
            )

            rows.append(
                {
                    "user_id": user.id,
                    "email": user.email or "",
                    "display_name": user.display_name or "",
                    "verified": "yes" if is_verified else "no",
                    "active": "yes" if is_active else "no",
                    "created_at": user.created_at.isoformat() if user.created_at else "",
                    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else "",
                    "plan_tier": user.plan_tier or "free",
                    "jobs_total": jobs_total,
                    "jobs_done": jobs_done,
                    "jobs_error": jobs_error,
                    "jobs_other": jobs_other,
                    "minutes_consumed": minutes_consumed,
                    "free_minutes": free_minutes,
                    "paid_minutes": paid_minutes,
                    "allowance_minutes": allowance_minutes,
                    "remaining_minutes": remaining_minutes,
                    "payments_total": len(user_payments),
                    "payments_captured": len(captured_payments),
                    "amount_paid_usd": amount_paid_usd,
                    "last_job_at": last_job_at.isoformat() if last_job_at else "",
                    "segment": segment,
                }
            )

        rows.sort(
            key=lambda r: (
                r["amount_paid_usd"],
                r["minutes_consumed"],
                r["jobs_done"],
            ),
            reverse=True,
        )

        os.makedirs("reports", exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join("reports", f"user_usage_report_{stamp}.csv")

        fieldnames = [
            "user_id",
            "email",
            "display_name",
            "verified",
            "active",
            "created_at",
            "last_login_at",
            "plan_tier",
            "jobs_total",
            "jobs_done",
            "jobs_error",
            "jobs_other",
            "minutes_consumed",
            "free_minutes",
            "paid_minutes",
            "allowance_minutes",
            "remaining_minutes",
            "payments_total",
            "payments_captured",
            "amount_paid_usd",
            "last_job_at",
            "segment",
        ]

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        total_users = len(rows)
        verified_users = sum(1 for r in rows if r["verified"] == "yes")
        users_with_usage = sum(1 for r in rows if float(r["minutes_consumed"]) > 0)
        exhausted_users = sum(1 for r in rows if r["segment"] == "free_minutes_exhausted")
        hot_leads = sum(1 for r in rows if r["segment"] == "hot_lead_low_balance")
        paid_customers = sum(1 for r in rows if r["segment"] == "paid_customer")
        total_minutes = round(sum(float(r["minutes_consumed"]) for r in rows), 2)
        total_revenue = round(sum(float(r["amount_paid_usd"]) for r in rows), 2)

        print("")
        print("PolyScribe User Usage Report")
        print("-" * 36)
        print(f"Output file: {output_path}")
        print(f"Total users: {total_users}")
        print(f"Verified users: {verified_users}")
        print(f"Users with usage: {users_with_usage}")
        print(f"Total consumed minutes: {total_minutes}")
        print(f"Free tier minutes: {free_minutes}")
        print(f"Hot leads low balance: {hot_leads}")
        print(f"Free minutes exhausted: {exhausted_users}")
        print(f"Paid customers: {paid_customers}")
        print(f"Total revenue USD: {total_revenue}")
        print("")


if __name__ == "__main__":
    main()