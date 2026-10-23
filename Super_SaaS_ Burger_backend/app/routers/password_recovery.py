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
def reset(payload: ResetRequest, response: Response, db: Session = Depends(get_db)):
    limit(response)
    recovery.reset_password(db,payload.token,payload.password,payload.tenant_slug)
    return {'message':'Senha atualizada. Entre com sua nova senha.'}
