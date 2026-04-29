import duckdb
import glob
from pathlib import Path

def inspect_parquet():
    hot_tier_files = glob.glob("data/hot_tier/*.parquet")
    cache_files = glob.glob("data/cache/*.parquet")
    
    print("=== DUCKDB PARQUET INSPECTION ===\n")
    
    # 1. Inspect Hot Tier (Events)
    if hot_tier_files:
        print(f"Found {len(hot_tier_files)} files in hot_tier. Inspecting combined schema...")
        conn = duckdb.connect(database=':memory:')
        try:
            # Check row count
            count = conn.execute("SELECT COUNT(*) FROM read_parquet('data/hot_tier/*.parquet')").fetchone()[0]
            print(f"Total Rows in Hot Tier: {count:,}")
            
            # Check columns
            print("\nColumns in Hot Tier (Events):")
            columns = conn.execute("DESCRIBE SELECT * FROM read_parquet('data/hot_tier/*.parquet') LIMIT 0").fetchall()
            for col in columns:
                print(f"  - {col[0]:25} ({col[1]})")
                
            # Sample data check
            print("\nSample Data (First row):")
            sample = conn.execute("SELECT * FROM read_parquet('data/hot_tier/*.parquet') LIMIT 1").fetchone()
            print(sample)
            
        except Exception as e:
            print(f"Error inspecting hot_tier: {e}")
        finally:
            conn.close()
    else:
        print("No Parquet files found in data/hot_tier.")

    # 2. Inspect Cache (Forecasts)
    if cache_files:
        print(f"\nFound {len(cache_files)} files in cache. Inspecting {cache_files[0]}...")
        conn = duckdb.connect(database=':memory:')
        try:
            for cf in cache_files:
                print(f"\nFile: {cf}")
                count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{cf}')").fetchone()[0]
                print(f"Total Rows: {count:,}")
                
                print("Columns:")
                columns = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{cf}') LIMIT 0").fetchall()
                for col in columns:
                    print(f"  - {col[0]:25} ({col[1]})")
        except Exception as e:
            print(f"Error inspecting cache: {e}")
        finally:
            conn.close()
    else:
        print("\nNo Parquet files found in data/cache.")

if __name__ == "__main__":
    inspect_parquet()
