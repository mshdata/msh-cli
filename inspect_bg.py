import duckdb
conn = duckdb.connect("msh.duckdb")
print("Tables:")
print(conn.execute("SHOW TABLES").fetchall())
print("Views:")
print(conn.execute("SELECT table_name, view_definition FROM information_schema.views WHERE table_schema='main'").fetchall())

try:
    print("Content of revenue:")
    print(conn.execute("SELECT * FROM revenue").fetchall())
except Exception as e:
    print(f"Error querying revenue: {e}")

conn.close()
