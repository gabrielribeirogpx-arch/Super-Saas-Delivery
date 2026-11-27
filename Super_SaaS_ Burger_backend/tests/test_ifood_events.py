import json
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.ifood_event import IFoodEvent
from app.models.tenant import Tenant
from app.services.ifood_events import poll_ifood_events


@pytest.fixture
def database():
    engine = create_engine("sqlite://")
    Tenant.__table__.create(engine)
    IFoodEvent.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([Tenant(id=1, slug="pilot"), Tenant(id=2, slug="other")])
        db.commit()
        yield engine, db
    engine.dispose()


def test_poll_persists_before_ack_and_handles_replay(database):
    engine, db = database
    merchant = uuid4()
    event = {
        "id": str(uuid4()),
        "merchantId": str(merchant),
        "orderId": str(uuid4()),
        "createdAt": "2026-11-27T13:00:00Z",
        "fullCode": "PLACED",
    }
    another = {**event, "id": str(uuid4()), "merchantId": str(uuid4())}
    acks = []

    def handle(request):
        assert request.headers["authorization"] == "Bearer pilot-token"
        if request.method == "GET":
            assert request.headers["x-polling-merchants"] == str(merchant)
            assert request.url.params["categories"] == "FOOD"
            return httpx.Response(200, json=[event, event, another])
        with Session(engine) as verify:
            assert verify.get(IFoodEvent, event["id"]).tenant_id == 1
            assert verify.get(IFoodEvent, another["id"]) is None
        acks.append(json.loads(request.content))
        return httpx.Response(500 if len(acks) == 1 else 202)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        kwargs = dict(access_token="pilot-token", tenant_id=1, merchant_id=merchant)
        with pytest.raises(httpx.HTTPStatusError):
            poll_ifood_events(http, db, **kwargs)
        assert poll_ifood_events(http, db, **kwargs) == 1
        with pytest.raises(ValueError, match="different tenant"):
            poll_ifood_events(http, db, **{**kwargs, "tenant_id": 2})
    assert db.query(IFoodEvent).count() == 1
    assert acks == [[{"id": event["id"]}], [{"id": event["id"]}]]


def test_no_new_events_does_not_ack(database):
    _, db = database

    def handle(request):
        assert request.method == "GET"
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        assert poll_ifood_events(
            http, db, access_token="pilot-token", tenant_id=1, merchant_id=uuid4(),
        ) == 0
    assert db.query(IFoodEvent).count() == 0
