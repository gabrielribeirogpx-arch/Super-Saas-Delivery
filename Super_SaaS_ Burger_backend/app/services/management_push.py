import json
import os
from functools import lru_cache
from logging import getLogger

from app.models.admin_user import AdminUser
from app.models.management_push import ManagementPushDevice

ROLES = {"admin", "owner", "operator", "cashier"}
EFFECT = "management_push.created"
logger = getLogger(__name__)

_PROVIDER_CODES = {
    "INVALID_ARGUMENT", "PERMISSION_DENIED", "UNAUTHENTICATED",
    "RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED",
    "INTERNAL", "NOT_FOUND", "FAILED_PRECONDITION",
}


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
        app = _firebase_app()
    except Exception:
        logger.warning("management_push_fcm_error reason=credential_configuration")
        raise

    try:
        messaging.send(messaging.Message(
            token=device.token,
            data={"kind": "new_order", "binding": device.binding, "event": str(order_id)},
            android=messaging.AndroidConfig(priority="high", ttl=60),
        ), app=app)
    except messaging.UnregisteredError:
        return False
    except Exception as exc:
        # Provider exception text can include request data or credential details.
        from firebase_admin import exceptions
        from google.auth.exceptions import GoogleAuthError

        if isinstance(exc, messaging.SenderIdMismatchError):
            reason = "sender_id_mismatch"
        elif isinstance(exc, GoogleAuthError):
            reason = "credential_authentication"
        elif isinstance(exc, exceptions.FirebaseError) and exc.code in _PROVIDER_CODES:
            reason = exc.code.lower()
        else:
            reason = "unknown"
        logger.warning("management_push_fcm_error reason=%s", reason)
        raise
    return True
