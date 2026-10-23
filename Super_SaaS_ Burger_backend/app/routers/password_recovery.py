from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.rate_limiter import InMemoryRateLimiterService
from app.services import password_recovery as recovery

router = APIRouter(prefix='/api/admin/auth', tags=['admin-auth'])
_limiter = InMemoryRateLimiterService(limit=60, window_seconds=60)

class ForgotRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=80, pattern=r'^[a-z0-9][a-z0-9-]*$')
    email: EmailStr

class ResetRequest(BaseModel):
    token: str = Field(min_length=20,max_length=2048)
    password: str = Field(min_length=8,max_length=72)
    tenant_slug: str = Field(min_length=1,max_length=80,pattern=r'^[a-z0-9][a-z0-9-]*$')

class RecoveryRead(BaseModel):
    message: str


def limit(response):
    response.headers['Cache-Control'] = 'no-store'
    decision = _limiter.check(tenant_id='password-recovery',endpoint='public')
    if not decision.allowed:
        raise HTTPException(429,'Muitas tentativas. Aguarde um minuto.',headers={'Retry-After':str(decision.retry_after_seconds)})

@router.post('/forgot-password', response_model=RecoveryRead, status_code=202)
def forgot(payload: ForgotRequest, response: Response, background: BackgroundTasks, db: Session = Depends(get_db)):
    limit(response)
    recovery.ready()
    engine = db.get_bind()
    def deliver():
        try:
            with Session(bind=engine) as session:
                recovery.request_recovery(session,payload.tenant_slug,payload.email)
        except Exception:
            import logging
            logging.getLogger(__name__).error("Password recovery background task failed; details omitted")
    background.add_task(deliver)
    return {'message':recovery.MESSAGE}

@router.post('/reset-password', response_model=RecoveryRead)
def reset(payload: ResetRequest, response: Response, background: BackgroundTasks, db: Session = Depends(get_db)):
    limit(response)
    changed = recovery.reset_password(db,payload.token,payload.password,payload.tenant_slug)
    from app.services.transactional_emails import deliver_account_message
    background.add_task(deliver_account_message,db.get_bind(),'password_changed',changed['user_id'],changed['tenant_id'],changed['version'])
    return {'message':'Senha atualizada. Entre com sua nova senha.'}


# Separate public endpoints: a driver link cannot reset an administrative account.
driver_router = APIRouter(prefix='/api/driver/auth', tags=['driver-auth'])

@driver_router.post('/forgot-password', response_model=RecoveryRead, status_code=202)
def driver_forgot(payload: ForgotRequest, response: Response, background: BackgroundTasks, db: Session = Depends(get_db)):
    limit(response)
    recovery.ready()
    engine = db.get_bind()
    def deliver():
        try:
            with Session(bind=engine) as session:
                recovery.request_recovery(session,payload.tenant_slug,payload.email,audience='driver')
        except Exception:
            import logging
            logging.getLogger(__name__).error('Driver recovery task failed; details omitted')
    background.add_task(deliver)
    return {'message':recovery.MESSAGE}

@driver_router.post('/reset-password', response_model=RecoveryRead)
def driver_reset(payload: ResetRequest, response: Response, background: BackgroundTasks, db: Session = Depends(get_db)):
    limit(response)
    changed = recovery.reset_password(db,payload.token,payload.password,payload.tenant_slug,audience='driver')
    from app.services.transactional_emails import deliver_account_message
    background.add_task(deliver_account_message,db.get_bind(),'password_changed',changed['user_id'],changed['tenant_id'],changed['version'])
    return {'message':'Senha atualizada. Entre na área do entregador com sua nova senha.'}
