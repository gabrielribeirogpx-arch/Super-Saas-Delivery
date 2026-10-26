import asyncio
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from sqlalchemy.pool import QueuePool
from starlette.requests import Request
from starlette.responses import Response
from app.middleware import tenant_context as module


def request(path='/public/menu', method='GET'):
    return Request({'type': 'http', 'method': method, 'path': path,
                    'query_string': b'slug=meuburger', 'headers': []})


def test_pool_contention_does_not_block_connection_return(monkeypatch):
    pool = QueuePool(lambda: sqlite3.connect(':memory:', check_same_thread=False),
                     pool_size=1, max_overflow=0, timeout=1)
    held = pool.connect()
    started = threading.Event()
    threads = []
    tenant = SimpleNamespace(id=7)
    class Session:
        def __init__(self):
            threads.append(threading.get_ident())
            self.connection = None
        def close(self):
            threads.append(threading.get_ident())
            if self.connection is not None: self.connection.close()
    def resolve(db, req):
        threads.append(threading.get_ident())
        started.set()
        db.connection = pool.connect()
        return tenant
    monkeypatch.setattr(module, 'SessionLocal', Session)
    monkeypatch.setattr(module.TenantResolver, 'resolve_tenant_from_request', resolve)
    async def exercise():
        async def next_handler(r):
            assert r.state.tenant is tenant
            assert r.state.tenant_id == 7
            assert pool.checkedout() == 0
            return Response(status_code=204)
        async def return_connection():
            # Pending request must be able to resume and release its connection.
            while not started.is_set(): await asyncio.sleep(.001)
            held.close()
        releaser = asyncio.create_task(return_connection())
        try:
            result = await module.TenantContextMiddleware(lambda *a: None).dispatch(request(), next_handler)
            assert result.status_code == 204
        finally:
            await releaser
        assert len(threads) == 3 and len(set(threads)) == 1
        assert threads[0] != threading.get_ident()
    try:
        asyncio.run(exercise())
    finally:
        held.close()
        pool.dispose()


def test_session_closed_in_worker_on_resolution_error(monkeypatch):
    threads = []
    class Session:
        def __init__(self): threads.append(threading.get_ident())
        def close(self): threads.append(threading.get_ident())
    def fail(db, req):
        threads.append(threading.get_ident())
        raise ValueError('resolution failed')
    monkeypatch.setattr(module, 'SessionLocal', Session)
    monkeypatch.setattr(module.TenantResolver, 'resolve_tenant_from_request', fail)
    async def exercise():
        async def next_handler(r): pytest.fail('continued after error')
        with pytest.raises(ValueError, match='resolution failed'):
            await module.TenantContextMiddleware(lambda *a: None).dispatch(request(), next_handler)
        assert len(threads) == 3 and len(set(threads)) == 1
        assert threads[0] != threading.get_ident()
    asyncio.run(exercise())


@pytest.mark.parametrize('kind', ['options', 'hotmart', 'kiwify'])
def test_bypasses_do_not_open_session(monkeypatch, kind):
    from app.core.hotmart_config import WEBHOOK_PATH as hotmart
    from app.core.kiwify_config import WEBHOOK_PATH as kiwify
    def forbidden(): pytest.fail('bypassed request opened a DB session')
    monkeypatch.setattr(module, 'SessionLocal', forbidden)
    req = request(method='OPTIONS') if kind == 'options' else request(path=hotmart if kind == 'hotmart' else kiwify, method='POST')
    async def exercise():
        async def next_handler(r): return Response(status_code=204)
        response = await module.TenantContextMiddleware(lambda *a: None).dispatch(req, next_handler)
        assert response.status_code == 204
    asyncio.run(exercise())
