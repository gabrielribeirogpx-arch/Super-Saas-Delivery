"""Application controls, independent of the unconfirmed webhook signature."""
from dataclasses import dataclass, field
import os

from app.services.billing_common import BillingError, identifier, scope

WEBHOOK_PATH = "/api/webhooks/billing/kiwify"


@dataclass(frozen=True)
class KiwifySettings:
    enabled: bool = False
    environment: str = "sandbox"
    account_id: str = ""
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)

    def validate(self):
        if self.enabled:
            scope("kiwify", self.environment)
            identifier(self.account_id)
        if bool(self.client_id) != bool(self.client_secret):
            raise BillingError("incomplete_kiwify_api_credentials")


def kiwify_settings():
    settings = KiwifySettings(
        enabled=os.getenv("KIWIFY_UNTRUSTED_INGRESS_ENABLED", "false").lower() == "true",
        environment=os.getenv("KIWIFY_ENVIRONMENT", "sandbox"),
        account_id=os.getenv("KIWIFY_PROVIDER_ACCOUNT_ID", ""),
        client_id=os.getenv("KIWIFY_API_CLIENT_ID", ""),
        client_secret=os.getenv("KIWIFY_API_CLIENT_SECRET", ""),
    )
    settings.validate()
    return settings
