import os, re, time, requests, io, json, cloudinary, cloudinary.uploader
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. CẤU HÌNH HỆ THỐNG =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
cloudinary.config(cloudinary_url=os.environ.get("CLOUDINARY_URL"))

# Helper: Trích xuất số từ chuỗi (ví dụ: "350 m2" -> 350) để lưu vào cột int4
def extract_number(text):
    if not text: return 0
    match = re.search(r'\d+', text.replace('.', '').replace(',', ''))
    return int(match.group()) if match else 0

# ================= 2. AI BIÊN TẬP & CHIẾT XUẤT DỮ LIỆU =================
def ai_process_bds(tieu_de, mo_ta_tho):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia dữ liệu BĐS tại Lào Cai. Hãy đọc bài đăng sau và trả về kết quả dưới dạng JSON.\n"
        f"YÊU CẦU:\n"
        f"1. Viết lại mô tả sang HTML sạch (thẻ <p>, <ul>, <li>) chuyên nghiệp, xóa hết SĐT/tên môi giới.\n"
        f"2. Trích xuất các thông số kỹ thuật.\n"
        f"3. Tạo meta_title và meta_desc chuẩn SEO.\n\n"
        f"ĐỊNH DẠNG JSON TRẢ VỀ:\n"
        f"{{\n"
        f"  \"html_clean\": \"nội dung html\",\n"
        f"  \"phap_ly\": \"Sổ đỏ/Hợp đồng...\",\n"
        f"  \"huong_nha\": \"Đông Nam...\",\n"
        f"  \"phong_ngu\": số lượng (int),\n"
        f"  \"phong_tam\": số lượng (int),\n"
        f"  \"loai_bds\": \"Nhà mặt phố/Đất nền...\",\n"
        f"  \"meta_title\": \"tựa đề SEO\",\n"
        f"  \"meta_desc\": \"mô tả SEO\"\n"
        f"}}\n\n"
        f"Nội dung: {mo_ta_tho}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": { "type": "json_object" }, # Ép AI trả về JSON chuẩn
        "temperature": 0.1
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        return json.loads(res.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f"⚠️ Lỗi AI: {e}")
        return None

# ================= 3. XỬ LÝ HÌNH ẢNH =================
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
    except: return url_goc

# ================= 4. QUÉT & LƯU DỮ LIỆU =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 Bắt đầu quét BĐS Sa Pa theo cấu trúc bảng bds_ban...")

    for page in range(1, 4):
        url = base_url if page == 1 else f"{base_url}/p{page}"
        res = curl_requests.get(url, impersonate="chrome", timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        cards = soup.select('div.re__card-full-compact, div.js__card')

        for card in cards:
            link_tag = card.select_one('a.js__product-link-for-product-id')
            if not link_tag: continue
            detail_url = "https://batdongsan.com.vn" + link_tag['href']

            # Kiểm tra trùng
            check = supabase.table("bds_ban").select("id").eq("vi_tri_hien_thi", detail_url).execute()
            if len(check.data) > 0: continue

            # Lấy chi tiết
            res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
            soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
            raw_desc = soup_dt.select_one('div.re__section-body.re__detail-content.js__section-body').get_text(separator="\n")
            
            # AI xử lý
            ai_data = ai_process_bds(card.select_one('h3').get_text(), raw_desc)
            if not ai_data: continue

            # Xử lý thông tin cơ bản
            title = card.select_one('h3').get_text(strip=True)
            slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
            
            # Tải ảnh bìa
            img_tag = soup_dt.select_one('div.re__pr-image-item img')
            img_url = img_tag.get('data-src') or img_tag.get('src') if img_tag else ""
            final_img = upload_cloudinary(img_url, slug)

            # Insert khớp cột dữ liệu
            data_to_save = {
                "tieu_de": title,
                "slug": slug,
                "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                "dien_tich": extract_number(card.select_one('span.re__card-config-area').get_text()),
                "vi_tri": "Sa Pa, Lào Cai",
                "loai_bds": ai_data.get("loai_bds"),
                "hinh_anh": final_img,
                "mo_ta": ai_data.get("html_clean"),
                "phap_ly": ai_data.get("phap_ly"),
                "huong_nha": ai_data.get("huong_nha"),
                "phong_ngu": ai_data.get("phong_ngu"),
                "phong_tam": ai_data.get("phong_tam"),
                "meta_title": ai_data.get("meta_title"),
                "meta_desc": ai_data.get("meta_desc"),
                "vi_tri_hien_thi": detail_url # Lưu link gốc để tránh trùng
            }

            supabase.table("bds_ban").insert(data_to_save).execute()
            print(f"✅ Đã lưu: {title[:40]}...")
            time.sleep(15)

if __name__ == "__main__":
    run_bot()
