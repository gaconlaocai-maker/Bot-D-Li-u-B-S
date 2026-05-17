import re

def remove_vietnamese_accents(text):
    if not text:
        return ""
    accents_map = {
        'a': 'áàảãạăắằẳẵặâấầẩẫậ',
        'A': 'ÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬ',
        'd': 'đ',
        'D': 'Đ',
        'e': 'éèẻẽẹêếềểễệ',
        'E': 'ÉÈẺẼẸÊẾỀỂỄỆ',
        'i': 'íìỉĩị',
        'I': 'ÍÌỈĨỊ',
        'o': 'óòỏõọôốồổỗộơớờởỡợ',
        'O': 'ÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢ',
        'u': 'úùủũụưứừửữự',
        'U': 'ÚÙỦŨỤƯỨỪỬỮỰ',
        'y': 'ýỳỷỹỵ',
        'Y': 'ÝỲỶỸỴ'
    }
    res = text
    for char, accented_chars in accents_map.items():
        for ac in accented_chars:
            res = res.replace(ac, char)
    return res.lower()

def sanitize_slug(slug):
    if not slug:
        return ""
    s = remove_vietnamese_accents(slug)
    s = re.sub(r'[^a-z0-9\-]', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')

def generate_property_slug(title, item_id, current_slug=None):
    if not title:
        return f"ban-dat-{item_id}" if item_id else "ban-dat"
        
    title_lower = title.lower()
    
    # 1. Determine exact property type
    prop_type = "ban-dat"
    if "biệt thự" in title_lower or "villa" in title_lower:
        prop_type = "biet-thu"
    elif "căn hộ" in title_lower or "chung cư" in title_lower or "irista" in title_lower:
        prop_type = "can-ho"
    elif "khách sạn" in title_lower or "hotel" in title_lower:
        prop_type = "khach-san"
    elif "homestay" in title_lower:
        prop_type = "homestay"
    elif "nhà mặt phố" in title_lower or "nha mat pho" in title_lower or "nhà phố" in title_lower:
        prop_type = "nha-pho"
    elif "nhà riêng" in title_lower or "nha rieng" in title_lower:
        prop_type = "nha-rieng"
    elif "đất công nghiệp" in title_lower or "dat cong nghiep" in title_lower or "ccn" in title_lower:
        prop_type = "dat-cong-nghiep"
    elif "đất thương mại" in title_lower or "dat thuong mai" in title_lower:
        prop_type = "dat-thuong-mai"
    elif "đất nền" in title_lower or "dat nen" in title_lower:
        prop_type = "dat-nen"
    elif "đất thổ cư" in title_lower or "dat tho cu" in title_lower or "thổ cư" in title_lower:
        prop_type = "dat-tho-cu"
        
    # 2. Location extraction
    location = ""
    locations_dict = {
        "ta-phin": ["tả phìn", "ta phin"],
        "ta-van": ["tả van", "ta van"],
        "muong-hoa": ["mường hoa", "muong hoa"],
        "sa-pa": ["sa pa", "sapa"],
        "y-ty": ["y tý", "y ty"],
        "bat-xat": ["bát xát", "bat xat"],
        "au-lau": ["âu lâu", "au lau"],
        "yen-bai": ["yên bái", "yen bai"],
        "nghia-lo": ["nghĩa lộ", "nghia lo"],
        "lao-cai": ["lào cai", "lao cai"],
        "tang-loong": ["tằng loỏng", "tang loong"],
        "mau-a": ["mậu a", "mau a"]
    }
    for loc_key, loc_vals in locations_dict.items():
        if any(val in title_lower for val in loc_vals):
            location = loc_key
            break
    if not location:
        location = "lao-cai"
        
    # Brand/Project Identity Check
    identity = ""
    if "jade hill" in title_lower or "jade-hill" in title_lower:
        identity = "jade-hill"
    elif "irista" in title_lower:
        identity = "irista-hill"
    elif "grand flamant" in title_lower:
        identity = "grand-flamant"
        
    # 3. Area normalization (thousands separator, e.g. 1.640m² -> 1640m)
    area = ""
    area_match = re.search(r'(\d+[\.,]\d+|\d+)\s*(?:m²|m2|m\b|ha\b|héc\b|hecta\b)', title, re.IGNORECASE)
    if area_match:
        val = area_match.group(1)
        if '.' in val or ',' in val:
            val_clean = re.sub(r'[\.,]', '', val)
            if len(val_clean) >= 4:
                area = f"{val_clean}m"
            else:
                val_clean = val.replace(',', '.').replace('.', '-')
                area = f"{val_clean}m"
        else:
            unit_match = re.search(r'\d+\s*(ha\b|héc\b|hecta\b)', title, re.IGNORECASE)
            if unit_match:
                area = f"{val}ha"
            else:
                area = f"{val}m"
                
    # 4. Features extraction (safeguarded against duplicate concepts)
    feature = ""
    is_tho_cu = "tho-cu" in prop_type
    
    if "2 mặt tiền" in title_lower or "2 mat tien" in title_lower:
        feature = "2-mat-tien"
    elif "mặt tiền" in title_lower or "mat tien" in title_lower:
        mt_match = re.search(r'mặt tiền\s*(\d+)\s*m', title_lower)
        if mt_match:
            feature = f"mat-tien-{mt_match.group(1)}m"
        else:
            feature = "mat-tien"
    elif "1 phòng ngủ" in title_lower or "1pn" in title_lower:
        feature = "1pn"
    elif "7 phòng ngủ" in title_lower or "7pn" in title_lower:
        feature = "7pn"
    elif "5 phòng ngủ" in title_lower or "5pn" in title_lower:
        feature = "5pn"
    elif ("full thổ cư" in title_lower or "100% thổ cư" in title_lower) and not is_tho_cu:
        feature = "full-tho-cu"
        
    # 5. Assemble slug
    parts = []
    if identity:
        parts.append(prop_type)
        parts.append(identity)
        parts.append(location)
    else:
        parts.append(prop_type)
        parts.append(location)
        
    if area:
        parts.append(area)
    if feature:
        parts.append(feature)
        
    base_slug = "-".join([sanitize_slug(p) for p in parts if p])
    base_slug = sanitize_slug(base_slug)
    
    # Keep the trailing ID or generate one
    trailing_id = ""
    if current_slug:
        match = re.search(r'-(\d+)$', current_slug)
        if match:
            trailing_id = match.group(1)
    if not trailing_id and item_id:
        trailing_id = str(item_id)
        
    new_slug = f"{base_slug}-{trailing_id}" if trailing_id else base_slug
    new_slug = sanitize_slug(new_slug)
    
    # Safe limit
    if len(new_slug) > 85:
        excess = len(new_slug) - 80
        if len(base_slug) > excess:
            base_slug = base_slug[:len(base_slug)-excess]
            new_slug = f"{sanitize_slug(base_slug)}-{trailing_id}" if trailing_id else sanitize_slug(base_slug)
            
    return new_slug
