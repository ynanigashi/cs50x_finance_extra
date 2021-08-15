from sqlalchemy import Column, Integer, Float,String, ForeignKey, text, TIMESTAMP
from sqlalchemy.sql.functions import current_timestamp
from sqlalchemy.orm import declarative_base


Base = declarative_base()

"""
Tables
"""
class Users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String, unique=True, nullable=False)
    hash = Column(String, nullable=False)
    cash = Column(Float, nullable=Float, server_default=text('10000.00'))

    def __repr__(self):
        return f'id: {self.id}, user name: {self.username}, cash: {self.cash}'

class Transactions(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    type = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    created_datetime = Column(TIMESTAMP, server_default=current_timestamp())

    def __repr__(self):
        return f'id: {self.id}, user id: {self.user_id}, type: {self.type}, symbol: {self.symbol}, price: {self.price}, shares: {self.shares} , create_datetime: {self.create_datetime}'

'''
.schema transactions
CREATE TABLE transactions (
    id INTEGER,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC NOT NULL,
    shares INTEGER NOT NULL,
    created_datetime TIMESTAMP DEFAULT (datetime(CURRENT_TIMESTAMP,'localtime')),
    PRIMARY KEY(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE users (
    id INTEGER, 
    username TEXT NOT NULL, 
    hash TEXT NOT NULL, 
    cash NUMERIC NOT NULL DEFAULT 10000.00, 
    PRIMARY KEY(id)
);
CREATE UNIQUE INDEX username ON users (username);
'''