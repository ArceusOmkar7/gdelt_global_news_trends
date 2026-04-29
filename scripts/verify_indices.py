import pandas as pd
import httpx
import io
import zipfile

def verify():
    print("Fetching lastupdate.txt...")
    r = httpx.get('http://data.gdeltproject.org/gdeltv2/lastupdate.txt')
    # Filter for export.CSV (Events)
    url = [l for l in r.text.strip().split('\n') if 'export.CSV' in l][0].split()[-1]
    print(f"Target URL: {url}")
    
    zdata = httpx.get(url).content
    with zipfile.ZipFile(io.BytesIO(zdata)) as z:
        fname = z.namelist()[0]
        with z.open(fname) as f:
            # Read first 5 rows to be sure
            df = pd.read_csv(f, sep='\t', header=None, nrows=5)
            
            # Map of few columns we care about
            mapping = {
                "GLOBALEVENTID": 0,
                "SQLDATE": 1,
                "Actor1CountryCode": 7,
                "Actor1Type1Code": 12,
                "Actor2CountryCode": 17,
                "Actor2Type1Code": 22,
                "EventCode": 26,
                "EventBaseCode": 27,
                "EventRootCode": 28,
                "QuadClass": 29,
                "GoldsteinScale": 30,
                "NumMentions": 31,
                "NumSources": 32,
                "AvgTone": 34,
                "ActionGeo_CountryCode": 53,
                "ActionGeo_Lat": 56,
                "ActionGeo_Long": 57,
                "SOURCEURL": 60
            }
            
            print("\nVerification of indices (Row 0):")
            row = df.iloc[0]
            for name, idx in mapping.items():
                val = row[idx] if idx < len(row) else "OUT_OF_BOUNDS"
                print(f"Index {idx:2} | {name:22} | Value: {val}")

if __name__ == "__main__":
    verify()
