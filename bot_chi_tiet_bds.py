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
        f"Tiêu đề: {tieu_de}\n"
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
        # Thêm User-Agent để tránh bị chặn khi tải ảnh
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
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
        print(f"⚠️ Lỗi xử lý ảnh: {e}")
        return url_goc

# ================= 4. QUY TRÌNH QUÉT DỮ LIỆU CHI TIẾT =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 Khởi động Bot BĐS Sa Pa - Phiên bản sửa lỗi nội dung...")

    for page in range(1, 4):
        url = base_url if page == 1 else f"{base_url}/p{page}"
        try:
            res = curl_requests.get(url, impersonate="chrome", timeout=30)
            soup = BeautifulSoup(res.content, 'html.parser')
            cards = soup.select('div.re__card-full-compact, div.js__card')
            
            print(f"\n📄 Trang {page}: Tìm thấy {len(cards)} tin")

            for card in cards:
                try:
                    link_tag = card.select_one('a.js__product-link-for-product-id')
                    if not link_tag: continue
                    detail_url = "https://batdongsan.com.vn" + link_tag['href']

                    # Kiểm tra trùng
                    check = supabase.table("bds_ban").select("id").contains("vi_tri_hien_thi", [detail_url]).execute()
                    if len(check.data) > 0: continue

                    print(f"🔍 Bóc tách: {detail_url[-20:]}")
                    res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
                    soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
                    
                    # --- LẤY MÔ TẢ (REFINED SELECTORS) ---
                    # Tìm thẻ div chứa class mô tả chính xác nhất
                    desc_body = soup_dt.select_one('.re__section-body.re__detail-content.js__section-body, .re__detail-content, .js__section-body')
                    raw_desc = desc_body.get_text(separator="\n", strip=True) if desc_body else ""
                    
                    # --- LẤY ĐẶC ĐIỂM KỸ THUẬT (SPECS) ---
                    specs_items = soup_dt.select('.re__pr-specs-content-item')
                    specs_data = []
                    for item in specs_items:
                        label = item.select_one('.re__pr-specs-content-item-title')
                        value = item.select_one('.re__pr-specs-content-item-value')
                        if label and value:
                            specs_data.append(f"{label.get_text(strip=True)}: {value.get_text(strip=True)}")
                    
                    raw_specs = "\n".join(specs_data)
                    full_context = f"THÔNG TIN MÔ TẢ:\n{raw_desc}\n\nĐẶC ĐIỂM BẤT ĐỘNG SẢN:\n{raw_specs}"
                    
                    if not raw_desc and not raw_specs:
                        print("⚠️ Không lấy được nội dung thô.")
                        continue

                    # 3. AI XỬ LÝ
                    ai_data = ai_analyze_bds(card.select_one('h3').get_text(), full_context)
                    if not ai_data: continue

                    # 4. XỬ LÝ ẢNH (Lấy từ carousel hoặc ảnh chính)
                    # Batdongsan dùng data-src cho lazy load ảnh carousel
                    img_tag = soup_dt.select_one('.re__pr-image-item img, .re__pr-image-item-main img, .js__pr-image-item img')
                    img_url = ""
                    if img_tag:
                        img_url = img_tag.get('data-src') or img_tag.get('data-original') or img_tag.get('src') or ""
                    
                    title = card.select_one('h3').get_text(strip=True)
                    slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
                    final_img = process_image(img_url, slug)

                    # 5. LƯU VÀO DATABASE
                    data_to_save = {
                        "tieu_de": title,
                        "slug": slug,
                        "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                        "dien_tich": extract_number(card.select_one('span.re__card-config-area').get_text()),
                        "vi_tri": "Sa Pa, Lào Cai",
                        "loai_bds": ai_data.get("loai_bds", "land"), # Mặc định là land nếu AI lỗi
                        "hinh_anh": [final_img] if final_img else [],
                        "mo_ta": ai_data.get("html_clean", "Nội dung đang cập nhật"),
                        "trang_thai": "Mở bán",
                        "nhan_fomo": ai_data.get("nhan_fomo"),
                        "phong_ngu": extract_number(ai_data.get("phong_ngu")),
                        "phong_tam": extract_number(ai_data.get("phong_tam")),
                        "huong_nha": ai_data.get("huong_nha") or "Không xác định",
                        "phap_ly": ai_data.get("phap_ly") or "Sổ đỏ/Sổ hồng",
                        "meta_title": ai_data.get("meta_title"),
                        "meta_desc": ai_data.get("meta_desc"),
                        "vi_tri_hien_thi": [detail_url]
                    }

                    supabase.table("bds_ban").insert(data_to_save).execute()
                    print(f"✅ Đã lưu: {title[:30]}...")
                    time.sleep(15)

                except Exception as e:
                    print(f"❌ Lỗi tin: {str(e)}")
                    continue
        except Exception as e:
            print(f"❌ Lỗi trang: {str(e)}")

if __name__ == "__main__":
    run_bot()
