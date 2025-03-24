# pylint: skip-file
"""Mysql 数据库模块."""
import logging
from typing import Union, Dict
from datetime import datetime

from sqlalchemy import create_engine, text, func
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.decl_api import DeclarativeMeta

from mysql_api.exception import MySQLAPIAddError, MySQLAPIQueryError, MySQLAPIDeleteError, MySQLAPIUpdateError


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

    def add_data_multiple(self, model_cls, data: list[dict]):
        """向指定数据表添加多行数据.

        Args:
            model_cls: 数据表模型class.
            data: 要添加的数据列表, 每个元素是一个字典, 表示一行数据.

        Raises:
            MySQLAPIAddError: 添加数据失败抛出异常.
        """
        with self.session() as session:
            try:
                # 创建多个模型实例
                new_instances = [model_cls(**item) for item in data]
                session.add_all(new_instances)  # 使用 add_all 批量添加
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
                if instances := session.query(model_cls).filter_by(**{key: key_value}):
                    instances.update(update_values)
                    session.commit()
            except DatabaseError as e:
                session.rollback()
                raise MySQLAPIAddError(f"Failed to add data to {model_cls.__name__}: {e}") from e

    def update_column_values(
            self, model_cls, column_name: str, new_value: Union[str, int, float]
    ):
        """更新数据表中某一列的所有值为指定值.

        Args:
            model_cls: 数据表模型class.
            column_name: 要更新的列名.
            new_value: 要更新的新值.

        Raises:
            MySQLAPIUpdateError: 更新数据失败抛出异常.
        """
        with self.session() as session:
            try:
                session.query(model_cls).update({column_name: new_value})
                session.commit()
            except DatabaseError as e:
                session.rollback()
                raise MySQLAPIUpdateError(f"Failed to update column {column_name} in {model_cls.__name__}: {e}") from e


    def update_columns_values(self, model_cls, column_updates: Dict[str, Union[str, int, float]]):
        """更新数据表中多列的所有值为指定值。

        Args:
            model_cls: 数据表模型类。
            column_updates: 字典格式的列名和新值，例如：
                {"column1": "new_value1", "column2": 123}

        Raises:
            MySQLAPIUpdateError: 更新数据失败时抛出异常。
        """
        with self.session() as session:
            try:
                session.query(model_cls).update(column_updates)
                session.commit()
            except DatabaseError as e:
                session.rollback()
                raise MySQLAPIUpdateError(
                    f"Failed to update columns {list(column_updates.keys())} "
                    f"in {model_cls.__name__}: {e}"
                ) from e

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

    def query_join(self, model_cls_a, model_cls_b, column_name, **filters) -> list:
        """连接 model_cls_a 和 model_cls_b 表, 以 model_cls_a 表的数据个数为准.

        Args:
            model_cls_a: 左表模型.
            model_cls_b: 右表模型.
            column_name: 左右表连接键的列名.
            filters: 查询条件，以关键字参数传入.

        Returns:
            list: 连接后的结果，以字典形式返回.

        Raises:
            MySQLAPIQueryError: 查询失败抛出异常.
        """
        with self.session() as session:
            try:
                # 查询 ProductInStationLeft 表的数据
                table_a_data = session.query(model_cls_a).filter_by(**filters).all()

                # 查询 OriginMapData 表的数据
                table_b_data = session.query(model_cls_b).all()

                # 将 OriginMapData 表的数据转换为字典，以 product_code 为键
                table_b_dict = {getattr(item, column_name): item.as_dict() for item in table_b_data}

                # 连接两个表的数据
                joined_data = []
                for instance in table_a_data:
                    one_row_data = instance.as_dict()
                    if getattr(instance, column_name) in table_b_dict:
                        one_row_data.update(table_b_dict[getattr(instance, column_name)])
                    joined_data.append(one_row_data)

                return joined_data
            except DatabaseError as e:
                raise MySQLAPIQueryError(f"Failed to join tables: {e}") from e

    def query_data_by_values(self, model_cls, field: str, values: list, **filters) -> list:
        """查询指定字段的值等于多个值的数据.

        Args:
            model_cls: SQLAlchemy 模型类.
            field: 要查询的字段名.
            values: 字段对应的多个值，以列表形式传入.
            filters: 其他查询条件，以关键字参数传入.

        Returns:
            list: 查询结果列表.

        Raises:
            MySQLAPIQueryError: 查询失败抛出异常.
        """
        with self.session() as session:
            try:
                query = session.query(model_cls)
                # 如果指定了 field 和 values，则添加相应的过滤条件
                if field is not None and values is not None:
                    query = query.filter(getattr(model_cls, field).in_(values))
                # 添加其他过滤条件
                if filters:
                    query = query.filter_by(**filters)
                return query.all()
            except DatabaseError as e:
                raise MySQLAPIQueryError(f"Failed to query data for {model_cls.__name__}: {e}") from e

    def query_data_one(self, model_cls, **filters):
        """查询指定模型的一条数据.

        Args:
            model_cls: SQLAlchemy 模型类.
            filters: 查询条件，以关键字参数传入.

        Returns:
            模型类实例或None: 查询结果，如果未找到数据则返回None.

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

    def delete_all_data(self, model_cls):
        """删除指定模型的所有数据，并重置自增索引.

        Args:
            model_cls: SQLAlchemy 模型类.

        Raises:
            MySQLAPIDeleteError: 删除失败抛出异常.
        """
        with self.session() as session:
            try:
                session.query(model_cls).delete()
                table_name = model_cls.__tablename__
                session.execute(text(f"ALTER TABLE {table_name} AUTO_INCREMENT = 1"))
                session.commit()
            except DatabaseError as e:
                session.rollback()
                raise MySQLAPIDeleteError(f"Failed to delete data from {model_cls.__name__}: {e}") from e

    def delete_data_by_id(self, model_cls, record_id: Union[int, str]):
        """根据id删除指定模型的一条数据.

        Args:
            model_cls: SQLAlchemy 模型类.
            record_id: 要删除的记录的id值.

        Raises:
            MySQLAPIDeleteError: 删除失败抛出异常.
        """
        with self.session() as session:
            try:
                instance = session.query(model_cls).filter_by(id=int(record_id)).first()
                if instance:
                    session.delete(instance)
                    session.commit()
            except DatabaseError as e:
                session.rollback()
                raise MySQLAPIDeleteError(f"Failed to delete data by id from {model_cls.__name__}: {e}") from e

    def query_data_with_date(self, model_cls, **filters) -> list:
        """根据日期查询指定模型的数据.

        Args:
            model_cls: SQLAlchemy 模型类.
            filters: 查询条件, 以关键字参数传入.

        Returns:
            list: 查询结果列表.

        Raises:
            MySQLAPIQueryError: 查询失败抛出异常.
        """
        with self.session() as session:
            try:
                query = session.query(model_cls)
                for filter_name, value in filters.items():
                    if filter_name == "created_at":
                        value = datetime.strptime(value, "%Y-%m-%d")
                        query = query.filter(func.date(getattr(model_cls, filter_name)) == value.date())
                    else:
                        query = query.filter(getattr(model_cls, filter_name) == value)
                return query.all()
            except DatabaseError as e:
                raise MySQLAPIQueryError(f"Failed to query data for {model_cls.__name__}: {e}") from e
