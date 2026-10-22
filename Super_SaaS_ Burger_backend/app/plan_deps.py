from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.services.plan_access import require_feature


def require_plan_feature(feature):
    def guard(user: AdminUser = Depends(require_admin_user), db: Session = Depends(get_db)):
        require_feature(db, user.tenant_id, feature)
    return guard
