# signals.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.db import connections, ProgrammingError
from django.apps import apps
import logging
logger = logging.getLogger(__name__)

# 定义一个函数来创建分表
def create_partition_tables_for_model(model, num_partitions):
    # 创建连接
    connection = connections['default']

    # 获取源表的结构
    source_table_name = model._meta.db_table
    source_table_columns = [col.name for col in model._meta.concrete_fields]

    # 遍历每个分区
    for i in range(1, num_partitions + 1):
        table_name = f"{source_table_name}_{i}"

        # 检查是否已经有这样的表
        if table_name not in connection.introspection.table_names():
            # 构建 SQL 语句
            column_definitions = ',\n'.join([
                f"{col} {connection.introspection.get_field_type(col, model._meta.get_field(col))}"
                for col in source_table_columns
            ])

            # 构建 SQL 语句
            sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {column_definitions}
            );
            """

            with connection.cursor() as cursor:
                try:
                    cursor.execute(sql)
                    print(f"Table {table_name} created successfully.")
                except ProgrammingError as e:
                    print(f"Error creating table {table_name}: {e}")

@receiver(post_migrate)
def create_partition_tables(sender, **kwargs):
    # 获取所有模型
    models = apps.get_models()

    # 遍历每个模型
    for model in models:
        # 只处理需要分表的模型
        if hasattr(model, 'num_partitions'):
            # 创建分表
            logger.info(f"Creating partition tables for {model._meta.db_table}...")
            create_partition_tables_for_model(model, model.num_partitions)

    logger.info("All tables created successfully.")