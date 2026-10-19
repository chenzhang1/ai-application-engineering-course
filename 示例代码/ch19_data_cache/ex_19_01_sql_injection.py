# EX-19-01 | SQL 注入：字符串拼接 vs 参数化查询的真实对照（sqlite3 内存库）
# 运行：python3 示例代码/ch19_data_cache/ex_19_01_sql_injection.py
import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, password TEXT)")
    conn.executemany("INSERT INTO users (name, password) VALUES (?, ?)",
                     [("alice", "s3cret!"), ("bob", "hunter2")])
    conn.commit()

    # 模拟攻击者输入：注释掉密码条件 + 永真化（经典 payload，-- 是 SQL 行注释）
    evil_input = "' OR '1'='1' --"

    # ── 写法一（错误示范）：f-string 拼接——输入被当成了 SQL 代码 ────────────
    sql_vuln = f"SELECT id, name FROM users WHERE name = '{evil_input}' AND password = 'whatever'"
    rows_vuln = conn.execute(sql_vuln).fetchall()
    print(f"[拼接查询] 生成的 SQL：{sql_vuln}")
    print(f"[拼接查询] 返回 {len(rows_vuln)} 行 → 密码校验被 -- 注释，全表用户泄露！")
    for r in rows_vuln:
        print(f"    泄露：id={r[0]} name={r[1]}")

    # 教学插叙：不带注释的永真 payload（' OR '1'='1）其实防不住这一句——
    # AND 优先级高于 OR，密码条件仍然生效，返回 0 行。写注入 payload 也要"对齐语法树"。
    naive = conn.execute(
        "SELECT id FROM users WHERE name = '' OR '1'='1' AND password = 'whatever'").fetchall()
    print(f"[教学] 朴素永真 payload 返回 {len(naive)} 行（AND 优先级救了它，但别指望攻击者写错）")

    # ── 写法二（正确）：参数化查询——输入永远是"数据"，不进入 SQL 解析器 ──────
    sql_safe = "SELECT id, name FROM users WHERE name = ? AND password = ?"
    rows_safe = conn.execute(sql_safe, (evil_input, "whatever")).fetchall()
    print(f"[参数化]   同样的恶意输入 → 返回 {len(rows_safe)} 行（数据库只找一个名字恰好"
          f"为 \"' OR '1'='1\" 的用户）")

    # ── 为什么参数化能防住：预编译时 SQL 结构已定型，? 的值改变不了语法树 ────
    conn.execute("DROP TABLE IF EXISTS log")
    conn.execute("CREATE TABLE log (msg TEXT)")
    conn.execute("INSERT INTO log (msg) VALUES ('hello')")
    conn.commit()
    # sqlite 的 execute() 单语句天然安全；但 executescript() 允许多语句——
    # 拼接进 executescript 的输入可以"夹带"第二条 SQL：
    payload = "x'); DELETE FROM log; --"
    script = f"INSERT INTO log (msg) VALUES ('{payload}')"
    conn.executescript(script)
    remain = conn.execute("SELECT count(*) FROM log").fetchone()[0]
    print(f"[升级危害] executescript 拼接被夹带 DELETE：执行后 log 表剩 {remain} 行（原 1 行被删空）")
    conn.close()


if __name__ == "__main__":
    main()
