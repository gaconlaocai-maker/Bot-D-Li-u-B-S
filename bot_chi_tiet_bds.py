import os, sys, re, time, requests, io, json, cloudinary, cloudinary.uploader
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. CẤU HÌNH HỆ THỐNG =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
cloudinary.config(cloudinary_url=os.environ.get("CLOUDINARY_URL"))

def extract_number(text):
    if not text: return 0
    match = re.search(r'\d+', str(text).replace('.', '').replace(',', ''))
    return int(match.group()) if match else 0

# ================= 2. AI BIÊN TẬP & CHIẾT XUẤT =================
def ai_analyze_bds(tieu_de, mo_ta_tho):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia BĐS Lào Cai. Hãy đọc bài đăng và trả về JSON.\n"
        f"Yêu cầu: Viết lại HTML sạch, xóa SĐT, trích xuất pháp lý, hướng nhà, số phòng.\n\n"
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
        return json.loads(res.json()['choices'][0]['message']['content'])
    except:
        return None

# ================= 3. XỬ LÝ ẢNH =================
def upload_cloudinary(url_goc, slug):
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

# ================= 4. QUY TRÌNH CHÍNH =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 Bot đang chạy và sửa lỗi Array...")

    for page in range(1, 4):
        url = base_url if page == 1 else f"{base_url}/p{page}"
        res = curl_requests.get(url, impersonate="chrome", timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        cards = soup.select('div.re__card-full-compact, div.js__card')

        for card in cards:
            link_tag = card.select_one('a.js__product-link-for-product-id')
            if not link_tag: continue
            detail_url = "https://batdongsan.com.vn" + link_tag['href']

            # KIỂM TRA TRÙNG: Vì cột là mảng, ta dùng filter .contains
            check = supabase.table("bds_ban").select("id").contains("vi_tri_hien_thi", [detail_url]).execute()
            if len(check.data) > 0: continue

            print(f"🔍 Đang xử lý: {detail_url[:50]}...")
            res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
            soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
            desc_tag = soup_dt.select_one('div.re__section-body.re__detail-content.js__section-body')
            raw_desc = desc_tag.get_text(separator="\n") if desc_tag else ""
            
            ai_data = ai_analyze_bds(card.select_one('h3').get_text(), raw_desc)
            if not ai_data: continue

            title = card.select_one('h3').get_text(strip=True)
            slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
            
            img_tag = soup_dt.select_one('div.re__pr-image-item img')
            img_url = img_tag.get('data-src') or img_tag.get('src') if img_tag else ""
            final_img = upload_cloudinary(img_url, slug)

            # ĐÓNG GÓI DỮ LIỆU KHỚP KIỂU MẢNG (ARRAY)
            data_to_save = {
                "tieu_de": title,
                "slug": slug,
                "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                "dien_tich": extract_number(card.select_one('span.re__card-config-area').get_text()),
                "vi_tri": "Sa Pa, Lào Cai",
                "loai_bds": ai_data.get("loai_bds"),
                "hinh_anh": [final_img] if final_img else [], # Chuyển sang Mảng
                "mo_ta": ai_data.get("html_clean"),
                "phap_ly": ai_data.get("phap_ly"),
                "huong_nha": ai_data.get("huong_nha"),
                "phong_ngu": extract_number(ai_data.get("phong_ngu")),
                "phong_tam": extract_number(ai_data.get("phong_tam")),
                "meta_title": ai_data.get("meta_title"),
                "meta_desc": ai_data.get("meta_desc"),
                "vi_tri_hien_thi": [detail_url] # Chuyển sang Mảng để hết lỗi 22P02
            }

            try:
                supabase.table("bds_ban").insert(data_to_save).execute()
                print(f"✅ Đã lưu thành công bài đăng.")
                time.sleep(15)
            except Exception as e:
                print(f"❌ Lỗi ghi Database: {e}")

if __name__ == "__main__":
    run_bot()
