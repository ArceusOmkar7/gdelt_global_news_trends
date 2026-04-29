import duckdb
query = "SELECT * FROM read_parquet('data/hot_tier/*.parquet') WHERE GLOBALEVENTID=1299363039"
print(duckdb.execute(query).fetchall())