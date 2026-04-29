import duckdb
conn = duckdb.connect(':memory:')
query = """
SELECT EventRootCode, MODE(ActionGeo_CountryCode) 
FROM read_parquet('data/hot_tier/*.parquet') 
WHERE ActionGeo_CountryCode IS NOT NULL AND ActionGeo_CountryCode != ''
GROUP BY EventRootCode
"""
print(conn.execute(query).fetchall())
