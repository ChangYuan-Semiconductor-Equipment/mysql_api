"""Mysql 数据库模块."""
import logging
from typing import Union, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.decl_api import DeclarativeMeta

from mysql_api.exception import MySQLAPIAddError, MySQLAPIQueryError


# pylint: disable=R0913, R0917
# noinspection SqlNoDataSourceInspection
class MySQLDatabase:
    """MySQLDatabase class."""

    def __init__(self, user_name, password, database_name: str = "cyg", host: str = "127.0.0.1", port: int = 3306):
        self.logger = logging.getLogger(__name__)
        self.engine = create_engine(
            f"mysql+pymysql://{user_name}:{password}@{host}:{port}/{database_name}?charset=utf8mb4", echo=True
        )
        self.session = scoped_session(sessionmaker(bind=self.engine))

    @staticmethod
    def create_database(user_name: str, password: str, db_name: str, host: str = "127.0.0.1", port: int = 3306):
        """创建数据库.

        Args:
            user_name: 用户名.
            password: 密码.
            host: 数据库服务地址ip.
            port:端口号.
            db_name: 要创建的数据库名称.
        """
        engine = create_engine(f"mysql+pymysql://{user_name}:{password}@{host}:{port}", echo=True)
        with engine.connect() as con:
            con.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name}"))

    def create_table(self, declarative_base: DeclarativeMeta):
        """在执行数据库下创建数据表.

        Args:
            declarative_base: SQLAlchemy的declarative_base对象.
        """
        declarative_base.metadata.create_all(self.engine)

    def add_data(self, model_cls, data: dict):
        """向指定数据表添加一行数据.

        Args:
            model_cls: 数据表模型class.
            data: 要添加的数据, 键值对形式.

        Raises:
            MySQLAPIAddError: 添加数据失败抛出异常.
        """
        with self.session() as session:
            try:
                new_instance = model_cls(**data)
                session.add(new_instance)
                session.commit()
            except DatabaseError as e:
                session.rollback()
                raise MySQLAPIAddError(f"Failed to add data to {model_cls.__name__}: {e}") from e

    def update_data(
            self, model_cls, key: str, key_value: Union[str, int, float],
            update_values: Dict[str, Union[str, int, float]]
    ):
        """向指定数据表更新数据.

        Args:
            model_cls: 数据表模型class.
            key: 要更新的字段名.
            key_value: key字段的值.
            update_values: 要更新的字段值.

        Raises:
            MySQLAPIAddError: 更新数据失败抛出异常.
        """
        with self.session() as session:
            try:
                if instances := self.query_data_all(model_cls, **{key: key_value}):
                    for instance in instances:
                        for field, value in update_values.items():
                            setattr(instance, field, value)
                        session.commit()
            except DatabaseError as e:
                session.rollback()
                raise MySQLAPIAddError(f"Failed to add data to {model_cls.__name__}: {e}") from e

    def query_data_all(self, model_cls, **filters) -> list:
        """查询指定模型的数据.

        Args:
            model_cls: SQLAlchemy 模型类.
            filters: 查询条件，以关键字参数传入.

        Returns:
            list: 查询结果列表.

        Raises:
            MySQLAPIQueryError: 查询失败抛出异常.
        """
        with self.session() as session:
            try:
                return session.query(model_cls).filter_by(**filters).all()
            except DatabaseError as e:
                raise MySQLAPIQueryError(f"Failed to query data for {model_cls.__name__}: {e}") from e

    def query_data_one(self, model_cls, **filters):
        """查询指定模型的一条数据.

        Args:
            model_cls: SQLAlchemy 模型类.
            filters: 查询条件，以关键字参数传入.

        Returns:
            list: 查询结果列表.

        Raises:
            MySQLAPIQueryError: 查询失败抛出异常.
        """
        with self.session() as session:
            try:
                return session.query(model_cls).filter_by(**filters).first()
            except DatabaseError as e:
                raise MySQLAPIQueryError(f"Failed to query data for {model_cls.__name__}: {e}") from e

    def query_data_page(self, model_cls, page=1, page_size=10, **filters):
        """查询指定模型的多条数据，并支持分页.

        Args:
            model_cls: SQLAlchemy 模型类.
            page: 当前页码, 默认为 1.
            page_size: 每页记录数, 默认为 10.
            filters: 查询条件，以关键字参数传入.

        Returns:
            list: 查询结果列表.

        Raises:
            MySQLAPIQueryError: 查询失败抛出异常.
        """
        with self.session() as session:
            try:
                offset_value = (page - 1) * page_size
                return session.query(model_cls).filter_by(**filters).limit(page_size).offset(offset_value).all()
            except DatabaseError as e:
                raise MySQLAPIQueryError(f"Failed to query data for {model_cls.__name__}: {e}") from e
