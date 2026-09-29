import urllib.request
import gzip
import struct
import json

def parse_item_state(data):
    offset = 0
    def read_u8():
        nonlocal offset
        v = data[offset]
        offset += 1
        return v
    
    def read_u16():
        nonlocal offset
        v = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        return v

    def read_u32():
        nonlocal offset
        v = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4
        return v

    p = read_u8()
    m = True
    h = True
    if p == 3:
        m = False
    elif p == 4:
        h = False
    
    n_mult = 60000
    a_mult = 86400000

    snapshot = read_u32() * n_mult
    price = read_u32() * 100
    quantity = read_u32()
    
    auctions = []
    auctions_len = read_u16()
    for _ in range(auctions_len):
        auc_price = read_u32() * 100
        auc_quant = read_u32()
        auctions.append({'price': auc_price, 'quantity': auc_quant})
    
    specifics = []
    specifics_len = read_u16()
    for _ in range(specifics_len):
        spec_price = read_u32() * 100
        modifiers = {}
        if m:
            mod_len = read_u8()
            for _ in range(mod_len):
                mod_k = read_u16()
                mod_v = read_u32()
                modifiers[mod_k] = mod_v
        else:
            mod_v = read_u8()
            if mod_v:
                modifiers['timewalkerLevel'] = mod_v
        
        bonuses = []
        bonuses_len = read_u8()
        for _ in range(bonuses_len):
            bonuses.append(read_u16())
        
        specifics.append({'price': spec_price, 'modifiers': modifiers, 'bonuses': bonuses})
        
    snapshots = {}
    snapshots_len = read_u16()
    for _ in range(snapshots_len):
        snap_time = read_u32() * n_mult
        snap_price = read_u32() * 100
        snap_quant = read_u32()
        snapshots[snap_time] = {'snapshot': snap_time, 'price': snap_price, 'quantity': snap_quant}
        
    daily = []
    if h:
        daily_len = read_u16()
        for _ in range(daily_len):
            d_snap = read_u16() * a_mult
            d_price = read_u32() * 100
            d_quant = read_u32()
            daily.append({'snapshot': d_snap, 'price': d_price, 'quantity': d_quant})

    return {
        'snapshot': snapshot,
        'price': price,
        'quantity': quantity,
        'auctions': auctions,
        'specifics': specifics,
        'snapshots': list(snapshots.values()),
        'daily': daily
    }

url = 'https://undermine.exchange/data/32512/51/171315.bin'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = gzip.decompress(response.read())
        parsed = parse_item_state(data)
        
        print(f"Parsed {len(data)} bytes successfully.")
        print(f"Current Price: {parsed['price']/10000} gold")
        print(f"Current Quantity: {parsed['quantity']}")
        print(f"Number of auctions: {len(parsed['auctions'])}")
        print(f"Number of specifics: {len(parsed['specifics'])}")
        print(f"Number of snapshots: {len(parsed['snapshots'])}")
        print(f"Number of daily records: {len(parsed['daily'])}")
        
        with open('scratch/171315.json', 'w') as f:
            json.dump(parsed, f, indent=2)
except Exception as e:
    import traceback
    traceback.print_exc()
