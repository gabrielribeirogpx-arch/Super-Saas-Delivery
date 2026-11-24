import json
import os
from functools import lru_cache

from app.models.admin_user import AdminUser
from app.models.management_push import ManagementPushDevice

ROLES = {"admin", "owner", "operator", "cashier"}
EFFECT = "management_push.created"


def enabled():
    return os.getenv("MANAGEMENT_PUSH_ENABLED", "").strip().lower() in {"1", "true"}


def devices_for_tenant(db, tenant_id, now):
    return db.query(ManagementPushDevice).join(
        AdminUser, AdminUser.id == ManagementPushDevice.admin_user_id,
    ).filter(
        ManagementPushDevice.tenant_id == tenant_id,
        ManagementPushDevice.expires_at > now,
        AdminUser.tenant_id == tenant_id,
        AdminUser.active.is_(True),
        AdminUser.role.in_(ROLES),
        AdminUser.credential_version == ManagementPushDevice.credential_version,
        AdminUser.email_verification_required.is_(False) | AdminUser.email_verified_at.is_not(None),
    )


@lru_cache(maxsize=1)
def _firebase_app():
    import firebase_admin
    from firebase_admin import credentials

    service_account = os.getenv("MANAGEMENT_PUSH_SERVICE_ACCOUNT_JSON")
    credential = (credentials.Certificate(json.loads(service_account))
                  if service_account else credentials.ApplicationDefault())
    return firebase_admin.initialize_app(credential, {"httpTimeout": 8}, name="management-push")


def send_order_alert(device, order_id):
    from firebase_admin import messaging

    try:
        messaging.send(messaging.Message(
            token=device.token,
            data={"kind": "new_order", "binding": device.binding, "event": str(order_id)},
            android=messaging.AndroidConfig(priority="high", ttl=60),
        ), app=_firebase_app())
    except messaging.UnregisteredError:
        return False
    return True
