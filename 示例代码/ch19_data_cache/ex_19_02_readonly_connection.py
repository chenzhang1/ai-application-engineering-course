# EX-19-02 | 只读防线：PRAGMA query_only 模拟"只读账户"（思想可平移到真实数据库）
# 运行：python3 示例代码/ch19_data_cache/ex_19_02_readonly_connection.py
"""思想：即使代码被注入/有 bug，只读账户也只能"看"，不能"改"。
真实数据库的等价操作（语法以各自官方文档为准，此处仅示意）：
  PostgreSQL: CREATE USER report_ro WITH PASSWORD '...'; GRANT SELECT ON ALL TABLES ... TO report_ro;
  MySQL:      CREATE USER 'report_ro'@'%' IDENTIFIED BY '...'; GRANT SELECT ON shop.* TO 'report_ro'@'%';
AI 应用尤其要记住：LLM 生成的 SQL 也不该用高权限账户执行（ch58 纵深防御的一环）。
"""
import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)")
    conn.execute("INSERT INTO orders (amount) VALUES (99.0)")

    # SQLite 的"只读账户"替代物：连接级开关 query_only（生产等价物是只读账户+白名单）
    conn.execute("PRAGMA query_only = ON")
    print(f"[开关] query_only = {conn.execute('PRAGMA query_only').fetchone()[0]}")

    # 读操作正常
    rows = conn.execute("SELECT id, amount FROM orders WHERE amount > ?", (50,)).fetchall()
    print(f"[读] 参数化查询正常：{rows}")

    # 写操作被数据库本身拒绝——应用层出 bug 也写不进去
    try:
        conn.execute("INSERT INTO orders (amount) VALUES (1.0)")
    except sqlite3.OperationalError as exc:
        print(f"[写] 被数据库拒绝：sqlite3.OperationalError: {exc}")
    try:
        conn.execute("DELETE FROM orders")
    except sqlite3.OperationalError as exc:
        print(f"[写] DELETE 同样被拒绝：{exc}")

    count = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
    print(f"[结果] 数据完好：orders 仍有 {count} 行")
    conn.close()


if __name__ == "__main__":
    main()
