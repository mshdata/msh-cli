import duckdb
conn = duckdb.connect("msh.duckdb")
print("Tables:")
print(conn.execute("SHOW TABLES").fetchall())
print("Schemas:")
print(conn.execute("SELECT schema_name FROM information_schema.schemata").fetchall())
try:
    print("Content of msh_raw.dummy_source:")
    print(conn.execute("SELECT * FROM msh_raw.dummy_source").fetchall())
except Exception as e:
    print(f"Error querying msh_raw.dummy_source: {e}")

try:
    print("Content of revenue:")
    print(conn.execute("SELECT * FROM revenue").fetchall())
except Exception as e:
    print(f"Error querying revenue: {e}")

conn.close()
