# pylint: skip-file
"""Mysql 数据库模块."""
from typing import Union, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.decl_api import DeclarativeMeta

from mysql_api import exception


# noinspection SqlNoDataSourceInspection
class MySQLDatabase:
    """MySQLDatabase class."""

    def __init__(
            self, user_name: str, password: str, database_name: str = "big_beauty",
            host: str = "127.0.0.1", port: int = 3306, echo: bool = False
    ):
        """MySQLDatabase 构造方法.

        Args:
            user_name: 用户名.
            password: 密码.
            database_name: 数据库名称.
            host: 数据库 ip 地址.
            port: 数据库端口号.
        """
        self.engine = create_engine(
            f"mysql+pymysql://{user_name}:{password}@{host}:{port}/{database_name}?charset=utf8mb4",
            pool_size = 5,  # 连接池大小
            max_overflow = 10,  # 最大溢出连接数
            pool_pre_ping = True,  # 执行前检查连接是否有效
            pool_recycle = 3600,  # 1小时后回收连接
            echo = echo
        )
        self.session = scoped_session(sessionmaker(bind=self.engine))

    def _check_connection(self):
        """检查数据库连接.

        Raises:
            MySQLAPIConnectionError: 连接失败异常.
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except OperationalError as e:
            # 释放引擎资源
            self.engine.dispose()
            raise exception.MySQLAPIConnectionError(f"连接失败: {str(e)}") from e

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
        engine = create_engine(f"mysql+pymysql://{user_name}:{password}@{host}:{port}", echo=False)
        with engine.connect() as con:
            con.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name}"))

    def create_table(self, declarative_base: DeclarativeMeta):
        """在执行数据库下创建数据表.

        Args:
            declarative_base: SQLAlchemy的declarative_base对象.
        """
        declarative_base.metadata.create_all(self.engine)

    def add_data(self, model_cls, data_list: list[dict[str, Union[int, float, str]]]):
        """向指定数据表添加数据.

        Args:
            model_cls: 数据表模型class.
            data_list: 要添加的数据列表, 每行数据是一个字典, 列表下有几个字典代表要写入多少行数据.

        Raises:
            MySQLAPIAddError: 添加数据失败抛出异常.
        """
        self._check_connection()
        try:
            with self.session() as session:
                new_instances = [model_cls(**item) for item in data_list]
                session.add_all(new_instances)
                session.commit()
        except DatabaseError as e:
            session.rollback()
            raise exception.MySQLAPIAddError(f"Failed to add data to {model_cls.__name__}: {str(e)}") from e

    def delete_data(self, model_cls, filter_dict: Optional[dict] = None):
        """删除指定表里的数据.

        Args:
            model_cls: 数据表模型class.
            filter_dict: 要删除数据的筛选条件, 默认是 None, 则删除所有数据.

        Raises:
            MySQLAPIDeleteError: 删除数据失败抛出异常.
        """
        self._check_connection()
        try:
            with self.session() as session:
                if filter_dict:
                    session.query(model_cls).filter_by(**filter_dict).delete()
                else:
                    session.execute(text(f"TRUNCATE TABLE {model_cls.__tablename__}"))
                session.commit()
        except DatabaseError as e:
            session.rollback()
            raise exception.MySQLAPIDeleteError(f"Failed to delete data from {model_cls.__name__}: {str(e)}") from e

    def update_data(self, model_cls, update_values: dict, filter_dict: Optional[dict] = None):
        """更新数据表的数据.

        Args:
            model_cls: 数据表模型class.
            update_values: 要更新的字段值.
            filter_dict: 要更新数据的筛选条件, 默认是 None, 则更新所有行数据的列为指定值.

        Raises:
            MySQLAPIUpdateError: 更新数据失败抛出异常.
        """
        self._check_connection()
        try:
            with self.session() as session:
                if filter_dict:
                    session.query(model_cls).filter_by(**filter_dict).update(update_values)
                else:
                    session.query(model_cls).update(update_values)
                session.commit()
        except DatabaseError as e:
            session.rollback()
            raise exception.MySQLAPIUpdateError(f"Failed to add data to {model_cls.__name__}: {str(e)}") from e

    def query_data_join(self, model_cls_a, model_cls_b, column_name, filter_dict: dict) -> list:
        """连接 model_cls_a 和 model_cls_b 表, 以 model_cls_a 表的数据个数为准.

        Args:
            model_cls_a: 左表模型.
            model_cls_b: 右表模型.
            column_name: 左右表连接键的列名.
            filter_dict: 要查询数据的筛选条件, 默认是 None, 则查询表的所有数据.

        Returns:
            list: 连接后的结果，以字典形式返回.

        Raises:
            MySQLAPIQueryError: 查询失败抛出异常.
        """
        self._check_connection()
        try:
            with self.session() as session:
                key_a = getattr(model_cls_a, column_name)
                key_b = getattr(model_cls_b, column_name)
                query = session.query(model_cls_a, model_cls_b).join(model_cls_a, key_a == key_b, isouter=True)
                model_instance_list = query.filter_by(**filter_dict).all()
                real_data_list = []
                for model_instance in model_instance_list:
                    _temp_dict = {}
                    model_cls_a_dict = model_instance[0].__dict__
                    model_cls_b_dict = model_instance[1].__dict__
                    model_cls_a_dict.pop("_sa_instance_state", None)
                    model_cls_b_dict.pop("_sa_instance_state", None)
                    _temp_dict.update(model_cls_a_dict)
                    _temp_dict.update(model_cls_b_dict)
                    real_data_list.append(_temp_dict)
                return real_data_list
        except DatabaseError as e:
            raise exception.MySQLAPIQueryError(f"Failed to join tables: {str(e)}") from e

    def query_data(self, model_cls, filter_dict: Optional[dict] = None, columns_return: list = None) -> list:
        """查询表数据.

        Args:
            model_cls: 数据表模型 class.
            filter_dict: 要查询数据的筛选条件, 默认是 None, 则查询表的所有数据.
            columns_return: 要返回的列名.

        Returns:
            list: 返回查询到数据表实例列表.

        Raises:
            MySQLAPIQueryError: 查询数据失败抛出异常.
        """
        self._check_connection()
        column_filter = [getattr(model_cls, column_name) for column_name in columns_return] if columns_return else [model_cls]
        try:
            with self.session() as session:
                if filter_dict:
                    model_instance_list = session.query(*column_filter).filter_by(**filter_dict).all()
                else:
                    model_instance_list = session.query(*column_filter).all()

                if columns_return:
                    return [dict(zip(columns_return, value_tuple)) for value_tuple in model_instance_list]

                real_data_list = []
                for model_instance in model_instance_list:
                    data_dict = model_instance.__dict__
                    data_dict.pop("_sa_instance_state", None)
                    real_data_list.append(data_dict)
                return real_data_list
        except DatabaseError as e:
            raise exception.MySQLAPIQueryError(f"Failed to query data for {model_cls.__name__}: {str(e)}") from e

    def query_data_in(
            self, model_cls, column_name: str, column_values: list, filter_dict: Optional[dict] = None,
            columns_return: list = None
    ) -> list:
        """查询表数据, 指定列的值在筛选列表里.

        Args:
            model_cls: 数据表模型class.
            column_name: 指定列名.
            column_values: 要筛选的值列表.
            filter_dict: 要查询数据的筛选条件, 默认是 None, 则查询表的所有数据.
            columns_return: 要返回的列名.

        Returns:
            list: 返回查询到数据表实例列表.

        Raises:
            MySQLAPIQueryError: 查询数据失败抛出异常.
        """
        self._check_connection()
        column_filter = [getattr(model_cls, column_name) for column_name in columns_return] if columns_return  else [model_cls]
        try:
            with self.session() as session:
                query_instance = session.query(*column_filter).filter(getattr(model_cls, column_name).in_(column_values))
                if filter_dict:
                    model_instance_list = query_instance.filter_by(**filter_dict).all()
                else:
                    model_instance_list = query_instance.all()

                if columns_return:
                    return [dict(zip(columns_return, value_tuple)) for value_tuple in model_instance_list]

                real_data_list = []
                for model_instance in model_instance_list:
                    data_dict = model_instance.__dict__
                    data_dict.pop("_sa_instance_state", None)
                    real_data_list.append(data_dict)
                return real_data_list
        except DatabaseError as e:
            raise exception.MySQLAPIQueryError(f"Failed to query data for {model_cls.__name__}: {str(e)}") from e
