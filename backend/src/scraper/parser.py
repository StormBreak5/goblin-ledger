import struct
import gzip

def parse_item_state(data: bytes) -> dict:
    """
    Parses The Undermine Exchange item state binary format.
    Returns a dictionary containing the item's auction, snapshot, and daily statistics.
    """
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
    
    # Time multipliers
    n_mult = 60000     # Minutes to milliseconds
    a_mult = 86400000  # Days to milliseconds

    snapshot = read_u32() * n_mult
    price = read_u32() * 100
    quantity = read_u32()
    
    # 1. Current Auctions
    auctions = []
    auctions_len = read_u16()
    for _ in range(auctions_len):
        auc_price = read_u32() * 100
        auc_quant = read_u32()
        auctions.append({'price': auc_price, 'quantity': auc_quant})
    
    # 2. Specifics (Item variations, modifiers, bonuses)
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
        
    # 3. Snapshots (Recent history)
    snapshots = {}
    snapshots_len = read_u16()
    for _ in range(snapshots_len):
        snap_time = read_u32() * n_mult
        snap_price = read_u32() * 100
        snap_quant = read_u32()
        snapshots[snap_time] = {'snapshot': snap_time, 'price': snap_price, 'quantity': snap_quant}
        
    # 4. Daily aggregates (Long-term history)
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

def decompress_and_parse(data: bytes) -> dict:
    """Decompress gzip payload if needed, then parse."""
    try:
        data = gzip.decompress(data)
    except gzip.BadGzipFile:
        pass # Probably uncompressed already
    return parse_item_state(data)
