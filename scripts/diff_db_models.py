"""对比线上数据库实际列 vs 模型定义列，输出所有差异（缺失/多余列）。

在 api 容器内运行：poetry run python scripts/diff_db_models.py
用 asyncpg 反射（容器内已装）。
"""
import asyncio
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import get_settings
from src.api.models.db_models import Base


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)

    async with engine.connect() as conn:
        def _inspect(sync_conn):
            return inspect(sync_conn)
        insp = await conn.run_sync(_inspect)
        db_tables = set(await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names())))

    # 重新用同步 inspect 取列（上面 insp 在 run_sync 内有效，这里重新反射）
    async with engine.connect() as conn:
        table_cols = {}
        for tname in db_tables:
            cols = await conn.run_sync(
                lambda sync_conn, t=tname: [c["name"] for c in inspect(sync_conn).get_columns(t)]
            )
            table_cols[tname] = set(cols)

    await engine.dispose()

    model_tables = {t.name: set(c.name for c in t.columns) for t in Base.metadata.sorted_tables}

    print("=== 模型有、数据库缺的列（会导致 500）===")
    missing_any = False
    for tname, model_cols in sorted(model_tables.items()):
        if tname not in db_tables:
            print(f"  [缺整表] {tname}")
            missing_any = True
            continue
        db_cols = table_cols.get(tname, set())
        missing = model_cols - db_cols
        if missing:
            missing_any = True
            print(f"  {tname}: 缺 {sorted(missing)}")
    if not missing_any:
        print("  (无缺失)")

    print()
    print("=== 数据库有、模型没定义的列（通常无害）===")
    for tname in sorted(db_tables):
        if tname == "alembic_version":
            continue
        if tname not in model_tables:
            print(f"  [模型无此表] {tname}")
            continue
        db_cols = table_cols.get(tname, set())
        model_cols = model_tables[tname]
        extra = db_cols - model_cols
        if extra:
            print(f"  {tname}: 多 {sorted(extra)}")


if __name__ == "__main__":
    asyncio.run(main())
