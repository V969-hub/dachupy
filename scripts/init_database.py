"""
Database initialization script for the private chef booking system.
Creates all tables using SQLAlchemy models or raw SQL script.

Usage:
    python scripts/init_database.py              # Create tables using SQLAlchemy
    python scripts/init_database.py --drop       # Drop and recreate tables
    python scripts/init_database.py --sql        # Execute raw SQL script
    python scripts/init_database.py --verify     # Verify tables exist
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect, create_engine
from app.config import settings

# Expected tables based on models
EXPECTED_TABLES = [
    "users",
    "dishes", 
    "daily_dish_quantities",
    "orders",
    "order_items",
    "reviews",
    "tips",
    "addresses",
    "bindings",
    "notifications",
    "favorites"
]


def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    # Connect to MySQL server without specifying database
    server_url = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/"
    server_engine = create_engine(server_url)
    
    with server_engine.connect() as conn:
        # Create database if not exists
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {settings.DB_NAME} DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci"))
        conn.commit()
        print(f"数据库 '{settings.DB_NAME}' 已创建或已存在")
    
    server_engine.dispose()


def create_tables():
    """Create all database tables using SQLAlchemy models."""
    # First ensure database exists
    create_database_if_not_exists()
    
    # Now import database and models
    from app.database import engine, Base
    from app.models import (
        User, Dish, DailyDishQuantity, Order, OrderItem,
        Review, Tip, Address, Binding, Notification, Favorite
    )
    
    print("使用 SQLAlchemy 创建数据库表...")
    
    # Import all models to ensure they are registered with Base
    models = [
        User, Dish, DailyDishQuantity, Order, OrderItem,
        Review, Tip, Address, Binding, Notification, Favorite
    ]
    
    print(f"已注册模型: {[m.__tablename__ for m in models]}")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("数据库表创建成功!")
    print("\n已创建的表:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")


def drop_tables():
    """Drop all database tables."""
    from app.database import engine, Base
    from app.models import (
        User, Dish, DailyDishQuantity, Order, OrderItem,
        Review, Tip, Address, Binding, Notification, Favorite
    )
    
    print("删除所有数据库表...")
    Base.metadata.drop_all(bind=engine)
    print("所有表已删除!")


def execute_sql_script():
    """Execute the raw SQL initialization script."""
    script_path = os.path.join(os.path.dirname(__file__), "init_db.sql")
    
    if not os.path.exists(script_path):
        print(f"错误: SQL脚本未找到: {script_path}")
        return False
    
    print(f"执行SQL脚本: {script_path}")
    
    # First connect without database to create it
    server_url = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/"
    server_engine = create_engine(server_url)
    
    with open(script_path, "r", encoding="utf-8") as f:
        sql_content = f.read()
    
    # Split by semicolons and execute each statement
    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    
    with server_engine.connect() as conn:
        for i, statement in enumerate(statements):
            # Skip empty statements and comments-only statements
            lines = [l for l in statement.split('\n') if l.strip() and not l.strip().startswith('--')]
            if not lines:
                continue
            try:
                conn.execute(text(statement))
                conn.commit()
            except Exception as e:
                print(f"警告: 语句 {i+1} 执行失败: {str(e)[:100]}")
                continue
    
    server_engine.dispose()
    print("SQL脚本执行成功!")
    return True


def verify_tables():
    """Verify that all expected tables exist in the database."""
    # First ensure database exists
    create_database_if_not_exists()
    
    from app.database import engine
    
    print("验证数据库表...")
    
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    print(f"\n数据库中已存在的表:")
    for table in existing_tables:
        print(f"  - {table}")
    
    # Check for missing tables
    missing_tables = [t for t in EXPECTED_TABLES if t not in existing_tables]
    
    if missing_tables:
        print(f"\n⚠️  缺少的表: {missing_tables}")
        return False
    else:
        print(f"\n✓ 所有 {len(EXPECTED_TABLES)} 个预期的表都已存在!")
        return True


def show_table_info():
    """Show detailed information about each table."""
    # First ensure database exists
    create_database_if_not_exists()
    
    from app.database import engine
    
    print("\n表结构信息:")
    print("=" * 60)
    
    inspector = inspect(engine)
    
    for table_name in EXPECTED_TABLES:
        if table_name not in inspector.get_table_names():
            print(f"\n{table_name}: 未找到")
            continue
            
        print(f"\n{table_name}:")
        columns = inspector.get_columns(table_name)
        for col in columns:
            nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
            print(f"  - {col['name']}: {col['type']} {nullable}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库初始化脚本")
    parser.add_argument(
        "--drop", 
        action="store_true", 
        help="删除所有表后重新创建"
    )
    parser.add_argument(
        "--sql",
        action="store_true",
        help="执行原始SQL脚本而不是使用SQLAlchemy"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="验证所有表是否存在"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="显示详细的表结构信息"
    )
    args = parser.parse_args()
    
    try:
        if args.verify:
            verify_tables()
        elif args.info:
            show_table_info()
        else:
            if args.drop:
                drop_tables()
            
            if args.sql:
                execute_sql_script()
            else:
                create_tables()
            
            # Always verify after creation
            print("\n" + "=" * 60)
            verify_tables()
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
