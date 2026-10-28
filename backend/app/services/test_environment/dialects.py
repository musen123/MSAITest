"""被测库多类型直连的「方言」抽象（数据库能力中心）。

把每种数据库的差异集中在一处——**连接驱动 / 占位符风格 / 连通性探测 SQL / 表结构内省 /
分页语法 / 标识符引用 / 行→字典归一**。三个接缝统一按 ``db_type`` 取方言：

- 连通性测试（database_service._test_*）
- 表结构内省 + 分页取数（database_service.get_schema / get_table_rows）
- 脚本/SQL 节点执行（script_db）

设计取向与既有 MySQL 实现一致：**同步 DBAPI2 驱动 + 即用即弃连接**（无池），脚本侧走
autocommit；只读内省/取数走普通连接。所有驱动均为纯 wheel、免系统依赖
（psycopg2-binary / oracledb thin / pymssql 自带 FreeTDS）。

新增方言（PostgreSQL/Oracle/SQLServer）本机无真实例，逻辑经单测覆盖，真连待真实例验证。
"""

from __future__ import annotations

import re
from typing import Any

# 具名占位符 ${{param}}（与平台其它占位符同语法）——渲染为各驱动的参数占位符（防注入）
_SQL_PARAM_RE = re.compile(r"\$\{\{\s*([^{}]+?)\s*\}\}")


class Dialect:
    """方言基类。子类实现连接/内省/分页；共性（占位符渲染、行归一）在基类。

    ``paramstyle``：``"format"`` → 占位符 ``%s``（pymysql/psycopg2/pymssql）；
    ``"numeric"`` → ``:1、:2``（oracledb）。渲染统一收集**按出现顺序**的位置参数列表。
    """

    name: str = ""
    paramstyle: str = "format"  # "format"(%s) | "numeric"(:1)

    # ---- 连接 ----
    def connect(self, cfg: dict, *, autocommit: bool = False, timeout: int = 10):
        raise NotImplementedError

    # ---- 连通性探测 ----
    def test_query(self) -> str:
        return "SELECT 1"

    # ---- 占位符渲染（${{name}} → 驱动占位符） ----
    def placeholder(self, index: int) -> str:
        """第 index 个占位符（从 1 起）的文本。"""
        return ":%d" % index if self.paramstyle == "numeric" else "%s"

    def render(self, sql_text: str, params: dict | None) -> tuple[str, list]:
        """把 ``${{param}}`` 渲染为占位符并**按出现顺序**收集参数值。

        缺参数抛 KeyError（清晰指出缺哪个）。无占位符则原样返回、空参数列表。
        """
        params = params or {}
        ordered: list = []
        missing: list[str] = []

        def _sub(m: "re.Match[str]") -> str:
            key = m.group(1)
            if key not in params:
                missing.append(key)
                return m.group(0)
            ordered.append(params[key])
            return self.placeholder(len(ordered))

        rendered = _SQL_PARAM_RE.sub(_sub, sql_text or "")
        if missing:
            raise KeyError(f"SQL 缺少参数：{', '.join(sorted(set(missing)))}")
        return rendered, ordered

    # ---- 标识符引用 ----
    def quote_ident(self, ident: str) -> str:
        """引用表名/列名。默认双引号（PG/Oracle/标准 SQL）；转义内部引号。"""
        return '"' + str(ident).replace('"', '""') + '"'

    # ---- 分页取数 ----
    def page_query(self, table: str, limit: int, offset: int) -> tuple[str, list]:
        """构造分页 ``SELECT *``（表名已过白名单，此处仅负责引用 + 分页语法）。

        返回 (sql, 位置参数列表)。``limit`` 由调用方决定（通常传 want+1 判 has_more）。
        默认 LIMIT/OFFSET（MySQL/PG）。
        """
        return (
            f"SELECT * FROM {self.quote_ident(table)} "
            f"LIMIT {self.placeholder(1)} OFFSET {self.placeholder(2)}",
            [limit, offset],
        )

    # ---- 行归一 ----
    def rows(self, cur) -> list[dict]:
        """fetchall → list[dict]。"""
        return self.rows_from(cur, cur.fetchall())

    def rows_from(self, cur, raw: list) -> list[dict]:
        """把**已取出**的原始行转为 list[dict]（供 fetchmany 限量场景，避免全量拉取）。

        默认假设行已是字典（DictCursor / RealDictCursor / as_dict）；以元组产出的驱动
        （oracledb）在子类按 cursor.description 覆盖。"""
        return [dict(r) for r in raw]

    def new_cursor(self, conn):
        """产出字典行的游标（供内省/取数用）。默认 conn.cursor()。"""
        return conn.cursor()

    # ---- 表结构内省 ----
    def introspect(self, conn, database: str) -> dict:
        """返回 ``{"database": 库名, "tables": [{name, comment, columns:[
        {name, type, nullable, key, comment}]}]}``。子类实现各自的内省 SQL。"""
        raise NotImplementedError

    # 内省结果拼装（子类拿到 table 行 + column 行后共用此组装）
    @staticmethod
    def _assemble(database: str, table_rows: list[dict], col_rows: list[dict]) -> dict:
        cols_by_table: dict[str, list] = {}
        for r in col_rows:
            cols_by_table.setdefault(r["t"], []).append(
                {
                    "name": r["n"],
                    "type": r["ty"],
                    "nullable": bool(r["nu"]),
                    "key": r["k"] or "",
                    "comment": r["cm"] or "",
                }
            )
        tables = [
            {
                "name": r["t"],
                "comment": r["c"] or "",
                "columns": cols_by_table.get(r["t"], []),
            }
            for r in table_rows
        ]
        return {"database": database, "tables": tables}


class MySQLDialect(Dialect):
    name = "mysql"
    paramstyle = "format"

    def connect(self, cfg: dict, *, autocommit: bool = False, timeout: int = 10):
        import pymysql

        return pymysql.connect(
            host=cfg["host"],
            port=int(cfg["port"]),
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            charset=cfg.get("charset") or "utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=autocommit,
            connect_timeout=timeout,
            **(cfg.get("params") or {}),
        )

    def quote_ident(self, ident: str) -> str:
        return "`" + str(ident).replace("`", "``") + "`"

    def introspect(self, conn, database: str) -> dict:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT TABLE_NAME AS t, TABLE_COMMENT AS c "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME",
                (database,),
            )
            table_rows = list(cur.fetchall())
            cur.execute(
                "SELECT TABLE_NAME AS t, COLUMN_NAME AS n, COLUMN_TYPE AS ty, "
                "IS_NULLABLE AS nu, COLUMN_KEY AS k, COLUMN_COMMENT AS cm "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME, ORDINAL_POSITION",
                (database,),
            )
            col_rows = list(cur.fetchall())
        # MySQL 的 nullable 是 'YES'/'NO' → 归一为 bool
        for r in col_rows:
            r["nu"] = r["nu"] == "YES"
        return self._assemble(database, table_rows, col_rows)


class PostgreSQLDialect(Dialect):
    name = "postgresql"
    paramstyle = "format"  # psycopg2 = pyformat，%s 位置参数通用

    def connect(self, cfg: dict, *, autocommit: bool = False, timeout: int = 10):
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            host=cfg["host"],
            port=int(cfg["port"]),
            user=cfg["user"],
            password=cfg["password"],
            dbname=cfg["database"],
            connect_timeout=timeout,
            cursor_factory=psycopg2.extras.RealDictCursor,
            **(cfg.get("params") or {}),
        )
        conn.autocommit = autocommit
        return conn

    def _schema(self, cfg_params: Any) -> str:
        # PG 的 database 是库，表在 schema 下；默认 public，可经 connection_params.schema 覆盖
        if isinstance(cfg_params, dict) and cfg_params.get("schema"):
            return str(cfg_params["schema"])
        return "public"

    def introspect(self, conn, database: str) -> dict:
        # schema 从连接参数取（内省不持有 cfg，这里默认 public；如需自定义在 get_schema 侧传）
        schema = "public"
        with conn.cursor() as cur:
            # 表 + 表注释（走 pg_class.oid，避免 regclass 转换在特殊表名下抛错）
            cur.execute(
                "SELECT c.relname AS t, COALESCE(obj_description(c.oid), '') AS c "
                "FROM pg_catalog.pg_class c "
                "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relkind IN ('r','p') AND n.nspname = %s "
                "ORDER BY c.relname",
                (schema,),
            )
            table_rows = [dict(r) for r in cur.fetchall()]
            # 列 + 类型 + 可空 + 注释 + 主键
            cur.execute(
                "SELECT c.relname AS t, a.attname AS n, "
                "pg_catalog.format_type(a.atttypid, a.atttypmod) AS ty, "
                "(NOT a.attnotnull) AS nu, "
                "COALESCE(pg_catalog.col_description(c.oid, a.attnum), '') AS cm, "
                "CASE WHEN pk.attnum IS NOT NULL THEN 'PRI' ELSE '' END AS k "
                "FROM pg_catalog.pg_class c "
                "JOIN pg_catalog.pg_namespace nsp ON nsp.oid = c.relnamespace "
                "JOIN pg_catalog.pg_attribute a "
                "  ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped "
                "LEFT JOIN ("
                "  SELECT conrelid, unnest(conkey) AS attnum "
                "  FROM pg_catalog.pg_constraint WHERE contype='p'"
                ") pk ON pk.conrelid = c.oid AND pk.attnum = a.attnum "
                "WHERE c.relkind IN ('r','p') AND nsp.nspname = %s "
                "ORDER BY c.relname, a.attnum",
                (schema,),
            )
            col_rows = [dict(r) for r in cur.fetchall()]
        return self._assemble(database, table_rows, col_rows)


class SQLServerDialect(Dialect):
    name = "sqlserver"
    paramstyle = "format"  # pymssql = pyformat，%s 位置参数通用

    def connect(self, cfg: dict, *, autocommit: bool = False, timeout: int = 10):
        import pymssql

        return pymssql.connect(
            server=cfg["host"],
            port=str(cfg["port"]),
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            timeout=timeout + 20,  # 查询超时
            login_timeout=timeout,  # 连接超时
            autocommit=autocommit,
            **(cfg.get("params") or {}),
        )

    def new_cursor(self, conn):
        return conn.cursor(as_dict=True)

    def quote_ident(self, ident: str) -> str:
        return "[" + str(ident).replace("]", "]]") + "]"

    def page_query(self, table: str, limit: int, offset: int) -> tuple[str, list]:
        # SQL Server 的 OFFSET/FETCH 必须带 ORDER BY；无自然序时用 (SELECT NULL) 占位
        return (
            f"SELECT * FROM {self.quote_ident(table)} "
            f"ORDER BY (SELECT NULL) OFFSET {self.placeholder(1)} ROWS "
            f"FETCH NEXT {self.placeholder(2)} ROWS ONLY",
            [offset, limit],
        )

    def introspect(self, conn, database: str) -> dict:
        cur = conn.cursor(as_dict=True)
        try:
            cur.execute(
                "SELECT TABLE_NAME AS t, '' AS c "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE='BASE TABLE' AND TABLE_CATALOG=%s "
                "ORDER BY TABLE_NAME",
                (database,),
            )
            table_rows = list(cur.fetchall())
            cur.execute(
                "SELECT c.TABLE_NAME AS t, c.COLUMN_NAME AS n, c.DATA_TYPE AS ty, "
                "c.IS_NULLABLE AS nu, '' AS cm, "
                "CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PRI' ELSE '' END AS k "
                "FROM INFORMATION_SCHEMA.COLUMNS c "
                "LEFT JOIN ("
                "  SELECT ku.TABLE_NAME, ku.COLUMN_NAME "
                "  FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "  JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku "
                "    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME "
                "  WHERE tc.CONSTRAINT_TYPE='PRIMARY KEY'"
                ") pk ON pk.TABLE_NAME = c.TABLE_NAME AND pk.COLUMN_NAME = c.COLUMN_NAME "
                "WHERE c.TABLE_CATALOG=%s "
                "ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION",
                (database,),
            )
            col_rows = list(cur.fetchall())
        finally:
            cur.close()
        for r in col_rows:
            r["nu"] = r["nu"] == "YES"
        return self._assemble(database, table_rows, col_rows)


class OracleDialect(Dialect):
    name = "oracle"
    paramstyle = "numeric"  # oracledb = named/numeric，:1、:2

    def connect(self, cfg: dict, *, autocommit: bool = False, timeout: int = 10):
        import oracledb  # thin 模式，无需 Instant Client

        params = cfg.get("params") or {}
        # database 默认按 service_name 解析；可经 connection_params.sid 指定 SID
        if isinstance(params, dict) and params.get("sid"):
            dsn = oracledb.makedsn(cfg["host"], int(cfg["port"]), sid=params["sid"])
        else:
            dsn = oracledb.makedsn(
                cfg["host"], int(cfg["port"]), service_name=cfg["database"]
            )
        extra = {
            k: v
            for k, v in params.items()
            if k not in ("sid", "service_name", "schema")
        }
        conn = oracledb.connect(
            user=cfg["user"],
            password=cfg["password"],
            dsn=dsn,
            **extra,
        )
        conn.autocommit = autocommit
        return conn

    def test_query(self) -> str:
        return "SELECT 1 FROM DUAL"

    def new_cursor(self, conn):
        # oracledb 产出元组 → 由 rows/rows_from 按 description 转 dict
        return conn.cursor()

    def rows_from(self, cur, raw: list) -> list[dict]:
        cols = [d[0] for d in (cur.description or [])]
        return [dict(zip(cols, r)) for r in raw]

    def page_query(self, table: str, limit: int, offset: int) -> tuple[str, list]:
        # Oracle 12c+ 支持 OFFSET/FETCH
        return (
            f"SELECT * FROM {self.quote_ident(table)} "
            f"OFFSET {self.placeholder(1)} ROWS "
            f"FETCH NEXT {self.placeholder(2)} ROWS ONLY",
            [offset, limit],
        )

    def introspect(self, conn, database: str) -> dict:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT t.table_name AS t, NVL(c.comments, '') AS c "
                "FROM user_tables t "
                "LEFT JOIN user_tab_comments c "
                "  ON c.table_name = t.table_name AND c.table_type='TABLE' "
                "ORDER BY t.table_name"
            )
            table_rows = self.rows(cur)
            cur.execute(
                "SELECT col.table_name AS t, col.column_name AS n, col.data_type AS ty, "
                "col.nullable AS nu, NVL(cc.comments, '') AS cm, "
                "CASE WHEN pk.column_name IS NOT NULL THEN 'PRI' ELSE '' END AS k "
                "FROM user_tab_columns col "
                "LEFT JOIN user_col_comments cc "
                "  ON cc.table_name = col.table_name AND cc.column_name = col.column_name "
                "LEFT JOIN ("
                "  SELECT acc.table_name, acc.column_name "
                "  FROM user_constraints ac "
                "  JOIN user_cons_columns acc ON ac.constraint_name = acc.constraint_name "
                "  WHERE ac.constraint_type='P'"
                ") pk ON pk.table_name = col.table_name AND pk.column_name = col.column_name "
                "ORDER BY col.table_name, col.column_id"
            )
            col_rows = self.rows(cur)
        finally:
            cur.close()
        # Oracle 的 nullable 是 'Y'/'N' → 归一为 bool
        for r in col_rows:
            r["nu"] = r["nu"] == "Y"
        return self._assemble(database, table_rows, col_rows)


# db_type（大小写不敏感，含常见别名）→ 方言单例
_DIALECTS: dict[str, Dialect] = {
    "mysql": MySQLDialect(),
    "postgresql": PostgreSQLDialect(),
    "postgres": PostgreSQLDialect(),
    "pgsql": PostgreSQLDialect(),
    "oracle": OracleDialect(),
    "sqlserver": SQLServerDialect(),
    "mssql": SQLServerDialect(),
}

# 关系型（可套 SQL 模型）支持的 db_type 规范名 → 展示名
SUPPORTED_SQL_DB_TYPES = ("MySQL", "PostgreSQL", "Oracle", "SQLServer")


def get_dialect(db_type: str | None) -> Dialect | None:
    """按 db_type 取方言；非关系型/未知返回 None（调用方据此报「暂不支持」）。"""
    return _DIALECTS.get((db_type or "").strip().lower())
