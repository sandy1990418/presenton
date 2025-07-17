from contextlib import contextmanager
import os
import tempfile
from sqlalchemy import create_engine
from sqlmodel import Session


# 確保APP_DATA_DIRECTORY有值，如果沒有則使用臨時目錄
app_data_dir = os.getenv("APP_DATA_DIRECTORY") or tempfile.gettempdir()
database_url = os.getenv("DATABASE_URL") or "sqlite:///" + os.path.join(
    app_data_dir, "fastapi.db"
)
connect_args = {}
if "sqlite" in database_url:
    connect_args["check_same_thread"] = False

sql_engine = create_engine(database_url, connect_args=connect_args)


@contextmanager
def get_sql_session():
    session = Session(sql_engine)
    try:
        yield session
    finally:
        session.close()
