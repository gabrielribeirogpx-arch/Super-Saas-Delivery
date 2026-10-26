"""Bounded official OAuth/subscription client. Errors never include URLs/secrets/PII."""
import time
from urllib.parse import quote
import httpx
from app.services.billing_common import BillingError

class HotmartUnavailable(BillingError):
    pass

class HotmartAPI:
    def __init__(self, settings, *, transport=None):
        self.settings = settings
        self.client = httpx.Client(timeout=10, follow_redirects=False, transport=transport)
        self.token = None
        self.expires = 0
        host = "sandbox.hotmart.com" if settings.environment == "sandbox" else "developers.hotmart.com"
        self.base = "https://" + host + "/payments/api/v1"

    def close(self):
        self.client.close()

    def _json(self, method, url, *, array=False, **kwargs):
        try:
            with self.client.stream(method, url, **kwargs) as response:
                if response.status_code != 200:
                    if response.status_code == 401:
                        self.token = None
                    raise HotmartUnavailable("hotmart_api_unavailable")
                chunks, total = [], 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 512 * 1024:
                        raise HotmartUnavailable("hotmart_response_invalid")
                    chunks.append(chunk)
                import json
                data = json.loads(b"".join(chunks))
                if not isinstance(data, list if array else dict):
                    raise ValueError()
                return data
        except (httpx.RequestError, ValueError):
            raise HotmartUnavailable("hotmart_api_unavailable") from None

    def _headers(self):
        if self.token is None or time.monotonic() >= self.expires:
            data = self._json("POST", "https://api-sec-vlc.hotmart.com/security/oauth/token",
                params={"grant_type": "client_credentials", "client_id": self.settings.client_id,
                        "client_secret": self.settings.client_secret},
                headers={"Authorization": "Basic " + self.settings.basic, "Content-Type": "application/json"})
            if not isinstance(data.get("access_token"), str) or not data["access_token"]:
                raise HotmartUnavailable("hotmart_token_invalid")
            ttl = data.get("expires_in")
            if type(ttl) is not int or ttl <= 0:
                raise HotmartUnavailable("hotmart_token_invalid")
            self.token = data["access_token"]
            self.expires = time.monotonic() + max(0, ttl - 60)
        return {"Authorization": "Bearer " + self.token}

    def subscription(self, code, product_id):
        data = self._json("GET", self.base + "/subscriptions", headers=self._headers(),
            params={"subscriber_code": code, "product_id": product_id, "max_results": 2})
        rows = data.get("items")
        if not isinstance(rows, list) or len(rows) != 1:
            raise HotmartUnavailable("hotmart_subscription_unconfirmed")
        row = rows[0]
        if (not isinstance(row, dict) or row.get("subscriber_code") != code
            or str(row.get("product", {}).get("id")) != product_id):
            raise HotmartUnavailable("hotmart_subscription_mismatch")
        return row

    def purchases(self, code):
        data = self._json("GET", self.base + "/subscriptions/" + quote(code,safe="") + "/purchases",
            headers=self._headers(),array=True)
        if len(data)>1000 or not all(isinstance(row,dict) for row in data):
            raise HotmartUnavailable("hotmart_purchases_invalid")
        return data

    def cancel(self, code):
        data = self._json("POST", self.base + "/subscriptions/" + quote(code, safe="") + "/cancel",
            headers=self._headers(), json={"send_mail": True})
        if data.get("subscriber_code") != code or data.get("status") != "INACTIVE":
            raise HotmartUnavailable("hotmart_cancellation_unconfirmed")
