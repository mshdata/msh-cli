import duckdb
conn = duckdb.connect("msh.duckdb")
print("Tables:")
print(conn.execute("SHOW TABLES").fetchall())
print("Views:")
print(conn.execute("SELECT table_name FROM information_schema.views WHERE table_schema='main'").fetchall())
conn.close()
