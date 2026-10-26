"""Real HTTP/Chromium validation against loopback PostgreSQL and synthetic data.
Requires a frontend build targeting 127.0.0.1:8015. Never uses production URLs.
"""
import os, sys, secrets, subprocess, time, json, re
from pathlib import Path
import tempfile, socket, signal
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path[:0] = [str(ROOT), str(ROOT/"tests/staging")]
import pytest
import sqlalchemy as sa
from playwright.sync_api import sync_playwright, expect
from conftest import pg
from app.models.admin_user import AdminUser
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.billing_event import BillingEvent
from app.models.admin_audit_log import AdminAuditLog
from app.services.passwords import hash_password
from app.services.billing_catalog import BillingCatalogService
from app.models.plan import Plan
from app.services.billing_inbox import BillingInboxService
from app.services.kiwify_projection import project_webhook
from app.services.kiwify_api import KiwifySalesAPI
from app.services.kiwify_verification import KiwifyVerificationService
from app.core.kiwify_config import KiwifySettings
from datetime import datetime, timedelta, timezone
import httpx

RESULTS={}

def run():
    value=os.environ.get("FOMIZERO_PHASE4_DATABASE_URL")
    if not value or os.environ.get("FOMIZERO_PHASE4_CONFIRM_STAGING") != "yes":
        raise RuntimeError("Isolated database and confirmation required")
    url=sa.engine.make_url(value)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost","127.0.0.1","::1"}:
        raise RuntimeError("Loopback PostgreSQL only")
    for port in [8015,3015]:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            probe.bind(("127.0.0.1",port))
    manifest=json.loads((ROOT.parent/"super_saas_frontend/.next/routes-manifest.json").read_text())
    rewrites=manifest["rewrites"]
    if isinstance(rewrites,dict):
        rewrites=[rule for group in rewrites.values() for rule in group]
    assert any(rule.get("source")=="/api/:path*" and rule.get("destination")=="http://127.0.0.1:8015/api/:path*" for rule in rewrites)
    artifact_dir=Path(tempfile.mkdtemp(prefix="fomizero-phase4-"))
    monkey = pytest.MonkeyPatch()
    fixture = pg.__wrapped__(monkey)
    engine, cfg, sessions = next(fixture)
    processes=[]
    logs=[]
    results=RESULTS
    try:
        password=secrets.token_urlsafe(24)
        with sessions() as db, db.begin():
            for user in db.query(AdminUser):
                user.password_hash=hash_password(password)
        now=datetime.now(timezone.utc)
        settings=KiwifySettings(True,"sandbox","phase4-account","synthetic-client","synthetic-secret")
        def ref(i): return f"00000000-0000-4000-8000-{i:012d}"
        def event(tenant, sale, sub, product, offer, correlation=False):
            with sessions() as db,db.begin():
                if correlation:
                    plan=db.query(Plan).filter_by(code="essential").one()
                    catalog=BillingCatalogService(db)
                    catalog.create_mapping(provider="kiwify",environment="sandbox",provider_account_id=settings.account_id,external_product_id=product,external_offer_id=offer,plan_id=plan.id)
                    intent=catalog.create_intent(tenant,plan.id,provider="kiwify",environment="sandbox",provider_account_id=settings.account_id,expires_at=now+timedelta(hours=1),now=now)
                    catalog.complete_intent(tenant,intent.public_token,external_subscription_id=sub,now=now)
                body={"order_id":sale,"webhook_event_type":"order_approved","subscription_id":sub,"Product":{"product_id":product},"Subscription":{"id":sub,"plan":{"id":offer}},"Customer":{"email":"phase4-pii-marker","document":"phase4-pii-marker"}}
                projection,identity=project_webhook(body)
                eid=BillingInboxService(db).receive_event(provider="kiwify",environment="sandbox",provider_account_id=settings.account_id,provider_event_id=identity,event_type="order_approved",payload=body,schema_version=2,sanitized_projection=projection).event.id
            def api(request):
                if request.url.path.endswith("/oauth/token"):
                    return httpx.Response(200,json={"access_token":"phase4-secret-marker","token_type":"Bearer","scope":"sales","expires_in":86400})
                return httpx.Response(200,json={"id":sale,"status":"paid","product":{"id":product},"Customer":{"email":"phase4-pii-marker"}})
            source=KiwifySalesAPI(settings,reserve=lambda:None,transport=httpx.MockTransport(api))
            try: KiwifyVerificationService(sessions,settings,source=source).verify_event(eid)
            finally: source.close()
            return eid,body
        first,body=event(1,ref(1),ref(2),ref(3),ref(4),True)
        second,_=event(1,ref(5),ref(2),ref(3),ref(4))
        other,_=event(2,ref(6),ref(7),ref(8),ref(9),True)
        unknown,_=event(None,ref(10),ref(11),ref(12),ref(13))
        env=os.environ.copy()
        env.update(DATABASE_URL=engine.url.render_as_string(hide_password=False),ENVIRONMENT="staging",ENV="staging",ADMIN_SESSION_SECRET=secrets.token_urlsafe(32),ADMIN_SESSION_COOKIE_SECURE="false",KIWIFY_UNTRUSTED_INGRESS_ENABLED="true",KIWIFY_PROVIDER_ACCOUNT_ID=settings.account_id,KIWIFY_ENVIRONMENT="sandbox",FEATURE_LEGACY_ADMIN="false",DEV_ADMIN_PASSWORD="",REDIS_URL="",PYTHONPATH=".")
        backendlog=open(artifact_dir/"backend.log","w")
        logs.append(backendlog)
        backend=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8015"],env=env,stdout=backendlog,stderr=backendlog,start_new_session=True)
        processes.append(backend)
        for _ in range(100):
            try:
                if httpx.get("http://127.0.0.1:8015/openapi.json").status_code==200: break
            except httpx.RequestError: pass
            time.sleep(.2)
        else: raise RuntimeError("Isolated backend startup failed")
        response=httpx.post("http://127.0.0.1:8015/api/webhooks/billing/kiwify?signature=phase4-signature-marker",json=body)
        assert response.status_code==202
        frontenv=os.environ.copy()
        frontenv.update(NEXT_PUBLIC_API_URL="",STOREFRONT_BACKEND_URL="http://127.0.0.1:8015",PORT="3015",NEXT_TELEMETRY_DISABLED="1")
        frontendlog=open(artifact_dir/"frontend.log","w")
        logs.append(frontendlog)
        frontend=subprocess.Popen(["npm","run","start"],cwd="../super_saas_frontend",env=frontenv,stdout=frontendlog,stderr=frontendlog,start_new_session=True)
        processes.append(frontend)
        for _ in range(100):
            try:
                if httpx.get("http://127.0.0.1:3015/login").status_code==200: break
            except httpx.RequestError: pass
            time.sleep(.2)
        else: raise RuntimeError("Isolated frontend startup failed")
        with sync_playwright() as browser_api:
            browser=browser_api.chromium.launch(executable_path="/usr/bin/chromium",headless=True,args=["--no-sandbox"])
            def context(email,slug):
                ctx=browser.new_context(base_url="http://127.0.0.1:3015", service_workers="block")
                # Never permit the browser to call the production API baked into
                # a stale build, or any external origin during this validation.
                from urllib.parse import urlsplit
                ctx.route("**/*",lambda route: route.continue_() if urlsplit(route.request.url).hostname in {"127.0.0.1","localhost"} else route.abort())
                response=ctx.request.post("/api/admin/auth/login",data=json.dumps({"email":email,"password":password,"tenant_slug":slug}), headers={"Content-Type":"application/json"})
                assert response.status==200
                return ctx
            a=context("owner-a@example.com","phase4-a")
            page=a.new_page()
            page.goto("/subscriptions/reviews")
            expect(page.get_by_text("Assinaturas > Revisões pendentes",exact=True)).to_be_visible()
            expect(page.get_by_role("button",name="Revisar",exact=True)).to_have_count(2)
            page.get_by_label("Tipo de evento").select_option("subscription_renewed")
            expect(page.get_by_text("Nenhuma revisão pendente nesta página.")).to_be_visible()
            page.get_by_label("Tipo de evento").select_option("order_approved")
            expect(page.get_by_role("button",name="Revisar",exact=True)).to_have_count(2)
            row=page.locator("tbody tr").filter(has=page.locator("td:first-child").filter(has_text=re.compile(rf"^#{first}(?![0-9])")))
            row.get_by_role("button",name="Revisar",exact=True).click()
            expect(page.get_by_role("button",name="Aprovar vínculo da assinatura",exact=True)).to_be_enabled()
            assert "phase4-pii-marker" not in page.locator("body").inner_text()
            page.get_by_role("button",name="Aprovar vínculo da assinatura",exact=True).click()
            expect(page.get_by_text("Vínculo validado. O acesso continua pendente por ausência de período confiável (manual_review_period_missing).",exact=True).first).to_be_visible()
            with sessions() as db:
                sub=db.query(Subscription).filter_by(tenant_id=1).one()
                assert sub.status==SubscriptionStatus.INACTIVE and sub.current_period_end is None
            results["approve_inactive_without_period"]=True
            page.get_by_role("button",name="Fechar",exact=True).click()
            row=page.locator("tbody tr").filter(has=page.locator("td:first-child").filter(has_text=re.compile(rf"^#{second}(?![0-9])")))
            row.get_by_role("button",name="Revisar",exact=True).click()
            page.get_by_label("Motivo da rejeição").select_option("invalid_sale")
            page.get_by_role("button",name="Rejeitar",exact=True).click()
            expect(page.get_by_text("Evento rejeitado e preservado para auditoria.",exact=True)).to_be_visible()
            results["list_filter_detail_reject"]=True
            with sessions() as db:
                assert db.get(BillingEvent,second) is not None
                assert db.query(AdminAuditLog).filter_by(action="billing.manual_review_rejected",tenant_id=1,user_id=1).count()==1
            page.get_by_role("button",name="Fechar",exact=True).click()
            page.route("**/api/admin/billing/reviews**",lambda route:route.fulfill(status=503,json={"detail":"unavailable"}))
            page.get_by_role("button",name="Atualizar",exact=True).click()
            expect(page.get_by_text("Não foi possível carregar a fila. Tente atualizar.",exact=True)).to_be_visible(timeout=15000)
            results["error_state"]=True
            b=context("admin-b@example.com","phase4-b")
            bpage=b.new_page()
            bpage.goto("/subscriptions/reviews")
            expect(bpage.get_by_role("button",name="Revisar",exact=True)).to_have_count(1)
            assert b.request.post(f"/api/admin/billing/reviews/{first}/approve",headers={"X-Billing-Review":"1"}).status==404
            results["tenant_isolation"]=True
            operator=context("operator-a@example.com","phase4-a")
            opage=operator.new_page()
            opage.goto("/subscriptions/reviews")
            expect(opage.get_by_text("Acesso restrito",exact=True)).to_be_visible()
            results["rbac"]=True
            browser.close()
        time.sleep(.2)
    finally:
        for proc in processes:
            try: os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError: pass
        for proc in processes:
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait(timeout=5)
        for log in logs: log.close()
        fixture.close()
        monkey.undo()
    text="\n".join(path.read_text() for path in artifact_dir.glob("*.log"))
    results["application_and_access_logs_sanitized"] = not any(x in text for x in ["phase4-signature-marker","phase4-pii-marker","phase4-secret-marker",password])
    print(json.dumps(results,sort_keys=True))
    return 0 if all(results.values()) else 1

if __name__=="__main__":
    try: sys.exit(run())
    except Exception as error:
        print("Isolated HTTP/browser validation failed: "+type(error).__name__)
        print(json.dumps(RESULTS,sort_keys=True))
        sys.exit(2)
