import os

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer,
                        Numeric, String, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    category = Column(String(255))
    language = Column(String(255))


class Streamer(Base):
    __tablename__ = "streamers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255))
    english_name = Column(String(255))
    photo = Column(String(255))
    channel_id = Column(String(255), unique=True)
    twitter = Column(String(255))
    inactive = Column(Boolean)
    branch_id = Column(Integer, ForeignKey("branches.id"))
    branch = relationship("Branch")


class SuperChat(Base):
    __tablename__ = "super_chats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True))
    currency = Column(String(255))
    amount_value = Column(Numeric(10, 2))
    bg_color = Column(Integer)
    channel_id = Column(String(255))
    streamer_id = Column(Integer, ForeignKey("streamers.id"))
    streamer = relationship("Streamer")


class DoneVideo(Base):
    __tablename__ = "done_videos"
    id = Column(String(255), primary_key=True)
    streamer_id = Column(Integer, ForeignKey("streamers.id"))
    streamer = relationship("Streamer")


class Collection(Base):
    __tablename__ = "collections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True))


engine = create_engine(f"mysql+pymysql://{os.environ["MARIADB_USER"]}:{os.environ["MARIADB_PASSWORD"]}@db:3306/sc-stats")
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
