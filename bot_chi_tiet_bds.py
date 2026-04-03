import os, re, time, requests, io, json, cloudinary, cloudinary.uploader
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. KIỂM TRA BIẾN MÔI TRƯỜNG =================
def check_env():
    keys = ["GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "CLOUDINARY_URL"]
    for k in keys:
        if not os.environ.get(k):
            print(f"❌ THIẾU CẤU HÌNH: Biến môi trường '{k}' chưa được cài đặt trong GitHub Secrets!")
            sys.exit(1)

check_env()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
cloudinary.config(cloudinary_url=os.environ.get("CLOUDINARY_URL"))

# Helper: Trích xuất số
def extract_number(text):
    if not text: return 0
    match = re.search(r'\d+', text.replace('.', '').replace(',', ''))
    return int(match.group()) if match else 0

# ================= 2. AI BIÊN TẬP & BÁO LỖI CHI TIẾT =================
def ai_process_bds(tieu_de, mo_ta_tho):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia dữ liệu BĐS. Hãy đọc và trả về JSON chuẩn.\n"
        f"Nội dung: {mo_ta_tho}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": { "type": "json_object" },
        "temperature": 0.1
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code != 200:
            print(f"⚠️ Lỗi Groq API (Mã {res.status_code}): {res.text}")
            return None
        return json.loads(res.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f"⚠️ Lỗi xử lý AI: {str(e)}")
        return None

# ================= 3. XỬ LÝ ẢNH & BÁO LỖI CLOUDINARY =================
def upload_cloudinary(url_goc, slug):
    try:
        if not url_goc: return ""
        res = requests.get(url_goc, timeout=15)
        img_data = io.BytesIO(res.content)
        with Image.open(img_data) as img:
            rgb_img = img.convert("RGB")
            buffer = io.BytesIO()
            rgb_img.save(buffer, format="WEBP", quality=75)
            buffer.seek(0)
            up = cloudinary.uploader.upload(buffer, folder="sapa_bds", public_id=slug)
            return up['secure_url']
    except Exception as e:
        print(f"⚠️ Lỗi Cloudinary (Ảnh: {url_goc[:30]}...): {str(e)}")
        return url_goc

# ================= 4. QUÉT & BÁO LỖI DATABASE =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 Bot đang chạy...")

    for page in range(1, 4):
        try:
            url = base_url if page == 1 else f"{base_url}/p{page}"
            res = curl_requests.get(url, impersonate="chrome", timeout=30)
            soup = BeautifulSoup(res.content, 'html.parser')
            cards = soup.select('div.re__card-full-compact, div.js__card')
            
            print(f"📄 Trang {page}: Tìm thấy {len(cards)} tin.")

            for card in cards:
                try:
                    link_tag = card.select_one('a.js__product-link-for-product-id')
                    if not link_tag: continue
                    detail_url = "https://batdongsan.com.vn" + link_tag['href']

                    # Kiểm tra trùng trên Supabase
                    check = supabase.table("bds_ban").select("id").eq("vi_tri_hien_thi", detail_url).execute()
                    if len(check.data) > 0: continue

                    # Lấy chi tiết
                    res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
                    soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
                    raw_desc = soup_dt.select_one('div.re__section-body.re__detail-content.js__section-body').get_text(separator="\n")
                    
                    ai_data = ai_process_bds(card.select_one('h3').get_text(), raw_desc)
                    if not ai_data: continue

                    title = card.select_one('h3').get_text(strip=True)
                    slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
                    
                    img_tag = soup_dt.select_one('div.re__pr-image-item img')
                    img_url = img_tag.get('data-src') or img_tag.get('src') if img_tag else ""
                    final_img = upload_cloudinary(img_url, slug)

                    # Lưu và báo lỗi Supabase cụ thể
                    data_to_save = {
                        "tieu_de": title, "slug": slug, "hinh_anh": final_img,
                        "vi_tri_hien_thi": detail_url, "mo_ta": ai_data.get("html_clean")
                        # ... các cột khác giữ nguyên
                    }

                    result = supabase.table("bds_ban").insert(data_to_save).execute()
                    print(f"✅ Thành công: {title[:30]}...")
                    time.sleep(15)

                except Exception as inner_e:
                    print(f"❌ Lỗi xử lý tin đăng: {str(inner_e)}")
                    continue

        except Exception as page_e:
            print(f"❌ Lỗi quét trang {page}: {str(page_e)}")
            continue

if __name__ == "__main__":
    run_bot()
