import duckdb
conn = duckdb.connect("msh.duckdb")
print("Content of generic_loader:")
print(conn.execute("SELECT * FROM generic_loader").fetchall())
conn.close()
