from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.config import settings
from pymongo import MongoClient


def make_engine(url):
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def sqlite_pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

    return engine


engine = make_engine(settings.database_url)
Session = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with Session() as session:
        yield session


# One configured PyMongo client, shared by all document repositories.
mongo_client = (
    MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        socketTimeoutMS=5000,
    )
    if settings.mongodb_uri
    else None
)


def get_mongodb():
    """Return the configured MongoDB database, or None for durable local fallback."""
    return mongo_client[settings.mongodb_database] if mongo_client is not None else None
