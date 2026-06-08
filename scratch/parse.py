import urllib.request
import gzip
import struct

url = 'https://undermine.exchange/data/32512/51/171315.bin'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = response.read()
        uncompressed = gzip.decompress(data)
        
        print("Uncompressed size:", len(uncompressed))
        print("First bytes:", list(uncompressed[:30]))
except Exception as e:
    print(e)
