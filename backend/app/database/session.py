from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config.settings import settings, ensure_dirs
ensure_dirs(); engine=create_engine(settings.db_url, connect_args={'check_same_thread':False})
SessionLocal=sessionmaker(bind=engine, autoflush=False, autocommit=False)
class Base(DeclarativeBase): pass
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
def init_db():
    import app.models.entities
    Base.metadata.create_all(bind=engine)
