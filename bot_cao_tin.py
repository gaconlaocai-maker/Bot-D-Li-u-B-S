import io
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader
import feedparser
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps
from supabase import create_client


# ================= 1. CAU HINH HE THONG & BIEN TOAN CUC =================
GROQ_KEYS_STR = os.environ.get("GROQ_API_KEY", "")
DANH_SACH_GROQ_KEYS = [k.strip() for k in GROQ_KEYS_STR.split(",") if k.strip()]
DANH_SACH_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
vi_tri_groq_key = 0

MAX_ARTICLES_PER_RUN = int(os.environ.get("MAX_ARTICLES_PER_RUN", "10"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
FLIP_SOURCE_IMAGE = os.environ.get("FLIP_SOURCE_IMAGE", "false").lower() == "true"
WATERMARK_IMAGE = os.environ.get("WATERMARK_IMAGE", "true").lower() == "true"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    print("⚠️ Thiếu SUPABASE_URL hoặc SUPABASE_KEY. Bot sẽ bỏ qua kiểm tra DB/insert nếu không thể kết nối.")

if os.environ.get("CLOUDINARY_CLOUD_NAME"):
    cloudinary.config(
        cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
        api_key=os.environ.get("CLOUDINARY_API_KEY"),
        api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
        secure=True,
    )

NGUON_TIN = [
    {"ten": "CafeLand", "url": "https://cafeland.vn/tin-tuc/rss/", "chu_de": "Bất động sản"},
    {"ten": "VnEconomy", "url": "https://vneconomy.vn/bat-dong-san.rss", "chu_de": "Bất động sản"},
    {"ten": "VietnamNet BĐS", "url": "https://vietnamnet.vn/bat-dong-san.rss", "chu_de": "Bất động sản"},
    {"ten": "VnExpress BĐS", "url": "https://vnexpress.net/rss/bat-dong-san.rss", "chu_de": "Bất động sản"},
    {"ten": "Reatimes", "url": "https://reatimes.vn/rss/thi-truong-2.rss", "chu_de": "Bất động sản"},
    {"ten": "VnExpress Du Lịch", "url": "https://vnexpress.net/rss/du-lich.rss", "chu_de": "Du lịch"},
    {"ten": "Dân Trí Du Lịch", "url": "https://dantri.com.vn/rss/du-lich.rss", "chu_de": "Du lịch"},
    {"ten": "Tuổi Trẻ Du Lịch", "url": "https://dulich.tuoitre.vn/rss/du-lich.rss", "chu_de": "Du lịch"},
    {"ten": "Thanh Niên Du Lịch", "url": "https://thanhnien.vn/rss/du-lich.rss", "chu_de": "Du lịch"},
    {"ten": "VietnamNet Du Lịch", "url": "https://vietnamnet.vn/du-lich.rss", "chu_de": "Du lịch"},
]

ALLOW_KEYWORDS = [
    "lào cai", "lao cai", "sa pa", "sapa", "tả van", "ta van",
    "bắc hà", "bac ha", "bát xát", "bat xat", "bảo thắng", "bao thang",
    "văn bàn", "van ban", "mường khương", "muong khuong",
    "bất động sản", "bat dong san", "đất nền", "dat nen", "nhà đất", "nha dat",
    "nghỉ dưỡng", "nghi duong", "homestay", "khách sạn", "khach san",
    "du lịch", "du lich", "du lịch tây bắc", "du lich tay bac",
    "mặt bằng", "mat bang", "kinh doanh", "việc làm", "viec lam",
    "việc làm khách sạn", "viec lam khach san", "nhà hàng", "nha hang",
]

BLOCK_KEYWORDS = [
    "giá vàng", "gia vang", "chứng khoán", "chung khoan", "cổ phiếu", "co phieu",
    "dow jones", "mỹ", "my", "trung quốc", "trung quoc", "iran", "ukraine",
    "spacex", "showbiz", "hoa hậu", "hoa hau", "bóng đá", "bong da",
    "xăng e10", "xang e10", "quốc tế", "quoc te",
]

LOCAL_SIGNALS = ["lào cai", "lao cai", "sa pa", "sapa"]
VALID_TOPIC_TYPES = {
    "bat_dong_san",
    "du_lich_luu_tru",
    "viec_lam",
    "mat_bang",
    "cam_nang_dia_phuong",
    "bo_qua",
}

TOPIC_FALLBACK_IMAGES = {
    "bat_dong_san": "https://images.unsplash.com/photo-1560518883-ce09059eeffa",
    "du_lich_luu_tru": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee",
    "viec_lam": "https://images.unsplash.com/photo-1551836022-d5d88e9218df",
    "mat_bang": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab",
    "cam_nang_dia_phuong": "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429",
    "bo_qua": "https://images.unsplash.com/photo-1504711434969-e33886168f5c",
}

TONG_LOI_HE_THONG = 0
GIOI_HAN_LOI_MAX = 50

THONG_KE = {
    "rss_items": 0,
    "bo_qua_trung": 0,
    "bo_qua_keyword": 0,
    "ai_audit": 0,
    "ai_loai": 0,
    "ai_viet": 0,
    "dang_thanh_cong": 0,
}


def log(msg):
    print(msg, flush=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def tang_loi(so_luong=1):
    global TONG_LOI_HE_THONG
    TONG_LOI_HE_THONG += so_luong
    kiem_tra_gioi_han_loi()


def kiem_tra_gioi_han_loi():
    global TONG_LOI_HE_THONG
    if TONG_LOI_HE_THONG >= GIOI_HAN_LOI_MAX:
        log(f"🚨 CẢNH BÁO: Đã chạm mốc {GIOI_HAN_LOI_MAX} lỗi toàn cục. Tự động tắt Bot!")
        sys.exit(1)


# ================= 2. GOI API GROQ (XOAY VONG KEY & MODEL) =================
def goi_ai_groq(prompt):
    global vi_tri_groq_key
    if not DANH_SACH_GROQ_KEYS:
        log("⚠️ Không có GROQ_API_KEY. Bỏ qua gọi AI.")
        tang_loi()
        return None

    so_key_da_thu = 0
    while so_key_da_thu < len(DANH_SACH_GROQ_KEYS):
        key_hien_tai = DANH_SACH_GROQ_KEYS[vi_tri_groq_key]

        for model in DANH_SACH_MODELS:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key_hien_tai}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.25,
            }

            try:
                res = requests.post(url, headers=headers, json=payload, timeout=45)
                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and data["choices"]:
                        log(f"🪄 Groq ({model}) xử lý thành công bằng Key số {vi_tri_groq_key + 1}.")
                        return data["choices"][0]["message"]["content"].strip()
                elif res.status_code in [429, 401, 403]:
                    log(f"⚠️ Key {vi_tri_groq_key + 1} nghẽn/không hợp lệ với model {model}. Thử model tiếp theo.")
                    continue
                else:
                    log(f"⚠️ Groq trả HTTP {res.status_code} với model {model}: {res.text[:180]}")
                    continue
            except Exception as e:
                log(f"⚠️ Lỗi mạng Groq (model {model}): {e}")
                continue

        log(f"❌ Key số {vi_tri_groq_key + 1} không dùng được với các model hiện tại. Chuyển key.")
        vi_tri_groq_key = (vi_tri_groq_key + 1) % len(DANH_SACH_GROQ_KEYS)
        so_key_da_thu += 1

    tang_loi()
    return None


# ================= 3. LOC, FETCH, SLUG, AI AUDIT =================
def strip_html(text):
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def safe_get(entry, key, default=""):
    value = getattr(entry, key, default)
    return value if value is not None else default


def pre_filter_article(title, summary, source_name, chu_de):
    raw_text = " ".join([title or "", summary or "", source_name or "", chu_de or ""])
    text = raw_text.lower()
    ascii_text = bo_dau_tieng_viet(text)
    haystack = f"{text} {ascii_text}"

    if any(k in haystack for k in LOCAL_SIGNALS):
        return True, "Có tín hiệu trực tiếp Lào Cai/Sa Pa."

    if any(k in haystack for k in BLOCK_KEYWORDS):
        return False, "Có block keyword mạnh và không có tín hiệu địa phương."

    if any(k in haystack for k in ALLOW_KEYWORDS):
        return True, "Có allow keyword phù hợp LaoCaiView."

    if chu_de in ["Bất động sản", "Du lịch"]:
        return True, f"Chủ đề {chu_de} được cho AI audit để tìm góc nhìn địa phương."

    return False, "Không có allow keyword hoặc tín hiệu chủ đề phù hợp."


def fetch_page_meta(url):
    meta = {
        "og_description": "",
        "og_image": "",
        "canonical_url": "",
        "body_excerpt": "",
    }
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LaoCaiViewBot/1.0; +https://laocaiview.com)"
        }
        res = requests.get(url, headers=headers, timeout=18)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")

        desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        img = soup.find("meta", property="og:image")
        canonical = soup.find("link", rel="canonical")

        meta["og_description"] = desc.get("content", "").strip() if desc else ""
        meta["og_image"] = img.get("content", "").strip() if img else ""
        meta["canonical_url"] = canonical.get("href", "").strip() if canonical else ""

        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if len(text) > 60:
                paragraphs.append(text)
            if len(" ".join(paragraphs)) > 2200:
                break
        meta["body_excerpt"] = " ".join(paragraphs)[:2500]
    except Exception as e:
        log(f"⚠️ Không fetch được trang nguồn: {url} | {e}")
        tang_loi()
    return meta


def strip_json_response(text):
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    return match.group(0).strip() if match else cleaned


def ai_audit_article(title, summary, og_description, source_name, url, chu_de):
    prompt = f"""
Bạn là biên tập viên SEO địa phương của LaoCaiView.
Hãy đánh giá bài nguồn có nên viết lại thành bài hữu ích cho độc giả Lào Cai - Sa Pa không.

Website tập trung: Bất động sản Lào Cai - Sa Pa, du lịch/lưu trú/homestay/khách sạn Sa Pa, việc làm Lào Cai - Sa Pa, mặt bằng kinh doanh Lào Cai, cẩm nang địa phương Lào Cai - Sa Pa.

Chỉ trả về JSON strict, không markdown, không code block.
topic_type chỉ được là một trong: bat_dong_san, du_lich_luu_tru, viec_lam, mat_bang, cam_nang_dia_phuong, bo_qua.

Dữ liệu nguồn:
- title: {title}
- summary: {summary}
- og_description: {og_description}
- source_name: {source_name}
- url: {url}
- chu_de: {chu_de}

Schema bắt buộc:
{{
  "is_relevant": true,
  "local_score": 80,
  "topic_type": "bat_dong_san",
  "target_keyword": "bất động sản Sa Pa",
  "suggested_title": "Có nên mua đất nghỉ dưỡng Sa Pa năm 2026?",
  "suggested_meta": "Phân tích tiềm năng bất động sản nghỉ dưỡng Sa Pa, những khu vực đáng chú ý và lưu ý khi mua bán nhà đất tại Lào Cai.",
  "angle": "Góc nhìn địa phương cho người mua nhà đất và nhà đầu tư tại Lào Cai - Sa Pa",
  "reason": "Chủ đề BĐS nghỉ dưỡng có thể liên hệ trực tiếp tới thị trường Sa Pa.",
  "should_create_article": true
}}
"""
    raw = goi_ai_groq(prompt)
    if not raw:
        return None
    try:
        audit = json.loads(strip_json_response(raw))
    except Exception as e:
        log(f"❌ Không parse được JSON audit: {e} | raw={raw[:220]}")
        tang_loi()
        return None

    topic_type = audit.get("topic_type", "bo_qua")
    if topic_type not in VALID_TOPIC_TYPES:
        audit["topic_type"] = "bo_qua"
    try:
        audit["local_score"] = int(audit.get("local_score", 0))
    except Exception:
        audit["local_score"] = 0
    audit.setdefault("suggested_title", title)
    audit.setdefault("suggested_meta", summary[:155] if summary else title)
    audit.setdefault("target_keyword", "")
    audit.setdefault("angle", "")
    audit.setdefault("reason", "")
    audit.setdefault("should_create_article", False)
    audit.setdefault("is_relevant", False)
    return audit


def ai_viet_bai(audit, source_title, source_summary, og_description, chu_de, source_url):
    internal_link = {
        "bat_dong_san": "/bat-dong-san",
        "du_lich_luu_tru": "/dat-phong",
        "viec_lam": "/viec-lam",
        "mat_bang": "/mat-bang",
        "cam_nang_dia_phuong": "/tin-tuc",
    }.get(audit.get("topic_type"), "/tin-tuc")

    prompt = f"""
Bạn là biên tập viên LaoCaiView. Viết một bài HTML tiếng Việt mới, chuẩn SEO địa phương, gần gũi và hữu ích.

Quy tắc nội dung:
- Không copy nguyên văn nguồn, chỉ dùng để hiểu ngữ cảnh.
- Không nói "theo bài báo gốc", không nói "là một AI".
- Không bịa số liệu chắc chắn; nếu không chắc hãy dùng cách diễn đạt thận trọng.
- Hữu ích cho người mua nhà đất, du khách, người tìm việc hoặc chủ kinh doanh tại Lào Cai - Sa Pa.
- Độ dài mục tiêu 700-1200 chữ nếu có đủ ngữ cảnh.
- HTML chỉ dùng các thẻ: h2, h3, p, ul, li, strong, a.
- Không dùng script, iframe, style inline, markdown code block.
- Chèn internal link tự nhiên tới {internal_link}.

Dữ liệu để viết:
- Tiêu đề đề xuất: {audit.get("suggested_title")}
- Từ khóa mục tiêu: {audit.get("target_keyword")}
- Góc khai thác: {audit.get("angle")}
- Tiêu đề nguồn: {source_title}
- Tóm tắt/description nguồn: {(og_description or source_summary)[:1800]}
- Chủ đề nguồn: {chu_de}
- URL nguồn để hiểu ngữ cảnh, không trích nguyên văn: {source_url}

Cấu trúc cần có:
- Mở bài bằng thẻ p.
- 3 đến 5 mục h2.
- Có ul/li nếu phù hợp.
- Có đoạn gợi ý hành động.
- Có 3 câu FAQ nếu phù hợp, dùng h2 cho tiêu đề FAQ và h3 cho từng câu hỏi.

Chỉ trả về HTML, bắt đầu bằng <p> hoặc <h2>.
"""
    html = goi_ai_groq(prompt)
    if not html:
        return None
    return sanitize_html(html)


def sanitize_html(html):
    cleaned = html.replace("```html", "").replace("```", "").strip()
    soup = BeautifulSoup(cleaned, "html.parser")
    allowed = {"h2", "h3", "p", "ul", "li", "strong", "a"}
    for tag in soup.find_all(True):
        if tag.name not in allowed:
            tag.unwrap()
            continue
        attrs = {}
        if tag.name == "a" and tag.get("href"):
            attrs["href"] = tag.get("href")
        tag.attrs = attrs
    return str(soup).strip()


def bo_dau_tieng_viet(text):
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")


def tao_slug(title, them_timestamp=False):
    base = bo_dau_tieng_viet(title).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-")[:80].strip("-")
    if not base:
        base = "tin-lao-cai"
    if them_timestamp:
        base = f"{base}-{int(time.time())}"
    return base


def map_topic_to_chuyen_muc(topic_type):
    return {
        "bat_dong_san": "Bất động sản",
        "du_lich_luu_tru": "Du lịch - Lưu trú",
        "viec_lam": "Việc làm",
        "mat_bang": "Mặt bằng kinh doanh",
        "cam_nang_dia_phuong": "Cẩm nang Lào Cai - Sa Pa",
        "bo_qua": "Tin tức",
    }.get(topic_type, "Tin tức")


def da_ton_tai(field, value):
    if DRY_RUN and not supabase:
        return False
    if not supabase:
        return False
    try:
        res = supabase.table("tin_tuc").select("id").eq(field, value).execute()
        return bool(res.data)
    except Exception as e:
        log(f"⚠️ Lỗi kiểm tra trùng {field}: {e}")
        tang_loi()
        return False


def slug_prefix_ton_tai(slug_base):
    if DRY_RUN and not supabase:
        return False
    if not supabase or not slug_base:
        return False
    try:
        res = supabase.table("tin_tuc").select("id,slug").ilike("slug", f"{slug_base}%").limit(1).execute()
        return bool(res.data)
    except Exception as e:
        log(f"⚠️ Lỗi kiểm tra trùng slug prefix: {e}")
        tang_loi()
        return False


def bai_ai_da_ton_tai(audit):
    suggested_title = (audit.get("suggested_title") or "").strip()
    slug_base = tao_slug(suggested_title)

    if suggested_title and da_ton_tai("tieu_de", suggested_title):
        return True, "Tiêu đề AI đã tồn tại trong bảng tin_tuc."

    if slug_base and slug_prefix_ton_tai(slug_base):
        return True, "Base slug đã tồn tại, có thể là bài trùng đã được thêm timestamp trước đó."

    return False, ""


# ================= 4. XU LY ANH WEBP =================
def fallback_image(topic_type):
    return TOPIC_FALLBACK_IMAGES.get(topic_type, TOPIC_FALLBACK_IMAGES["cam_nang_dia_phuong"])


def add_watermark(img):
    draw = ImageDraw.Draw(img)
    text = "LaoCaiView"
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    pad = 18
    x = img.width - w - pad * 2
    y = img.height - h - pad * 2
    draw.rounded_rectangle((x - pad, y - pad, x + w + pad, y + h + pad), radius=8, fill=(0, 0, 0, 135))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 235))
    return img


def xu_ly_anh_webp(url_goc, slug, topic_type="cam_nang_dia_phuong"):
    image_meta = {
        "source_image_url": url_goc or "",
        "public_image_url": fallback_image(topic_type),
        "image_source_type": "fallback_image",
        "image_modified": False,
        "image_modifications": [],
        "image_rights_status": "unknown",
    }

    if not url_goc:
        return image_meta

    if DRY_RUN:
        image_meta.update({
            "public_image_url": url_goc,
            "image_source_type": "source_og_image",
        })
        return image_meta

    try:
        res = requests.get(url_goc, timeout=18)
        res.raise_for_status()
        img_data = io.BytesIO(res.content)

        with Image.open(img_data) as img:
            img = img.convert("RGB")
            img = ImageOps.exif_transpose(img)
            if FLIP_SOURCE_IMAGE:
                img = ImageOps.mirror(img)
                image_meta["image_modifications"].append("flip_horizontal")

            img = ImageOps.fit(img, (1200, 630), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            image_meta["image_modifications"].append("resize_webp")

            if WATERMARK_IMAGE:
                img = add_watermark(img)
                image_meta["image_modifications"].append("watermark")

            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=80, method=6)
            buffer.seek(0)

            up = cloudinary.uploader.upload(buffer, folder="laocai_news", public_id=slug, resource_type="image")
            image_meta.update({
                "public_image_url": up["secure_url"],
                "image_source_type": "source_og_image",
                "image_modified": True,
            })
            return image_meta
    except Exception as e:
        log(f"⚠️ Lỗi tải/xử lý ảnh, dùng fallback: {e}")
        tang_loi()
        return image_meta


# ================= 5. INSERT SUPABASE =================
def source_domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def insert_tin_tuc(payload):
    if DRY_RUN:
        log("🧪 DRY_RUN=true: không insert Supabase.")
        return {"dry_run": True}
    if not supabase:
        log("❌ Không có kết nối Supabase, không thể insert.")
        tang_loi()
        return None

    try:
        return supabase.table("tin_tuc").insert(payload).execute()
    except Exception as e:
        log(f"⚠️ Insert payload đầy đủ lỗi, có thể do thiếu cột mới: {e}")
        base_fields = {
            "tieu_de": payload.get("tieu_de"),
            "slug": payload.get("slug"),
            "mo_ta": payload.get("mo_ta"),
            "noi_dung_html": payload.get("noi_dung_html"),
            "anh_bia": payload.get("anh_bia"),
            "chuyen_muc": payload.get("chuyen_muc"),
            "trang_thai": payload.get("trang_thai"),
            "nguon_bai": payload.get("nguon_bai"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "vi_tri_hien_thi": payload.get("vi_tri_hien_thi"),
        }
        try:
            log("⚠️ Thử fallback insert với các cột chắc chắn/cũ.")
            return supabase.table("tin_tuc").insert(base_fields).execute()
        except Exception as e2:
            log(f"❌ Fallback insert cũng lỗi: {e2}")
            tang_loi()
            return None


def build_payload(audit, html, image_meta, source_url, canonical_url, published_at):
    topic_type = audit.get("topic_type", "cam_nang_dia_phuong")
    local_score = int(audit.get("local_score", 0))
    chuyen_muc = map_topic_to_chuyen_muc(topic_type)
    if 50 <= local_score <= 69:
        chuyen_muc = "Cẩm nang địa phương"

    slug = tao_slug(audit.get("suggested_title") or "tin-lao-cai")
    if da_ton_tai("slug", slug):
        slug = tao_slug(audit.get("suggested_title") or "tin-lao-cai", them_timestamp=True)

    timestamp = now_iso()
    full_audit = {
        **audit,
        **image_meta,
        "source_url": source_url,
        "canonical_url": canonical_url or None,
        "source_domain": source_domain(source_url),
    }

    return {
        "tieu_de": audit.get("suggested_title"),
        "slug": slug,
        "mo_ta": audit.get("suggested_meta"),
        "noi_dung_html": html,
        "anh_bia": image_meta.get("public_image_url"),
        "chuyen_muc": chuyen_muc,
        "trang_thai": "Đã đăng",
        "nguon_bai": source_url,
        "created_at": timestamp,
        "updated_at": timestamp,
        "vi_tri_hien_thi": None,
        "ai_audit": full_audit,
        "ai_score": local_score,
        "local_score": local_score,
        "is_local": local_score >= 70,
        "indexable": True,
        "show_on_home": local_score >= 70,
        "needs_review": False,
        "content_type": "ai_curated_local_article",
        "topic_type": topic_type,
        "target_keyword": audit.get("target_keyword"),
        "suggested_title": audit.get("suggested_title"),
        "suggested_meta": audit.get("suggested_meta"),
        "suggested_action": "auto_published",
        "source_urls": [source_url],
        "source_domain": source_domain(source_url),
        "canonical_url": None,
        "meta_title": f"{audit.get('suggested_title')} | LaoCaiView",
        "meta_desc": audit.get("suggested_meta"),
        "published_at": published_at or timestamp,
        "updated_by_ai_at": timestamp,
        "reviewed_at": None,
        "reviewed_by": None,
    }


# ================= 6. LOGIC CHAY BOT =================
def thuc_thi():
    log(
        "🚀 Khởi động Bot Cào Tin LaoCaiView "
        f"| MAX={MAX_ARTICLES_PER_RUN} | DRY_RUN={DRY_RUN} | WATERMARK={WATERMARK_IMAGE}"
    )
    so_luong_da_dang = 0

    for nguon in NGUON_TIN:
        if so_luong_da_dang >= MAX_ARTICLES_PER_RUN:
            break

        log(f"\n📡 Đang quét nguồn: {nguon['ten']} ({nguon['chu_de']})")
        loi_tren_mot_nguon = 0

        try:
            feed = feedparser.parse(nguon["url"])
        except Exception as e:
            log(f"⚠️ Feed lỗi: {nguon['ten']} | {e}")
            tang_loi()
            continue

        if getattr(feed, "bozo", False):
            log(f"⚠️ Feed có cảnh báo bozo: {nguon['ten']} | {getattr(feed, 'bozo_exception', '')}")
        if not getattr(feed, "entries", None):
            log(f"⏭️ Nguồn không có entries: {nguon['ten']}")
            continue

        for entry in feed.entries:
            if so_luong_da_dang >= MAX_ARTICLES_PER_RUN:
                break
            if loi_tren_mot_nguon >= 3:
                log(f"⏭️ Bỏ qua nguồn {nguon['ten']} vì lỗi 3 lần liên tiếp.")
                break

            THONG_KE["rss_items"] += 1
            title = strip_html(safe_get(entry, "title", "")).strip()
            link = safe_get(entry, "link", "").strip()
            summary = strip_html(safe_get(entry, "summary", "") or safe_get(entry, "description", "")).strip()
            published = safe_get(entry, "published", "") or safe_get(entry, "updated", "")

            if not title or not link:
                log("⏭️ Bỏ qua RSS item thiếu title/link.")
                continue

            log(f"📰 Xét bài: {title[:90]}")

            if da_ton_tai("nguon_bai", link):
                THONG_KE["bo_qua_trung"] += 1
                log("⏭️ Bỏ qua vì nguon_bai đã tồn tại.")
                continue

            qua_filter, ly_do = pre_filter_article(title, summary, nguon["ten"], nguon["chu_de"])
            if not qua_filter:
                THONG_KE["bo_qua_keyword"] += 1
                log(f"⏭️ Bỏ qua pre-filter: {ly_do}")
                continue
            log(f"✅ Qua pre-filter: {ly_do}")

            meta = fetch_page_meta(link)
            THONG_KE["ai_audit"] += 1
            audit = ai_audit_article(
                title=title,
                summary=summary,
                og_description=meta["og_description"],
                source_name=nguon["ten"],
                url=link,
                chu_de=nguon["chu_de"],
            )
            if not audit:
                loi_tren_mot_nguon += 1
                continue

            local_score = int(audit.get("local_score", 0))
            topic_type = audit.get("topic_type", "bo_qua")
            should_create = bool(audit.get("should_create_article"))
            log(f"🔎 AI audit: score={local_score}, topic={topic_type}, create={should_create}, reason={audit.get('reason')}")

            if not should_create or topic_type == "bo_qua" or local_score < 50:
                THONG_KE["ai_loai"] += 1
                log("⏭️ AI loại bài vì không đủ liên quan hoặc điểm thấp.")
                continue

            trung_ai, ly_do_trung_ai = bai_ai_da_ton_tai(audit)
            if trung_ai:
                THONG_KE["bo_qua_trung"] += 1
                log(f"⏭️ Bỏ qua vì trùng bài AI: {ly_do_trung_ai}")
                continue

            html = ai_viet_bai(
                audit=audit,
                source_title=title,
                source_summary=summary,
                og_description=meta["og_description"],
                chu_de=nguon["chu_de"],
                source_url=link,
            )
            if not html:
                loi_tren_mot_nguon += 1
                continue
            THONG_KE["ai_viet"] += 1

            slug_preview = tao_slug(audit.get("suggested_title") or title)
            image_meta = xu_ly_anh_webp(meta["og_image"], slug_preview, topic_type)
            payload = build_payload(audit, html, image_meta, link, meta["canonical_url"], published)

            if DRY_RUN:
                log(
                    "🧪 Bài sẽ đăng: "
                    f"title={payload['tieu_de']} | score={local_score} | topic={topic_type} | "
                    f"cover={payload['anh_bia']}"
                )
                so_luong_da_dang += 1
                THONG_KE["dang_thanh_cong"] += 1
                continue

            result = insert_tin_tuc(payload)
            if result:
                so_luong_da_dang += 1
                THONG_KE["dang_thanh_cong"] += 1
                loi_tren_mot_nguon = 0
                inserted_id = ""
                try:
                    inserted_id = result.data[0].get("id") if result.data else ""
                except Exception:
                    inserted_id = ""
                log(f"✅ [{so_luong_da_dang}/{MAX_ARTICLES_PER_RUN}] Đã đăng: {payload['tieu_de']} | ID={inserted_id}")
                time.sleep(8)
            else:
                loi_tren_mot_nguon += 1

    log("\n🎉 KẾT THÚC BOT")
    log(f"- Tổng RSS items đọc: {THONG_KE['rss_items']}")
    log(f"- Bỏ qua vì trùng: {THONG_KE['bo_qua_trung']}")
    log(f"- Bỏ qua vì keyword: {THONG_KE['bo_qua_keyword']}")
    log(f"- Số bài AI audit: {THONG_KE['ai_audit']}")
    log(f"- Số bài AI loại: {THONG_KE['ai_loai']}")
    log(f"- Số bài AI viết: {THONG_KE['ai_viet']}")
    log(f"- Số bài đăng thành công: {THONG_KE['dang_thanh_cong']}/{MAX_ARTICLES_PER_RUN}")
    log(f"- Tổng lỗi: {TONG_LOI_HE_THONG}")


if __name__ == "__main__":
    try:
        thuc_thi()
    except Exception as e:
        log(f"💥 Bot dừng vì lỗi chưa xử lý: {e}")
        sys.exit(1)
