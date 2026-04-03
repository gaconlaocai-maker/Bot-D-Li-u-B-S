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
    match = re.search(r'\d+([.,]\d+)?', str(text))
    if match:
        num_str = match.group().replace(',', '.')
        return int(float(num_str)) 
    return 0

# ================= 2. AI BIÊN TẬP (JSON MODE) =================
def ai_analyze_bds(tieu_de, ngu_canh_tho):
    print(f"🤖 Đang gửi dữ liệu thô sang AI (Độ dài: {len(ngu_canh_tho)} ký tự)...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia BĐS Lào Cai. Hãy đọc bài đăng thô và trả về ĐÚNG định dạng JSON sau:\n"
        f"{{\n"
        f"  \"loai_bds\": \"Phân loại BĐS (vd: Nhà riêng, Đất nền, Biệt thự, Căn hộ...)\",\n"
        f"  \"html_clean\": \"Viết lại nội dung bằng mã HTML sạch (<p>, <ul>, <li>), TUYỆT ĐỐI XÓA SẠCH SĐT, link và tên môi giới\"\n"
        f"}}\n\n"
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
        ai_res = json.loads(res.json()['choices'][0]['message']['content'])
        print("✅ AI đã xử lý xong và trả về JSON.")
        return ai_res
    except Exception as e:
        print(f"⚠️ Lỗi AI Groq: {str(e)}")
        return None

# ================= 3. XỬ LÝ HÌNH ẢNH =================
def process_image(url_goc, slug):
    try:
        if not url_goc: 
            return ""
        
        res = curl_requests.get(url_goc, impersonate="chrome", timeout=20)
        img_data = io.BytesIO(res.content)
        
        with Image.open(img_data) as img:
            rgb_img = img.convert("RGB")
            buffer = io.BytesIO()
            rgb_img.save(buffer, format="WEBP", quality=75)
            buffer.seek(0)
            up = cloudinary.uploader.upload(buffer, folder="sapa_bds", public_id=slug)
            print(f"    + Đã tải ảnh lên mây: {up['secure_url'][:40]}...")
            return up['secure_url']
    except Exception as e:
        print(f"    ⚠️ Lỗi xử lý ảnh: {str(e)}")
        return ""

# ================= 4. QUY TRÌNH QUÉT CHÍNH =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 BẮT ĐẦU CHẾ ĐỘ TEST: CHỈ LẤY 2 BĐS VÀ SOI LOG CHI TIẾT")
    
    da_xu_ly = 0
    gioi_han = 2

    res = curl_requests.get(base_url, impersonate="chrome", timeout=30)
    soup = BeautifulSoup(res.content, 'html.parser')
    cards = soup.select('div.re__card-full-compact, div.js__card')
    
    print(f"📋 Tìm thấy tổng cộng {len(cards)} tin trên trang 1.")

    for card in cards:
        if da_xu_ly >= gioi_han:
            break

        try:
            link_tag = card.select_one('a.js__product-link-for-product-id')
            if not link_tag: continue
            detail_url = "https://batdongsan.com.vn" + link_tag['href']

            print(f"\n--- 🔎 ĐANG SOI TIN {da_xu_ly + 1}: {detail_url[-20:]} ---")
            
            res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
            soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
            
            # --- 1. SOI MÔ TẢ ---
            desc_body = soup_dt.select_one('.re__section-body.re__detail-content.js__section-body, .re__detail-content, .js__section-body')
            raw_desc = desc_body.get_text(separator="\n", strip=True) if desc_body else ""
            if raw_desc:
                print(f"📍 Mô tả: ✅ Đã lấy ({len(raw_desc)} ký tự).")
            else:
                print("📍 Mô tả: ❌ KHÔNG TÌM THẤY (Selector hỏng hoặc trang trống)!")

            # --- 2. SOI THÔNG SỐ (SPECS) ---
            specs = soup_dt.select('.re__pr-specs-content-item')
            raw_specs = "\n".join([s.get_text(strip=True) for s in specs])
            
            # --- 3. SOI ẢNH TỪ SLIDER (BẢN VÁ LỖI) ---
            raw_img_urls = []
            # Cào tất cả thẻ img nằm trong khung chứa hình ảnh (ưu tiên data-src để lấy ảnh xịn)
            img_tags = soup_dt.select('.js__pr-image-item img, .re__pr-image-item img, swiper-slide img, .js__image-item img, .re__media-image img')
            
            for img in img_tags:
                src = img.get('data-src') or img.get('src')
                if src and "http" in src and src not in raw_img_urls:
                    raw_img_urls.append(src)
            
            # Nếu web đổi cấu trúc không lấy được slider, lúc đó mới dùng ảnh Meta dự phòng
            if not raw_img_urls:
                meta_img = soup_dt.find("meta", property="og:image")
                if meta_img and meta_img.get("content"):
                    raw_img_urls.append(meta_img.get("content"))
            
            # Giới hạn lấy 5 ảnh để không làm nặng hệ thống Cloudinary
            raw_img_urls = raw_img_urls[:5]
            print(f"📍 Ảnh: Đã nhặt được {len(raw_img_urls)} ảnh từ bài đăng.")

            # --- 4. GỬI AI ---
            full_context = f"MÔ TẢ:\n{raw_desc}\n\nTHÔNG SỐ:\n{raw_specs}"
            ai_data = ai_analyze_bds(card.select_one('h3').get_text(), full_context)
            
            if ai_data:
                # 5. XỬ LÝ VÀ LƯU THỬ NGHIỆM
                title = card.select_one('h3').get_text(strip=True)
                slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
                
                print("⏳ Đang nén và đưa ảnh lên Cloudinary...")
                final_images = []
                for idx, url in enumerate(raw_img_urls):
                    img_slug = f"{slug}-img{idx}"
                    up_url = process_image(url, img_slug)
                    if up_url:
                        final_images.append(up_url)

                data_to_save = {
                    "tieu_de": title,
                    "slug": slug,
                    "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                    "dien_tich": extract_number(card.select_one('span.re__card-config-area').get_text()),
                    "loai_bds": ai_data.get("loai_bds", "Nhà đất"),
                    "hinh_anh": final_images, # Truyền cả mảng ảnh vào đây
                    "mo_ta": ai_data.get("html_clean"),
                    "vi_tri_hien_thi": [detail_url]
                }

                supabase.table("bds_ban").insert(data_to_save).execute()
                print(f"✅ Đã lưu tin test {da_xu_ly + 1} vào Supabase với {len(final_images)} ảnh.")
                da_xu_ly += 1
            
            time.sleep(10)

        except Exception as e:
            print(f"❌ Lỗi xử lý tin {da_xu_ly + 1}: {str(e)}")

    print(f"\n🎉 KẾT THÚC THỬ NGHIỆM. Tổng số tin đã soi: {da_xu_ly}")

if __name__ == "__main__":
    run_bot()
