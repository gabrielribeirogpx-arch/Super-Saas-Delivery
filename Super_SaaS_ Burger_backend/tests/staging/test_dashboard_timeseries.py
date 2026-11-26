from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.finance import CashMovement
from app.models.order import Order
from app.models.tenant import Tenant
from app.routers.dashboard import dashboard_overview, dashboard_timeseries


@pytest.fixture(params=["sqlite", "postgresql"])
def dashboard_sessions(request):
    if request.param == "postgresql":
        yield request.getfixturevalue("pg")[2]
        return
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()


def test_last_local_day_matches_overview_and_respects_tenant(dashboard_sessions):
    midnight_utc = datetime(2026, 11, 25, tzinfo=timezone.utc)
    near_local_midnight = midnight_utc.replace(hour=2, minute=59)
    next_local_day = midnight_utc.replace(hour=3)
    with dashboard_sessions.begin() as db:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET LOCAL TIME ZONE 'Asia/Tokyo'"))
        new_store = Tenant(slug="dashboard-new-store")
        other_store = Tenant(slug="dashboard-other-store")
        db.add_all([new_store, other_store])
        db.flush()
        for tenant, when, cents in [
            (new_store, midnight_utc, 2990),
            (new_store, near_local_midnight, 3190),
            (new_store, next_local_day, 5000),
            (other_store, midnight_utc, 9900),
        ]:
            db.add(Order(tenant_id=tenant.id, cliente_telefone="", itens="[]",
                         created_at=when, total_cents=cents))
            db.add(CashMovement(tenant_id=tenant.id, occurred_at=when,
                                amount_cents=cents, type="in", category="sale"))
        db.add(CashMovement(tenant_id=new_store.id, occurred_at=near_local_midnight,
                            amount_cents=200, type="out", category="test"))
        db.flush()

        params = dict(tenant_id=new_store.id, start_date="2026-11-18", end_date="2026-11-24",
                      de=None, para=None, db=db, _user=None)
        overview = dashboard_overview(**params)
        points = dashboard_timeseries(**params, bucket="day")["points"]
        assert [point["date"] for point in points] == [f"2026-11-{day}" for day in range(18, 25)]
        assert sum(point["orders_count"] for point in points) == overview["orders_count"] == 2
        assert sum(point["gross_sales_cents"] for point in points) == overview["gross_sales_cents"] == 6180
        assert sum(point["net_cash_cents"] for point in points) == overview["net_cash_cents"] == 5980
        assert points[-1] == {
            "date": "2026-11-24", "orders_count": 2, "gross_sales_cents": 6180, "net_cash_cents": 5980,
        }

        hourly = dashboard_timeseries(**{**params, "start_date": "2026-11-24"}, bucket="hour")["points"]
        assert [point["date"] for point in hourly] == [
            f"2026-11-24T{hour:02d}:00:00" for hour in range(24)
        ]
        assert sum(point["orders_count"] for point in hourly) == 2
        assert sum(point["gross_sales_cents"] for point in hourly) == 6180
        assert hourly[21]["orders_count"] == hourly[23]["orders_count"] == 1
        assert hourly[22]["orders_count"] == 0
        assert hourly[23]["net_cash_cents"] == 2990

        params.update(start_date="2026-11-24T21:00:00-03:00", end_date="2026-11-24T22:00:00-03:00")
        assert dashboard_timeseries(**params, bucket="day")["points"] == [
            {"date": "2026-11-24", "orders_count": 1, "gross_sales_cents": 2990, "net_cash_cents": 2990}
        ]
