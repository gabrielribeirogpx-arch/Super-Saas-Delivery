"""Operator-only CLI for sanitized queue inspection/retry. Not an HTTP endpoint."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.core.hotmart_config import hotmart_settings
from app.models.billing_event import BillingEvent,BillingEventStatus as E
from app.services.admin_audit import log_admin_action

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--retry-event',type=int)
    args=parser.parse_args()
    settings=hotmart_settings()
    with SessionLocal() as db,db.begin():
        query=db.query(BillingEvent).filter_by(provider='hotmart',provider_account_id=settings.account_id,environment=settings.environment)
        if args.retry_event:
            row=query.filter_by(id=args.retry_event).with_for_update().one()
            if row.processing_status==E.PROCESSED:
                raise RuntimeError('Processed events cannot be reopened')
            row.attempt_count=0;row.next_attempt_at=None
            if row.tenant_id:
                log_admin_action(db,tenant_id=row.tenant_id,user_id=None,actor_type='system',action='billing.hotmart_retry_requested',
                    entity_type='billing_event',entity_id=row.id,meta={'origin':'operator_cli'})
            print('Event scheduled for retry')
        else:
            for row in query.filter(BillingEvent.processing_status!=E.PROCESSED).order_by(BillingEvent.id).limit(100):
                print({'id':row.id,'tenant_id':row.tenant_id,'type':row.event_type,'attempts':row.attempt_count,'reason':row.error_code})
    return 0
if __name__=='__main__':
    raise SystemExit(main())
