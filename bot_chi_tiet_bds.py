import os, sys, re, time, requests, io, json, cloudinary, cloudinary.uploader
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. CẤU HÌNH HỆ THỐNG =================
def check_config():
    required_keys = ["GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "CLOUDINARY_URL"]
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"❌ THIẾU CẤU HÌNH SECRETS: {', '.join(missing)}")
        sys.exit(1)

check_config()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
cloudinary.config(cloudinary_url=os.environ.get("CLOUDINARY_URL"))

def extract_number(text):
    if not text: return 0
    match = re.search(r'\d+', str(text).replace('.', '').replace(',', ''))
    return int(match.group()) if match else 0

# ================= 2. AI BIÊN TẬP CHUYÊN SÂU (JSON MODE) =================
def ai_analyze_bds(tieu_de, ngu_canh_tho):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia marketing BĐS Lào Cai. Hãy đọc bài đăng và trả về JSON.\n"
        f"YÊU CẦU: Viết lại HTML sạch (<p>, <ul>, <li>), xóa sạch SĐT/tên môi giới.\n"
        f"Nội dung thô: {ngu_canh_tho}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": { "type": "json_object" },
        "temperature": 0.1
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        return json.loads(res.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f"⚠️ Lỗi AI Groq: {str(e)}")
        return None

# ================= 3. XỬ LÝ HÌNH ẢNH (NÂNG CẤP ĐA LỚP) =================
def process_image(url_goc, slug):
    try:
        if not url_goc or "base64" in url_goc: return ""
        # Thêm Header giả trình duyệt để tải ảnh không bị chặn
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
        res = requests.get(url_goc, headers=headers, timeout=20)
        img_data = io.BytesIO(res.content)
        with Image.open(img_data) as img:
            rgb_img = img.convert("RGB")
            buffer = io.BytesIO()
            rgb_img.save(buffer, format="WEBP", quality=75)
            buffer.seek(0)
            up = cloudinary.uploader.upload(buffer, folder="sapa_bds", public_id=slug)
            return up['secure_url']
    except Exception as e:
        print(f"⚠️ Lỗi xử lý ảnh Cloudinary: {str(e)}")
        return url_goc # Fallback dùng link gốc

# ================= 4. QUY TRÌNH QUÉT DỮ LIỆU TỔNG LỰC =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 BẮT ĐẦU CHIẾN DỊCH QUÉT SÂU BĐS SA PA (Bản sửa lỗi Ảnh)...")

    for page in range(1, 4): # Quét sạch 3 trang danh sách
        url = base_url if page == 1 else f"{base_url}/p{page}"
        try:
            res = curl_requests.get(url, impersonate="chrome", timeout=30)
            soup = BeautifulSoup(res.content, 'html.parser')
            cards = soup.select('div.re__card-full-compact, div.js__card')
            
            print(f"\n📄 TRANG {page}: Tìm thấy {len(cards)} bài đăng.")

            for card in cards:
                try:
                    link_tag = card.select_one('a.js__product-link-for-product-id')
                    if not link_tag: continue
                    detail_url = "https://batdongsan.com.vn" + link_tag['href']

                    # Kiểm tra trùng lặp trên Supabase
                    check = supabase.table("bds_ban").select("id").contains("vi_tri_hien_thi", [detail_url]).execute()
                    if len(check.data) > 0: continue

                    print(f"🔍 Đang xử lý: {detail_url[-15:]}")
                    res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
                    soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
                    
                    # 1. LẤY MÔ TẢ & THÔNG SỐ (Selectors đã test OK trong log của bạn)
                    desc_body = soup_dt.select_one('.re__section-body.re__detail-content.js__section-body, .re__detail-content, .js__section-body')
                    raw_desc = desc_body.get_text(separator="\n", strip=True) if desc_body else ""
                    
                    specs = soup_dt.select('.re__pr-specs-content-item')
                    raw_specs = "\n".join([s.get_text(strip=True) for s in specs])
                    
                    # 2. LẤY ẢNH (BỘ LỌC ĐA ĐIỂM - SỬA LỖI ❌)
                    img_url = ""
                    # Ưu tiên lấy từ thẻ Meta SEO (luôn có ảnh đại diện bài viết)
                    meta_img = soup_dt.find("meta", property="og:image")
                    if meta_img:
                        img_url = meta_img.get("content")
                    
                    # Nếu meta không có, quét sâu vào Carousel
                    if not img_url:
                        img_tag = soup_dt.select_one('.re__pr-image-item img, .re__pr-image-item-main img, .js__pr-image-item img, .re__pr-image-item-main img')
                        if img_tag:
                            img_url = img_tag.get('data-src') or img_tag.get('data-original') or img_tag.get('src') or ""

                    # 3. AI BIÊN TẬP
                    full_context = f"MÔ TẢ:\n{raw_desc}\n\nTHÔNG SỐ:\n{raw_specs}"
                    ai_data = ai_analyze_bds(card.select_one('h3').get_text(), full_context)
                    if not ai_data: continue

                    # 4. XỬ LÝ ẢNH & SLUG
                    title = card.select_one('h3').get_text(strip=True)
                    slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
                    final_img = process_image(img_url, slug)

                    # 5. LƯU DATABASE
                    data_to_save = {
                        "tieu_de": title,
                        "slug": slug,
                        "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                        "dien_tich": extract_number(card.select_one('span.re__card-config-area').get_text()),
                        "vi_tri": "Sa Pa, Lào Cai",
                        "loai_bds": ai_data.get("loai_bds", "Nhà đất"),
                        "hinh_anh": [final_img] if final_img else [],
                        "mo_ta": ai_data.get("html_clean", "Nội dung đang cập nhật"),
                        "phap_ly": ai_data.get("phap_ly") or "Sổ đỏ/Sổ hồng",
                        "huong_nha": ai_data.get("huong_nha"),
                        "phong_ngu": extract_number(ai_data.get("phong_ngu")),
                        "phong_tam": extract_number(ai_data.get("phong_tam")),
                        "meta_title": ai_data.get("meta_title"),
                        "meta_desc": ai_data.get("meta_desc"),
                        "vi_tri_hien_thi": [detail_url]
                    }

                    supabase.table("bds_ban").insert(data_to_save).execute()
                    print(f"✅ Thành công: {title[:30]}...")
                    time.sleep(15)

                except Exception as e:
                    print(f"❌ Lỗi xử lý bài: {str(e)}")
                    continue
        except Exception as e:
            print(f"❌ Lỗi trang {page}: {str(e)}")

if __name__ == "__main__":
    run_bot()
