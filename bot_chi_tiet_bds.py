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
        print(f"❌ THIẾU CẤU HÌNH: {', '.join(missing)}")
        sys.exit(1)

check_config()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
cloudinary.config(cloudinary_url=os.environ.get("CLOUDINARY_URL"))

def extract_number(text):
    """Chuyển đổi văn bản thành số nguyên cho các cột int4"""
    if not text: return 0
    match = re.search(r'\d+', str(text).replace('.', '').replace(',', ''))
    return int(match.group()) if match else 0

# ================= 2. AI BIÊN TẬP CHUYÊN SÂU (JSON MODE) =================
def ai_analyze_bds(tieu_de, ngu_canh_tho):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia marketing BĐS tại Lào Cai. Hãy đọc dữ liệu sau và trả về JSON.\n"
        f"YÊU CẦU:\n"
        f"1. Viết lại mô tả sang HTML chuyên nghiệp (thẻ <p>, <ul>, <li>), xóa sạch SĐT/tên môi giới.\n"
        f"2. Trích xuất chính xác: Pháp lý, Hướng nhà, Số phòng, Loại hình BĐS.\n"
        f"3. Tạo Meta Title và Meta Description chuẩn SEO cho thị trường Sa Pa.\n\n"
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
        print(f"⚠️ Lỗi AI: {str(e)}")
        return None

# ================= 3. XỬ LÝ HÌNH ẢNH WEBP =================
def process_image(url_goc, slug):
    try:
        if not url_goc: return ""
        res = requests.get(url_goc, timeout=20)
        img_data = io.BytesIO(res.content)
        with Image.open(img_data) as img:
            rgb_img = img.convert("RGB")
            buffer = io.BytesIO()
            rgb_img.save(buffer, format="WEBP", quality=75)
            buffer.seek(0)
            up = cloudinary.uploader.upload(buffer, folder="sapa_bds", public_id=slug)
            return up['secure_url']
    except:
        return url_goc

# ================= 4. QUY TRÌNH QUÉT DỮ LIỆU CHI TIẾT =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 Khởi động Bot BĐS Sa Pa - Chế độ xử lý dữ liệu chuyên sâu...")

    for page in range(1, 4):
        url = base_url if page == 1 else f"{base_url}/p{page}"
        try:
            res = curl_requests.get(url, impersonate="chrome", timeout=30)
            soup = BeautifulSoup(res.content, 'html.parser')
            cards = soup.select('div.re__card-full-compact, div.js__card')
            
            print(f"\n📄 Đang quét Trang {page} (Tìm thấy {len(cards)} tin)")

            for card in cards:
                try:
                    link_tag = card.select_one('a.js__product-link-for-product-id')
                    if not link_tag: continue
                    detail_url = "https://batdongsan.com.vn" + link_tag['href']

                    # 1. KIỂM TRA TRÙNG (Sửa lỗi cho cột Mảng)
                    check = supabase.table("bds_ban").select("id").contains("vi_tri_hien_thi", [detail_url]).execute()
                    if len(check.data) > 0: continue

                    # 2. LẤY NỘI DUNG CHI TIẾT (Cập nhật Selector mới nhất)
                    res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
                    soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
                    
                    # Lấy mô tả đa lớp (fallback)
                    desc_body = soup_dt.select_one('div.re__detail-content, div.re__section-body, div.js__section-body')
                    raw_desc = desc_body.get_text(separator="\n", strip=True) if desc_body else ""
                    
                    # Lấy đặc điểm kỹ thuật (Pháp lý, Mặt tiền...)
                    specs = soup_dt.select('div.re__pr-specs-content-item')
                    raw_specs = "\n".join([s.get_text(strip=True) for s in specs])
                    
                    if not raw_desc:
                        print(f"⚠️ Bỏ qua: Không lấy được nội dung cho {detail_url[-15:]}")
                        continue

                    # 3. AI XỬ LÝ & BIÊN TẬP
                    full_context = f"MÔ TẢ:\n{raw_desc}\n\nTHÔNG SỐ:\n{raw_specs}"
                    ai_data = ai_analyze_bds(card.select_one('h3').get_text(), full_context)
                    if not ai_data: continue

                    # 4. XỬ LÝ ẢNH & SLUG
                    title = card.select_one('h3').get_text(strip=True)
                    slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
                    
                    img_tag = soup_dt.select_one('div.re__pr-image-item img, div.re__pr-image-item-main img')
                    img_url = img_tag.get('data-src') or img_tag.get('src') if img_tag else ""
                    final_img = process_image(img_url, slug)

                    # 5. LƯU VÀO DATABASE (Khớp chính xác cột bảng bds_ban)
                    data_to_save = {
                        "tieu_de": title,
                        "slug": slug,
                        "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                        "dien_tich": extract_number(card.select_one('span.re__card-config-area').get_text()),
                        "vi_tri": "Sa Pa, Lào Cai",
                        "loai_bds": ai_data.get("loai_bds"),
                        "hinh_anh": [final_img] if final_img else [], # Dạng Mảng
                        "mo_ta": ai_data.get("html_clean"),
                        "trang_thai": "Mở bán",
                        "nhan_fomo": ai_data.get("nhan_fomo"),
                        "phong_ngu": extract_number(ai_data.get("phong_ngu")),
                        "phong_tam": extract_number(ai_data.get("phong_tam")),
                        "huong_nha": ai_data.get("huong_nha") or "Không xác định",
                        "phap_ly": ai_data.get("phap_ly") or "Đang cập nhật",
                        "meta_title": ai_data.get("meta_title"),
                        "meta_desc": ai_data.get("meta_desc"),
                        "vi_tri_hien_thi": [detail_url] # Dạng Mảng
                    }

                    supabase.table("bds_ban").insert(data_to_save).execute()
                    print(f"✅ Đã lưu: {title[:35]}...")
                    
                    time.sleep(15) # Nghỉ để an toàn cho IP

                except Exception as e:
                    print(f"❌ Lỗi tin đăng: {str(e)}")
                    continue
        except Exception as e:
            print(f"❌ Lỗi quét trang: {str(e)}")

if __name__ == "__main__":
    run_bot()
