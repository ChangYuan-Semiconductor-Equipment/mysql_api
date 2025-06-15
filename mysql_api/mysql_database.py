# pylint: skip-file
"""Mysql 数据库模块."""
import logging
import os
import pathlib
from logging.handlers import TimedRotatingFileHandler
from typing import Union, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.decl_api import DeclarativeMeta

from mysql_api.exception import MySQLAPIAddError, MySQLAPIQueryError, MySQLAPIDeleteError, MySQLAPIUpdateError


# noinspection SqlNoDataSourceInspection
class MySQLDatabase:
    """MySQLDatabase class."""

    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"

    def __init__(self, user_name: str, password: str, database_name: str = "cyg", host: str = "127.0.0.1", port: int = 3306):
        """MySQLDatabase 构造方法.

        Args:
            user_name: 用户名.
            password: 密码.
            database_name: 数据库名称.
            host: 数据库 ip 地址.
            port: 数据库端口号.
        """
        self.logger = logging.getLogger(__name__)
        self.engine = create_engine(
            f"mysql+pymysql://{user_name}:{password}@{host}:{port}/{database_name}?charset=utf8mb4",
            pool_size = 5,  # 连接池大小
            max_overflow = 10,  # 最大溢出连接数
            pool_pre_ping = True,  # 执行前检查连接是否有效
            pool_recycle = 3600,  # 1小时后回收连接
            echo = True
        )
        self.session = scoped_session(sessionmaker(bind=self.engine))
        self._file_handler = None  # 保存日志的处理器
        self._initial_log_config()

    def _initial_log_config(self) -> None:
        """日志配置."""
        self._create_log_dir()
        self.logger.addHandler(self.file_handler)  # handler_passive 日志保存到统一文件

    def _check_connection(self):
        """检查数据库连接."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            self.logger.warning(f"Database connection check failed: {e}")
            # 尝试重新建立连接
            self.engine.dispose()

    @property
    def file_handler(self) -> TimedRotatingFileHandler:
        """设置保存日志的处理器, 每隔 24h 自动生成一个日志文件.

        Returns:
            TimedRotatingFileHandler: 返回 TimedRotatingFileHandler 日志处理器.
        """
        if self._file_handler is None:
            self._file_handler = TimedRotatingFileHandler(
                f"{os.getcwd()}/log/mysql.log",
                when="D", interval=1, backupCount=10, encoding="UTF-8"
            )
            self._file_handler.namer = self._custom_log_name
            self._file_handler.setFormatter(logging.Formatter(self.LOG_FORMAT))
        return self._file_handler

    @staticmethod
    def _custom_log_name(log_path: str):
        """自定义新生成的日志名称.

        Args:
            log_path: 原始的日志文件路径.

        Returns:
            str: 新生成的自定义日志文件路径.
        """
        _, suffix, date_str = log_path.split(".")
        new_log_path = f"{os.getcwd()}/log/mysql_{date_str}.{suffix}"
        return new_log_path

    @staticmethod
    def _create_log_dir():
        """判断log目录是否存在, 不存在就创建."""
        log_dir = pathlib.Path(f"{os.getcwd()}/log")
        if not log_dir.exists():
            os.mkdir(log_dir)

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
            raise MySQLAPIAddError(f"Failed to add data to {model_cls.__name__}: {e}") from e

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
            raise MySQLAPIDeleteError(f"Failed to delete data from {model_cls.__name__}: {e}") from e

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
            raise MySQLAPIUpdateError(f"Failed to add data to {model_cls.__name__}: {e}") from e

    def query_data(self, model_cls, filter_dict: Optional[dict] = None) -> list:
        """查询表数据.

        Args:
            model_cls: 数据表模型class.
            filter_dict: 要查询数据的筛选条件, 默认是 None, 则查询表的所有数据.

        Returns:
            list: 返回查询到数据表实例列表.

        Raises:
            MySQLAPIQueryError: 更新数据失败抛出异常.
        """
        self._check_connection()
        try:
            with self.session() as session:
                if filter_dict:
                    model_instance_list = session.query(model_cls).filter_by(**filter_dict).all()
                else:
                    model_instance_list = session.query(model_cls).all()
                real_data_list = []
                for model_instance in model_instance_list:
                    data_dict = model_instance.__dict__
                    data_dict.pop("_sa_instance_state", None)
                    real_data_list.append(data_dict)

                self.logger.info("查询数据为: %s", real_data_list)
                return real_data_list
        except DatabaseError as e:
            raise MySQLAPIQueryError(f"Failed to query data for {model_cls.__name__}: {e}") from e

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
                self.logger.info("查询数据为: %s", real_data_list)
                return real_data_list
        except DatabaseError as e:
            raise MySQLAPIQueryError(f"Failed to join tables: {e}") from e
