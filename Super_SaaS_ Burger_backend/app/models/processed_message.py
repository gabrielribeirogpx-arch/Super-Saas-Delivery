from sqlalchemy import Column, String
from app.core.database import Base

class ProcessedMessage(Base):
    __tablename__ = "processed_messages"
    message_id = Column(String, primary_key=True)
