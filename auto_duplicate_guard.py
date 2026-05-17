import os
import json
import re
import time
import difflib
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client
from slug_helper import generate_property_slug

# Load .env relative to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(script_dir, ".env"))

# --- CONNECT TO SUPABASE ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
REDIRECTS_FILE = "c:/Users/SV STORE/Desktop/LaocaiView/laocaiview-main/src/data/slug-redirects.json"

def get_db_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY env variables.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CLEANING & NORMALIZATION HELPERS ---
def clean_vietnamese(s):
    if not s: return ""
    s = str(s).lower()
    s = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', s)
    s = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', s)
    s = re.sub(r'[ìíịỉĩ]', 'i', s)
    s = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', s)
    s = re.sub(r'[ùúụủũưừứựửữ]', 'u', s)
    s = re.sub(r'[ỳýỵỷỹ]', 'y', s)
    s = re.sub(r'đ', 'd', s)
    return s.strip()

# --- DUPLICATE SCORE CALCULATION (PHẦN A) ---
def calculate_duplicate_score(a, b):
    """
    Calculates duplicate similarity score between two real estate records (0 to 100).
    Also checks for 'strong signals' of duplication.
    """
    # --- QUICK PRUNING FOR HIGH PERFORMANCE ---
    # 1. Property Type mismatch
    type_a = a.get("loai_bds")
    type_b = b.get("loai_bds")
    if type_a and type_b and type_a != type_b:
        return {"score": 0, "breakdown": {"pruned": "property type mismatch"}, "strong_signals": []}

    # 2. Area mismatch > 15%
    area_a = a.get("dien_tich")
    area_b = b.get("dien_tich")
    if area_a and area_b:
        try:
            val_a = float(area_a)
            val_b = float(area_b)
            if val_a > 0 and val_b > 0:
                diff = abs(val_a - val_b) / max(val_a, val_b)
                if diff > 0.15:
                    return {"score": 0, "breakdown": {"pruned": "area mismatch > 15%"}, "strong_signals": []}
        except:
            pass

    # 3. Price mismatch > 15%
    g_so_a = a.get("gia_tri_so")
    g_so_b = b.get("gia_tri_so")
    if g_so_a and g_so_b:
        try:
            val_a = float(g_so_a)
            val_b = float(g_so_b)
            if val_a > 0 and val_b > 0:
                diff = abs(val_a - val_b) / max(val_a, val_b)
                if diff > 0.15:
                    return {"score": 0, "breakdown": {"pruned": "price mismatch > 15%"}, "strong_signals": []}
        except:
            pass

    score = 0
    breakdown = {}
    strong_signals = []

    # 1. Title Similarity (max 15 pts)
    title_a = clean_vietnamese(a.get("tieu_de", ""))
    title_b = clean_vietnamese(b.get("tieu_de", ""))
    if title_a and title_b:
        ratio = difflib.SequenceMatcher(None, title_a, title_b).ratio()
        pts = round(ratio * 15, 2)
        score += pts
        breakdown["title"] = f"{pts}/15 (ratio={round(ratio, 2)})"
    else:
        breakdown["title"] = "0/15"

    # 2. Price Similarity (max 15 pts)
    g_so_a = a.get("gia_tri_so")
    g_so_b = b.get("gia_tri_so")
    g_str_a = str(a.get("gia") or "").lower().strip()
    g_str_b = str(b.get("gia") or "").lower().strip()

    if g_so_a and g_so_b:
        # If exactly match
        if g_so_a == g_so_b:
            score += 15
            breakdown["price"] = "15/15 (exact match)"
            strong_signals.append("same_exact_price")
        # Within 5% range
        elif abs(g_so_a - g_so_b) / max(g_so_a, g_so_b) <= 0.05:
            score += 10
            breakdown["price"] = "10/15 (within 5%)"
            strong_signals.append("same_near_price")
        else:
            breakdown["price"] = "0/15"
    elif g_str_a and g_str_b and g_str_a == g_str_b:
        score += 10
        breakdown["price"] = "10/15 (string match)"
        strong_signals.append("same_exact_price")
    else:
        breakdown["price"] = "0/15"

    # 3. Area Similarity (max 20 pts)
    area_a = a.get("dien_tich")
    area_b = b.get("dien_tich")
    if area_a and area_b:
        try:
            val_a = float(area_a)
            val_b = float(area_b)
            if val_a == val_b:
                score += 20
                breakdown["area"] = "20/20 (exact match)"
                strong_signals.append("same_exact_area")
            elif abs(val_a - val_b) / max(val_a, val_b) <= 0.05:
                score += 15
                breakdown["area"] = "15/20 (within 5%)"
                strong_signals.append("same_near_area")
            else:
                breakdown["area"] = "0/20"
        except:
            breakdown["area"] = "0/20"
    else:
        breakdown["area"] = "0/20"

    # 4. Location/Khu Vuc Similarity (max 20 pts)
    loc_a = clean_vietnamese(a.get("vi_tri", ""))
    loc_b = clean_vietnamese(b.get("vi_tri", ""))
    if loc_a and loc_b:
        if loc_a == loc_b:
            score += 20
            breakdown["location"] = "20/20 (exact match)"
            strong_signals.append("same_exact_location")
        else:
            # Common sub-regions
            subregions = ["sa pa", "ta van", "ta phin", "muong hoa", "cam duong", "coc leu", "bac cuong", "duyen hai"]
            shared = [r for r in subregions if r in loc_a and r in loc_b]
            if shared:
                score += 15
                breakdown["location"] = f"15/20 (shared sub-region: {shared[0]})"
                strong_signals.append("same_exact_location")
            elif difflib.SequenceMatcher(None, loc_a, loc_b).ratio() >= 0.5:
                score += 10
                breakdown["location"] = "10/20 (partial match)"
            else:
                breakdown["location"] = "0/20"
    else:
        breakdown["location"] = "0/20"

    # 5. Property Type (loai_bds) (max 10 pts)
    type_a = a.get("loai_bds")
    type_b = b.get("loai_bds")
    if type_a and type_b and type_a == type_b:
        score += 10
        breakdown["type"] = "10/10"
    else:
        breakdown["type"] = "0/10"

    # 6. Description Similarity (max 10 pts)
    desc_a = clean_vietnamese(BeautifulSoupClean(a.get("mo_ta", "")))
    desc_b = clean_vietnamese(BeautifulSoupClean(b.get("mo_ta", "")))
    if desc_a and desc_b:
        ratio = difflib.SequenceMatcher(None, desc_a, desc_b).ratio()
        pts = round(ratio * 10, 2)
        score += pts
        breakdown["description"] = f"{pts}/10 (ratio={round(ratio, 2)})"
        if ratio >= 0.8:
            strong_signals.append("description_above_80")
    else:
        breakdown["description"] = "0/10"

    # 7. Images / Contact / Source (max 10 pts)
    img_a = a.get("hinh_anh")
    img_b = b.get("hinh_anh")
    src_a = a.get("source_url")
    src_b = b.get("source_url")
    phone_a = a.get("contact_phone")
    phone_b = b.get("contact_phone")

    img_pts = 0
    # Clean images to list
    list_a = clean_list(img_a)
    list_b = clean_list(img_b)
    if list_a and list_b and list_a[0] == list_b[0]:
        img_pts += 5
        strong_signals.append("same_thumbnail_image")

    src_pts = 0
    if src_a and src_b and src_a == src_b:
        src_pts += 5
        strong_signals.append("same_source_url")

    phone_pts = 0
    if phone_a and phone_b and phone_a == phone_b:
        phone_pts += 5
        strong_signals.append("same_contact_phone")

    other_pts = min(10, img_pts + src_pts + phone_pts)
    score += other_pts
    breakdown["images_source_phone"] = f"{other_pts}/10 (img={img_pts}, src={src_pts}, phone={phone_pts})"

    return {
        "score": min(100, round(score, 1)),
        "breakdown": breakdown,
        "strong_signals": list(set(strong_signals))
    }

def BeautifulSoupClean(html_text):
    if not html_text: return ""
    # Strip HTML tags
    clean = re.sub(r'<[^>]*>', ' ', str(html_text))
    # Standardize whitespace
    return " ".join(clean.split())

def clean_list(val):
    if not val: return []
    if isinstance(val, list): return val
    if isinstance(val, str):
        try: return json.loads(val)
        except: return []
    return []

# --- PHẦN A: GUARD NEW LISTING BEFORE INSERT ---
def guard_new_listing(new_data, mode="safe-auto"):
    """
    Checks if a newly crawled listing is a duplicate of any existing active (Mở bán) listing.
    Applies the guard rules and returns the modified new_data payload, log payloads, and action action_type.
    """
    db = get_db_client()
    
    # 1. Fetch active listings for comparison
    res = db.table("bds_ban").select("*").eq("trang_thai", "Mở bán").execute()
    active_listings = res.data or []

    highest_score = 0
    matched_id = None
    matched_slug = None
    reason_details = ""
    best_breakdown = {}
    strong_signals = []

    for active in active_listings:
        calc = calculate_duplicate_score(new_data, active)
        if calc["score"] > highest_score:
            highest_score = calc["score"]
            matched_id = active["id"]
            matched_slug = active["slug"]
            best_breakdown = calc["breakdown"]
            reason_details = f"Trùng khớp với tin gốc ID {active['id']} ({active['tieu_de'][:40]}...). Chi tiết: {calc['breakdown']}"
            strong_signals = calc["strong_signals"]

    action_taken = "allow_insert"
    new_status = new_data.get("trang_thai", "Bản nháp")
    reasons = []

    # Apply Rules based on Duplicate Score & Mode
    if highest_score >= 95:
        # Rule 1: Always Block from public
        new_status = "Bản nháp"
        action_taken = "auto_block_duplicate"
        reasons.append(f"Score {highest_score} >= 95. Auto-blocked duplicate of ID {matched_id}.")
    elif 90 <= highest_score < 95:
        # Rule 2: Block if >= 2 strong signals (safe-auto) or >=3 (aggressive-auto)
        required_signals = 3 if mode == "aggressive-auto" else 2
        if len(strong_signals) >= required_signals:
            new_status = "Bản nháp"
            action_taken = "auto_block_duplicate"
            reasons.append(f"Score {highest_score} (90-94) and has {len(strong_signals)} strong signals. Blocked.")
        else:
            new_status = "Bản nháp"
            action_taken = "warning"
            reasons.append(f"Score {highest_score} (90-94) without enough strong signals. Warning.")
    elif 80 <= highest_score < 90:
        # Rule 3: Save as draft, set warning
        new_status = "Bản nháp"
        action_taken = "warning"
        reasons.append(f"Score {highest_score} (80-89). Kept in Drafts with warning.")
    elif 70 <= highest_score < 80:
        # Rule 4: Cảnh báo, nếu safe-auto bật thì đưa về Bản nháp
        action_taken = "warning"
        if mode in ["safe-auto", "aggressive-auto"]:
            new_status = "Bản nháp"
            reasons.append(f"Score {highest_score} (70-79). Kept in Drafts under {mode} mode.")
        else:
            reasons.append(f"Score {highest_score} (70-79). Allowed but warned.")
    else:
        # Rule 5: Normal insert
        action_taken = "allow_insert"

    # Add guard metadata fields to new_data payload
    new_data["trang_thai"] = new_status
    new_data["duplicate_score"] = highest_score
    new_data["duplicate_warning"] = (highest_score >= 70)
    new_data["duplicate_review"] = (highest_score >= 90)
    new_data["possible_duplicate_of"] = matched_id
    new_data["duplicate_checked_at"] = datetime.now(timezone.utc).isoformat()
    new_data["duplicate_status"] = "auto_blocked" if action_taken == "auto_block_duplicate" else ("warning" if highest_score >= 70 else "clean")

    # Generate log payloads
    bot_action = None
    dup_review = None

    if highest_score >= 70:
        bot_action = {
            "action_type": action_taken,
            "duplicate_score": highest_score,
            "reason": "; ".join(reasons) + f" Breakdown: {best_breakdown}",
            "old_status": "new_import",
            "new_status": new_status,
            "backup_json": new_data,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        if matched_id:
            bot_action["primary_id"] = matched_id

        dup_review = {
            "possible_duplicate_of": matched_id,
            "duplicate_score": highest_score,
            "duplicate_reason": "; ".join(reasons),
            "status": "warning" if action_taken == "warning" else "auto_resolved",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    return new_data, bot_action, dup_review

# --- PHẦN B: BOT TUẦN TRA ĐỊNH KỲ (PATROL ACTIVE LISTINGS) ---
def patrol_active_listings(mode="safe-auto", dry_run=True, limit=None):
    """
    Patrol active listings (Mở bán) updated in the last 14 days.
    Identifies duplicate pairs and handles them cleanly with redirects.
    """
    db = get_db_client()
    print(f"Patrolling active Mở bán listings... Mode: {mode}, Dry-run: {dry_run}, Limit: {limit}")
    
    # 1. Fetch active listings
    res = db.table("bds_ban").select("*").eq("trang_thai", "Mở bán").execute()
    active_listings = res.data or []
    
    print(f"Loaded {len(active_listings)} active listings.")
    processed_pairs = set()
    actions_performed = []

    for i in range(len(active_listings)):
        for j in range(i + 1, len(active_listings)):
            if limit is not None and len(actions_performed) >= limit:
                print(f"Reached patrol limit of {limit} actions. Stopping active listing scan.")
                return actions_performed
            a = active_listings[i]
            b = active_listings[j]
            pair_key = tuple(sorted([a["id"], b["id"]]))
            if pair_key in processed_pairs: continue
            processed_pairs.add(pair_key)

            calc = calculate_duplicate_score(a, b)
            score = calc["score"]
            strong_signals = calc["strong_signals"]

            if score < 80: continue

            # Decide action
            action_type = None
            reasons = []

            if score >= 95:
                action_type = "auto_hide_duplicate"
                reasons.append(f"Score {score} >= 95. Auto-hiding duplicate.")
            elif 90 <= score < 95:
                required_signals = 3 if mode == "aggressive-auto" else 2
                if len(strong_signals) >= required_signals:
                    action_type = "auto_hide_duplicate"
                    reasons.append(f"Score {score} (90-94) and has {len(strong_signals)} strong signals. Hiding.")
                else:
                    action_type = "warning"
                    reasons.append(f"Score {score} (90-94) but lacks strong signals. Warned.")
            elif 80 <= score < 90:
                action_type = "warning"
                reasons.append(f"Score {score} (80-89). Warned.")

            if not action_type or action_type == "warning":
                print(f"⚠️ [WARNING] Possible duplicate: ID {a['id']} vs ID {b['id']} | Score: {score} | Reasons: {reasons}")
                # Log warning
                if not dry_run:
                    log_warning(db, a, b, score, reasons)
                continue

            # We must auto-hide the duplicate! First, choose primary vs duplicate listing
            primary, duplicate = choose_primary_listing(a, b)
            if not primary or not duplicate:
                print(f"⚠️ [WARNING] Could not decide primary for ID {a['id']} vs ID {b['id']}. Skipping.")
                continue

            print(f"🚀 [AUTO-HIDE] Duplicate detected: ID {duplicate['id']} is a duplicate of ID {primary['id']} (Score: {score})")
            
            action_log = {
                "action_type": "auto_hide_duplicate",
                "primary_id": primary["id"],
                "duplicate_id": duplicate["id"],
                "duplicate_score": score,
                "reason": "; ".join(reasons) + f" Breakdown: {calc['breakdown']}",
                "old_status": duplicate["trang_thai"],
                "new_status": "Ẩn",
                "old_slug": duplicate["slug"],
                "redirect_to_slug": primary["slug"],
                "backup_json": duplicate,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            if not dry_run:
                # 1. Update duplicate listing status to 'Ẩn'
                db.table("bds_ban").update({
                    "trang_thai": "Ẩn",
                    "duplicate_score": score,
                    "duplicate_warning": True,
                    "possible_duplicate_of": primary["id"],
                    "duplicate_checked_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", duplicate["id"]).execute()

                # 2. Add redirect to slug-redirects.json
                add_redirect_rule(duplicate["slug"], primary["slug"])

                # 3. Log action
                db.table("bds_bot_actions").insert(action_log).execute()
                print(f"✅ Successfully hid ID {duplicate['id']} and created 301 redirect to {primary['slug']}")
            else:
                print(f"🧪 [DRY-RUN] Would hide ID {duplicate['id']}, set warning, and redirect {duplicate['slug']} -> {primary['slug']}")

            actions_performed.append(action_log)

    return actions_performed

# --- PHẦN C: BOT TUẦN TRA ĐĂNG TIN (PATROL AUTO PUBLISH DRAFTS) ---
def patrol_auto_publish_drafts(mode="safe-auto", dry_run=True, limit=None):
    """
    Scans listings in 'Bản nháp' or 'Chờ duyệt', validates against the publishing checklist,
    ensures no duplicate score >= 80, and auto-publishes them to 'Mở bán'.
    """
    db = get_db_client()
    print(f"Patrolling Bản nháp drafts for auto-publish... Mode: {mode}, Dry-run: {dry_run}, Limit: {limit}")
    
    # 1. Fetch Drafts
    res_drafts = db.table("bds_ban").select("*").in_("trang_thai", ["Bản nháp", "Chờ duyệt"]).execute()
    drafts = res_drafts.data or []
    
    # 2. Fetch active listings to check duplicates
    res_active = db.table("bds_ban").select("*").eq("trang_thai", "Mở bán").execute()
    active_listings = res_active.data or []

    published_count = 0
    actions_performed = []

    forbidden_words = ["siêu phẩm", "cực hot", "vị trí vàng", "cơ hội vàng", "sinh lời", "cam kết", "không rủi ro"]

    for draft in drafts:
        if limit is not None and len(actions_performed) >= limit:
            print(f"Reached auto-publish limit of {limit} actions. Stopping draft publish scan.")
            break
        # Publishing Checklist
        issues = []

        # 1. Check title
        title = draft.get("tieu_de")
        if not title or len(title.strip()) < 10:
            issues.append("Tiêu đề quá ngắn hoặc rỗng")

        # 2. Check slug
        slug = draft.get("slug")
        if not slug or "--" in slug or slug.startswith("-") or slug.endswith("-"):
            issues.append("Slug lỗi hoặc không hợp lệ")

        # 3. Check cover image
        images = clean_list(draft.get("hinh_anh"))
        if not images:
            issues.append("Thiếu hình ảnh")

        # 4. Check price
        gia = draft.get("gia")
        if not gia or str(gia).strip() == "":
            issues.append("Thiếu giá")

        # 5. Check area
        area = draft.get("dien_tich")
        if not area or float(area) <= 0:
            issues.append("Thiếu diện tích hoặc diện tích <= 0")

        # 6. Check location
        vi_tri = draft.get("vi_tri")
        if not vi_tri or str(vi_tri).strip() == "":
            issues.append("Thiếu khu vực/vị trí")

        # 7. Check description
        mo_ta = draft.get("mo_ta")
        if not mo_ta or len(BeautifulSoupClean(mo_ta)) < 30:
            issues.append("Mô tả quá ngắn hoặc trống")

        # 8. Check forbidden advertising words
        haystack = clean_vietnamese(f"{title} {mo_ta}")
        matched_forbidden = [w for w in forbidden_words if clean_vietnamese(w) in haystack]
        if matched_forbidden:
            issues.append(f"Chứa từ khóa quảng cáo bị cấm: {matched_forbidden}")

        # 9. Ensure no duplicate score >= 80 with any active listing
        is_duplicate = False
        highest_dup_score = 0
        matched_active_id = None
        for active in active_listings:
            calc = calculate_duplicate_score(draft, active)
            if calc["score"] >= 80:
                is_duplicate = True
                highest_dup_score = calc["score"]
                matched_active_id = active["id"]
                issues.append(f"Trùng lặp với tin Mở bán ID {active['id']} (Score: {calc['score']})")
                break

        if issues:
            print(f"⏭️ Draft ID {draft['id']} ({draft['tieu_de'][:30]}...) fails checklist: {issues}")
            continue

        # Passes checklist! Auto-publish!
        print(f"🚀 [AUTO-PUBLISH] Draft ID {draft['id']} passes all checks. Auto-publishing...")
        
        action_log = {
            "action_type": "auto_publish",
            "primary_id": draft["id"],
            "reason": "Đạt đầy đủ tiêu chuẩn tin đăng và không trùng lặp.",
            "old_status": draft["trang_thai"],
            "new_status": "Mở bán",
            "backup_json": draft,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        if not dry_run:
            db.table("bds_ban").update({
                "trang_thai": "Mở bán",
                "duplicate_checked_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", draft["id"]).execute()

            db.table("bds_bot_actions").insert(action_log).execute()
            published_count += 1
            print(f"✅ Successfully auto-published Draft ID {draft['id']}")
        else:
            print(f"🧪 [DRY-RUN] Would auto-publish Draft ID {draft['id']}")

        actions_performed.append(action_log)

    return actions_performed

# --- PHẦN D: CHOOSE PRIMARY LISTING (CRITERIA) ---
def choose_primary_listing(a, b):
    """
    Selects which listing to keep as primary based on the defined 9-point criteria.
    Returns (primary, duplicate) tuple.
    """
    # 1. Status: Mở bán vs Draft
    status_a = a.get("trang_thai")
    status_b = b.get("trang_thai")
    if status_a == "Mở bán" and status_b != "Mở bán":
        return a, b
    if status_b == "Mở bán" and status_a != "Mở bán":
        return b, a

    # 2. Number of images
    imgs_a = len(clean_list(a.get("hinh_anh")))
    imgs_b = len(clean_list(b.get("hinh_anh")))
    if imgs_a != imgs_b:
        return (a, b) if imgs_a > imgs_b else (b, a)

    # 4. Length of description
    len_a = len(BeautifulSoupClean(a.get("mo_ta", "")))
    len_b = len(BeautifulSoupClean(b.get("mo_ta", "")))
    if len_a != len_b:
        return (a, b) if len_a > len_b else (b, a)

    # 5. Clean meta tags presence
    has_meta_a = bool(a.get("meta_title") or a.get("meta_desc"))
    has_meta_b = bool(b.get("meta_title") or b.get("meta_desc"))
    if has_meta_a and not has_meta_b:
        return a, b
    if has_meta_b and not has_meta_a:
        return b, a

    # 6. Slug cleanliness (no "--" or multiple dashes)
    slug_a = a.get("slug", "")
    slug_b = b.get("slug", "")
    dashes_a = slug_a.count("-")
    dashes_b = slug_b.count("-")
    if dashes_a != dashes_b:
        return (a, b) if dashes_a < dashes_b else (b, a)

    # 7. Early index/published date
    pub_a = a.get("created_at") or ""
    pub_b = b.get("created_at") or ""
    if pub_a and pub_b:
        return (a, b) if pub_a < pub_b else (b, a)

    # 8. Updated date
    up_a = a.get("updated_at") or ""
    up_b = b.get("updated_at") or ""
    if up_a and up_b:
        return (a, b) if up_a > up_b else (b, a)

    # No clear winner
    return None, None

# --- PHẦN F: REDIRECT 301 MANAGER ---
def add_redirect_rule(src_slug, tgt_slug):
    """
    Appends a new redirect mapping to slug-redirects.json,
    and flattens redirect chains/loops.
    """
    if not src_slug or not tgt_slug or src_slug == tgt_slug:
        return
    try:
        redirects = {}
        if os.path.exists(REDIRECTS_FILE):
            with open(REDIRECTS_FILE, "r", encoding="utf-8") as f:
                redirects = json.load(f)

        redirects[src_slug] = tgt_slug

        # Flatten redirect chains: prevent chain redirects
        resolved_any = True
        while resolved_any:
            resolved_any = False
            for k in list(redirects.keys()):
                target = redirects[k]
                if target in redirects:
                    next_target = redirects[target]
                    if next_target != k:
                        redirects[k] = next_target
                        resolved_any = True

        # Write back
        os.makedirs(os.path.dirname(REDIRECTS_FILE), exist_ok=True)
        with open(REDIRECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(redirects, f, ensure_ascii=False, indent=2)
        print(f"🔄 [Redirect Added] {src_slug} -> {tgt_slug}")
    except Exception as e:
        print(f"⚠️ Error updating redirects config: {e}")

# --- PHẦN G: ROLLBACK BOT ACTION ---
def rollback_bot_action(action_id):
    """
    Rolls back a specific bot action, restores duplicate listings to 'Mở bán' or their old state,
    restores old data from backup_json, and removes the 301 redirect.
    """
    db = get_db_client()
    print(f"⏪ Rolling back bot action ID: {action_id}...")
    
    # 1. Fetch action record
    res = db.table("bds_bot_actions").select("*").eq("id", action_id).execute()
    if not res.data:
        print("❌ Action ID not found.")
        return False
        
    action = res.data[0]
    action_type = action.get("action_type")
    dup_id = action.get("duplicate_id")
    old_status = action.get("old_status", "Mở bán")
    old_slug = action.get("old_slug")
    backup_data = action.get("backup_json")

    if action_type == "auto_hide_duplicate" and dup_id:
        print(f"⏪ Restoring duplicate listing ID {dup_id} to status '{old_status}'...")
        
        # 1. Restore status & backup data in database
        payload = {
            "trang_thai": old_status,
            "duplicate_warning": False,
            "duplicate_score": 0,
            "possible_duplicate_of": None
        }
        if backup_data:
            # Overwrite fields from backup
            for k in ["tieu_de", "gia", "dien_tich", "vi_tri", "mo_ta", "hinh_anh"]:
                if k in backup_data:
                    payload[k] = backup_data[k]
                    
        db.table("bds_ban").update(payload).eq("id", dup_id).execute()

        # 2. Remove redirect from slug-redirects.json
        if old_slug and os.path.exists(REDIRECTS_FILE):
            try:
                with open(REDIRECTS_FILE, "r", encoding="utf-8") as f:
                    redirects = json.load(f)
                if old_slug in redirects:
                    del redirects[old_slug]
                    with open(REDIRECTS_FILE, "w", encoding="utf-8") as f:
                        json.dump(redirects, f, ensure_ascii=False, indent=2)
                    print(f"⏪ Removed redirect rule for slug: {old_slug}")
            except Exception as e:
                print(f"⚠️ Error removing redirect rule: {e}")

        # 3. Log rollback completion
        db.table("bds_bot_actions").update({
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "rollback_status": "rollbacked"
        }).eq("id", action_id).execute()

        print(f"✅ Rollback of bot action {action_id} completed successfully!")
        return True

    elif action_type == "auto_publish":
        # Rollback draft auto-publish
        primary_id = action.get("primary_id")
        if primary_id:
            print(f"⏪ Moving auto-published listing ID {primary_id} back to status '{old_status}'...")
            db.table("bds_ban").update({
                "trang_thai": old_status
            }).eq("id", primary_id).execute()

            db.table("bds_bot_actions").update({
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "rollback_status": "rollbacked"
            }).eq("id", action_id).execute()
            
            print(f"✅ Rollback of auto-publish for ID {primary_id} completed successfully!")
            return True

    print("❌ Rollback not supported or invalid action type.")
    return False

# --- LOGGER HELPER ---
def log_warning(db, a, b, score, reasons):
    try:
        db.table("bds_bot_actions").insert({
            "action_type": "warning",
            "primary_id": a["id"],
            "duplicate_id": b["id"],
            "duplicate_score": score,
            "reason": "; ".join(reasons),
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        print(f"⚠️ Error logging duplicate warning: {e}")
