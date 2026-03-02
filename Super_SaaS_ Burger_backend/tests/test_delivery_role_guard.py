from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.deps import require_delivery_user


def test_require_delivery_user_allows_delivery_with_tenant():
    user = SimpleNamespace(id=10, role="DELIVERY", tenant_id=3)
    assert require_delivery_user(user=user) is user


def test_require_delivery_user_rejects_non_delivery_role():
    user = SimpleNamespace(id=11, role="owner", tenant_id=3)
    with pytest.raises(HTTPException) as exc:
        require_delivery_user(user=user)

    assert exc.value.status_code == 403


def test_require_delivery_user_rejects_missing_tenant():
    user = SimpleNamespace(id=12, role="DELIVERY", tenant_id=None)
    with pytest.raises(HTTPException) as exc:
        require_delivery_user(user=user)

    assert exc.value.status_code == 403
