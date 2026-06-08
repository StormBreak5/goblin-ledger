import urllib.request
for i in range(256):
    try:
        req = urllib.request.Request(f'https://undermine.exchange/data/32512/{i}/232985.bin', headers={'User-Agent': 'Mozilla/5.0'})
        code = urllib.request.urlopen(req).getcode()
        if code == 200:
            print(f'FOUND: {i}')
            break
    except:
        pass
print('Done')
