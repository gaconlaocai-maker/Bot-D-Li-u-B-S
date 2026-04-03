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

# ================= 2. AI BIÊN TẬP (JSON MODE) =================
def ai_analyze_bds(tieu_de, ngu_canh_tho):
    print(f"🤖 Đang gửi dữ liệu thô sang AI (Độ dài: {len(ngu_canh_tho)} ký tự)...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia BĐS Lào Cai. Hãy đọc bài đăng và trả về JSON.\n"
        f"Yêu cầu: Viết lại HTML sạch (<p>, <ul>, <li>), xóa sạch SĐT/tên môi giới.\n"
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
            print("📍 Ảnh: ❌ Không có URL để xử lý.")
            return ""
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
        res = requests.get(url_goc, headers=headers, timeout=20)
        img_data = io.BytesIO(res.content)
        with Image.open(img_data) as img:
            rgb_img = img.convert("RGB")
            buffer = io.BytesIO()
            rgb_img.save(buffer, format="WEBP", quality=75)
            buffer.seek(0)
            up = cloudinary.uploader.upload(buffer, folder="sapa_bds", public_id=slug)
            print(f"📍 Ảnh: ✅ Đã nén và tải lên Cloudinary ({up['secure_url'][:50]}...)")
            return up['secure_url']
    except Exception as e:
        print(f"⚠️ Lỗi xử lý ảnh: {str(e)}")
        return url_goc

# ================= 4. QUY TRÌNH QUÉT THỬ NGHIỆM (2 TIN) =================
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
                print(f"📍 Mô tả: ✅ Đã lấy ({len(raw_desc)} ký tự). Đoạn đầu: {raw_desc[:50]}...")
            else:
                print("📍 Mô tả: ❌ KHÔNG TÌM THẤY (Selector hỏng hoặc trang trống)!")

            # --- 2. SOI THÔNG SỐ (SPECS) ---
            specs = soup_dt.select('.re__pr-specs-content-item')
            print(f"📍 Thông số: Tìm thấy {len(specs)} mục.")
            raw_specs = "\n".join([s.get_text(strip=True) for s in specs])
            
            # --- 3. SOI ẢNH ---
            img_url = ""
            meta_img = soup_dt.find("meta", property="og:image")
            if meta_img:
                img_url = meta_img.get("content")
                print(f"📍 Ảnh (Meta): ✅ Tìm thấy: {img_url[:50]}...")
            
            if not img_url:
                img_tag = soup_dt.select_one('.re__pr-image-item img, .re__pr-image-item-main img, .js__pr-image-item img')
                if img_tag:
                    img_url = img_tag.get('data-src') or img_tag.get('src') or ""
                    print(f"📍 Ảnh (Carousel): ✅ Tìm thấy: {img_url[:50]}...")
                else:
                    print("📍 Ảnh: ❌ KHÔNG TÌM THẤY TRONG THẺ HTML!")

            # --- 4. GỬI AI ---
            full_context = f"MÔ TẢ:\n{raw_desc}\n\nTHÔNG SỐ:\n{raw_specs}"
            ai_data = ai_analyze_bds(card.select_one('h3').get_text(), full_context)
            
            if ai_data:
                # 5. LƯU THỬ NGHIỆM
                title = card.select_one('h3').get_text(strip=True)
                slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
                final_img = process_image(img_url, slug)

                data_to_save = {
                    "tieu_de": title,
                    "slug": slug,
                    "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                    "dien_tich": extract_number(card.select_one('span.re__card-config-area').get_text()),
                    "loai_bds": ai_data.get("loai_bds", "Nhà đất"),
                    "hinh_anh": [final_img] if final_img else [],
                    "mo_ta": ai_data.get("html_clean"),
                    "vi_tri_hien_thi": [detail_url]
                }

                supabase.table("bds_ban").insert(data_to_save).execute()
                print(f"✅ Đã lưu tin test {da_xu_ly + 1} vào Supabase.")
                da_xu_ly += 1
            
            time.sleep(10)

        except Exception as e:
            print(f"❌ Lỗi xử lý tin {da_xu_ly + 1}: {str(e)}")

    print(f"\n🎉 KẾT THÚC THỬ NGHIỆM. Tổng số tin đã soi: {da_xu_ly}")

if __name__ == "__main__":
    run_bot()
