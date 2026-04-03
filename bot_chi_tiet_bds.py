import os, sys, io, re, time, requests, cloudinary, cloudinary.uploader
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. CẤU HÌNH HỆ THỐNG =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cấu hình Cloudinary (Lấy từ biến môi trường CLOUDINARY_URL)
cloudinary.config(cloudinary_url=os.environ.get("CLOUDINARY_URL"))

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
        if "choices" in data:
            print("🪄 AI Groq (Llama 3.3) đã biên tập xong nội dung.")
            return data['choices'][0]['message']['content'].replace("```html", "").replace("```", "").strip()
    except Exception as e:
        print(f"⚠️ Lỗi AI Groq: {e}")
    return None

# ================= 3. XỬ LÝ ẢNH WEBP & CLOUDINARY =================
def xu_ly_anh_bds(url_goc, slug):
    try:
        if not url_goc: return "https://images.unsplash.com/photo-1560518883-ce09059eeffa"
        
        # Tải ảnh qua requests (không cần curl_cffi cho ảnh thường)
        res = requests.get(url_goc, timeout=15)
        img_data = io.BytesIO(res.content)
        
        with Image.open(img_data) as img:
            rgb_img = img.convert("RGB")
            buffer = io.BytesIO()
            # Nén ảnh xuống chất lượng 75% và đổi định dạng WebP
            rgb_img.save(buffer, format="WEBP", quality=75)
            buffer.seek(0)
            
            # Đẩy lên Cloudinary vào thư mục riêng
            up = cloudinary.uploader.upload(buffer, folder="laocai_sapa_bds", public_id=slug)
            return up['secure_url']
    except Exception as e:
        print(f"⚠️ Lỗi xử lý ảnh: {e}")
        return url_goc # Trả về link gốc nếu lỗi để tránh mất ảnh

# ================= 4. QUÉT DANH SÁCH & CHI TIẾT =================
def lay_danh_sach_tin(url, so_trang):
    print(f"\n📡 Đang quét Danh sách Trang {so_trang}...")
    try:
        res = curl_requests.get(url, impersonate="chrome", timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        # Sử dụng selector chuẩn đã test thành công
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
    except Exception as e:
        print(f"⚠️ Lỗi quét danh sách: {e}")
        return []

def lay_chi_tiet_bai_dang(url):
    print(f"🔍 Đang bóc tách chi tiết: {url}")
    try:
        res = curl_requests.get(url, impersonate="chrome", timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Lấy phần mô tả nội dung
        desc_tag = soup.select_one('div.re__section-body.re__detail-content.js__section-body')
        mo_ta = desc_tag.get_text(separator="\n", strip=True) if desc_tag else ""
        
        # Lấy ảnh bìa đầu tiên
        img_tag = soup.select_one('div.re__pr-image-item img')
        anh_bia = img_tag.get('data-src') or img_tag.get('src') if img_tag else ""
        
        return {"mo_ta": mo_ta, "anh_bia": anh_bia}
    except Exception as e:
        print(f"⚠️ Lỗi bóc tách chi tiết: {e}")
        return None

# ================= 5. LUỒNG VẬN HÀNH CHÍNH =================
def thuc_thi():
    print("🚀 KHỞI ĐỘNG BOT BĐS SA PA - PHIÊN BẢN CHUYÊN GIA")
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    so_luong_moi = 0
    
    for i in range(1, 4): # Quét 3 trang để lấy đủ toàn bộ ~50 bài tại Sa Pa
        url_hien_tai = base_url if i == 1 else f"{base_url}/p{i}"
        tin_tuc_trang = lay_danh_sach_tin(url_hien_tai, i)
        
        if not tin_tuc_trang: continue
        
        for tin in tin_tuc_trang:
            try:
                # 1. Kiểm tra trùng lặp trong Database
                check = supabase.table("nha_dat_ban").select("id").eq("nguon_goc", tin['link']).execute()
                if len(check.data) > 0:
                    continue # Bỏ qua nếu đã có bài này

                # 2. Truy cập chi tiết để lấy mô tả và ảnh
                chi_tiet = lay_chi_tiet_bai_dang(tin['link'])
                if not chi_tiet or not chi_tiet['mo_ta']: continue
                
                # 3. AI biên tập lại nội dung sạch sẽ, chuẩn SEO
                noi_dung_ai = ai_bien_tap_bds(tin['tieu_de'], chi_tiet['mo_ta'])
                if not noi_dung_ai: continue

                # 4. Xử lý ảnh đại diện qua Cloudinary (Nén WebP)
                slug = re.sub(r'\W+', '-', tin['tieu_de'].lower())[:50] + "-" + str(int(time.time()))
                anh_final = xu_ly_anh_bds(chi_tiet['anh_bia'], slug)

                # 5. Lưu vào Supabase bảng nha_dat_ban
                supabase.table("nha_dat_ban").insert({
                    "tieu_de": tin['tieu_de'],
                    "slug": slug,
                    "gia": tin['gia'],
                    "dien_tich": tin['dien_tich'],
                    "noi_dung_html": noi_dung_ai,
                    "anh_dai_dien": anh_final,
                    "nguon_goc": tin['link'],
                    "khu_vuc": "Sa Pa"
                }).execute()

                so_luong_moi += 1
                print(f"✅ Đã lên sàn: {tin['tieu_de'][:40]}...")
                
                # Nghỉ 15s giữa mỗi bài để an toàn cho IP và Rate Limit của AI
                time.sleep(15) 
                
            except Exception as e:
                print(f"❌ Lỗi xử lý bài đăng: {e}")
                continue

    print(f"\n🎉 HOÀN THÀNH. Đã cập nhật thêm {so_luong_moi} bất động sản mới vào hệ thống.")

if __name__ == "__main__":
    thuc_thi()
