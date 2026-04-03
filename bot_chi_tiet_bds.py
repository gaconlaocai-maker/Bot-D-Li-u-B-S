import os, sys, re, time, requests, io
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client

# ================= 1. CẤU HÌNH HỆ THỐNG =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= 2. BỘ NÃO AI BIÊN TẬP (GROQ) =================
def ai_bien_tap_bds(tieu_de, mo_ta_tho):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia marketing bất động sản tại Lào Cai. "
        f"Hãy viết lại bài đăng sau để đăng lên website sàn giao dịch chuyên nghiệp. "
        f"YÊU CẦU BẮT BUỘC:\n"
        f"1. Xóa sạch mọi số điện thoại và tên môi giới, cá nhân từ bài viết cũ.\n"
        f"2. Chuyển văn phong sang chuyên nghiệp, tin cậy, tập trung vào tiềm năng đầu tư Sa Pa.\n"
        f"3. Chỉ trả về mã HTML sạch (thẻ <p>, <ul>, <li>, <h2>), không có lời bình của AI.\n"
        f"4. Trình bày thông số (Giá, Diện tích, Pháp lý) trong danh sách <ul>.\n\n"
        f"Tiêu đề: {tieu_de}\n"
        f"Mô tả gốc: {mo_ta_tho}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        data = res.json()
        return data['choices'][0]['message']['content'].replace("```html", "").replace("```", "").strip()
    except Exception as e:
        print(f"⚠️ Lỗi AI Groq: {e}")
        return None

# ================= 3. QUÉT DANH SÁCH & CHI TIẾT =================
def lay_danh_sach_tin(url, so_trang):
    print(f"📡 Đang quét Trang {so_trang}...")
    try:
        res = curl_requests.get(url, impersonate="chrome", timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        cards = soup.select('div.re__card-full-compact, div.js__card')
        
        ket_qua = []
        for card in cards:
            link_tag = card.select_one('a.js__product-link-for-product-id')
            if link_tag:
                ket_qua.append({
                    "tieu_de": card.select_one('h3.re__card-title span, span.pr-title').get_text(strip=True),
                    "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                    "dien_tich": card.select_one('span.re__card-config-area').get_text(strip=True),
                    "link": "https://batdongsan.com.vn" + link_tag['href']
                })
        return ket_qua
    except: return []

def lay_chi_tiet_bai_dang(url):
    print(f"🔍 Đang bóc tách chi tiết: {url}")
    try:
        res = curl_requests.get(url, impersonate="chrome", timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        desc_tag = soup.select_one('div.re__section-body.re__detail-content.js__section-body')
        mo_ta = desc_tag.get_text(separator="\n", strip=True) if desc_tag else ""
        
        img_tag = soup.select_one('div.re__pr-image-item img')
        anh_bia = img_tag.get('data-src') or img_tag.get('src') if img_tag else ""
        
        return {"mo_ta": mo_ta, "anh": anh_bia}
    except: return None

# ================= 4. LUỒNG VẬN HÀNH CHÍNH =================
def thuc_thi():
    print("🚀 Khởi động Bot BĐS Sa Pa - Chế độ Deep Scraping & AI Rewrite")
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    
    for i in range(1, 4): # Quét 3 trang để lấy đủ ~49 bài
        url_hien_tai = base_url if i == 1 else f"{base_url}/p{i}"
        tin_tuc_trang = lay_danh_sach_tin(url_hien_tai, i)
        
        for tin in tin_tuc_trang:
            # Kiểm tra trùng lặp
            check = supabase.table("nha_dat_ban").select("id").eq("nguon_goc", tin['link']).execute()
            if len(check.data) > 0: continue

            # Quét sâu & Biên tập
            chi_tiet = lay_chi_tiet_bai_dang(tin['link'])
            if not chi_tiet or not chi_tiet['mo_ta']: continue
            
            noi_dung_ai = ai_bien_tap_bds(tin['tieu_de'], chi_tiet['mo_ta'])
            if not noi_dung_ai: continue

            # Lưu vào Database
            supabase.table("nha_dat_ban").insert({
                "tieu_de": tin['tieu_de'],
                "gia": tin['gia'],
                "dien_tich": tin['dien_tich'],
                "noi_dung_html": noi_dung_ai,
                "anh_dai_dien": chi_tiet['anh'],
                "nguon_goc": tin['link']
            }).execute()

            print(f"✅ Đã lên sàn: {tin['tieu_de'][:40]}...")
            time.sleep(15) # Nghỉ để an toàn cho IP

if __name__ == "__main__":
    thuc_thi()
