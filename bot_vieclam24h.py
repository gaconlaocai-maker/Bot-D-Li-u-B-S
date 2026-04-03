import os, sys, re, time, requests, json
from supabase import create_client
from playwright.sync_api import sync_playwright

# ================= 1. CẤU HÌNH HỆ THỐNG =================
def check_config():
    required_keys = ["GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"❌ THIẾU CẤU HÌNH SECRETS: {', '.join(missing)}")
        sys.exit(1)

check_config()

raw_keys = os.environ.get("GROQ_API_KEY", "")
GROQ_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]
if not GROQ_KEYS:
    print("❌ Lỗi: Không tìm thấy GROQ_API_KEY nào hợp lệ!")
    sys.exit(1)

CHOTOT_COOKIE = os.environ.get("CHOTOT_COOKIE", "")
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def tao_slug(s):
    if not s: return ""
    s = str(s).lower()
    s = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', s)
    s = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', s)
    s = re.sub(r'[ìíịỉĩ]', 'i', s)
    s = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', s)
    s = re.sub(r'[ùúụủũưừứựửữ]', 'u', s)
    s = re.sub(r'[ỳýỵỷỹ]', 'y', s)
    s = re.sub(r'đ', 'd', s)
    s = re.sub(r'[^a-z0-9\s-]', '', s) 
    s = re.sub(r'\s+', '-', s)
    return re.sub(r'-+', '-', s).strip('-')

def ai_analyze_job(text_tho):
    if len(text_tho) < 50: return None
    print(f"🤖 Đang nhờ AI tút tát lại nội dung...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    prompt = (
        f"Bạn là Headhunter. Đọc mô tả công việc thô này và trích xuất dữ liệu. KHÔNG BỊA ĐẶT.\n\n"
        f"JSON Format:\n"
        f"{{\n"
        f"  \"kinh_nghiem\": \"VD: 1 năm, hoặc Không yêu cầu\",\n"
        f"  \"so_luong\": \"Số lượng (Điền số nguyên)\",\n"
        f"  \"han_nop\": \"Ngày hết hạn (VD: Đang mở)\",\n"
        f"  \"nhan_fomo\": \"VD: Tuyển gấp, Lương cao, Việc nhẹ...\",\n"
        f"  \"html_clean\": \"Viết lại Mô tả công việc, Yêu cầu, Quyền lợi chuyên nghiệp bằng HTML. Dùng <h3> và <ul>, <li>.\"\n"
        f"}}\n\n"
        f"--- NỘI DUNG RAW ---\n{text_tho[:8000]}"
    )
    
    danh_sach_models = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "llama-3.1-8b-instant"]

    for api_key in GROQ_KEYS:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        for model_name in danh_sach_models:
            payload = { "model": model_name, "messages": [{"role": "user", "content": prompt}], "response_format": { "type": "json_object" }, "temperature": 0.2 }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=35)
                if res.status_code == 200:
                    return json.loads(res.json()['choices'][0]['message']['content'])
            except: continue 
    return None

# ================= 3. QUY TRÌNH HÚT DATA & CLICK LẤY SỐ =================
def run_bot():
    print("🚀 BẮT ĐẦU CÀO DATA VÀ ÉP CHỢ TỐT NHẢ SĐT THẬT")
    
    danh_sach_link_cu = set()
    try:
        res_db = supabase.table("viec_lam").select("link_goc").execute()
        for row in res_db.data:
            if row.get("link_goc"): danh_sach_link_cu.add(row["link_goc"])
        print(f"🛡️ Khiên đã bật! Ghi nhớ {len(danh_sach_link_cu)} job cũ.")
    except: pass

    api_list = "https://gateway.chotot.com/v1/public/ad-listing?cg=13000&q=Lào%20Cai&limit=20"
    da_xu_ly = 0

    # Khởi động cỗ máy Click tự động
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        # Nhét Cookie vào để lách cửa bảo vệ
        if CHOTOT_COOKIE:
            cookies = []
            for item in CHOTOT_COOKIE.split(';'):
                if '=' in item:
                    k, v = item.strip().split('=', 1)
                    cookies.append({
                        "name": k,
                        "value": v,
                        "domain": ".chotot.com",
                        "path": "/"
                    })
            if cookies:
                context.add_cookies(cookies)
                
        page = context.new_page()

        try:
            res = requests.get(api_list, timeout=10)
            ads = res.json().get('ads', [])
            print(f"📋 Tìm thấy {len(ads)} tin.")

            headers_chotot = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Cookie": CHOTOT_COOKIE
            }

            for ad in ads:
                list_id = ad.get('list_id')
                
                # ĐÃ FIX LỖI CHẾT LINK: Đổi tên miền về thẳng www.chotot.com
                detail_url = f"https://www.chotot.com/{list_id}.htm"
                
                if detail_url in danh_sach_link_cu:
                    continue

                print(f"\n--- 🔎 ĐANG SOI: {ad.get('subject')} ---")
                
                api_detail = f"https://gateway.chotot.com/v1/public/ad-listing/{list_id}"
                res_dt = requests.get(api_detail, headers=headers_chotot, timeout=10)
                ad_dt = res_dt.json().get('ad', {})
                
                text_tho = ad_dt.get('body', '')
                hinh_anh = [ad_dt.get('image')] if ad_dt.get('image') else []
                
                so_dien_thoai = ""
                # 1. Quét thẳng vào mô tả trước
                text_clean = text_tho.replace('.', '').replace(' ', '').replace('-', '')
                phone_match = re.search(r'(0[3|5|7|8|9][0-9]{8})', text_clean)
                
                if phone_match:
                    so_dien_thoai = phone_match.group(1)
                    print(f"   🎯 Bắt được SĐT thật trong mô tả: {so_dien_thoai}")
                else:
                    # 2. Nhả Robot vào trình duyệt để CLICK NÚT LẤY SỐ
                    print("   🤖 Đang thả Robot vào web để click nút lấy SĐT...")
                    try:
                        page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(2000)
                        
                        btn = page.locator('text="Nhấn để hiện số"')
                        if btn.count() > 0:
                            btn.first.click(timeout=5000)
                            page.wait_for_timeout(1500) # Đợi nhả số
                            
                        # Sau khi click, lấy SĐT từ thuộc tính tel:
                        tel_links = page.locator('a[href^="tel:"]')
                        if tel_links.count() > 0:
                            so_dien_thoai = tel_links.first.get_attribute('href').replace('tel:', '').replace(' ', '')
                            print(f"   ✅ Robot click thành công, chốt SĐT thật: {so_dien_thoai}")
                        else:
                            so_dien_thoai = ad_dt.get('phone', '')
                            print(f"   ⚠️ Robot bó tay, lấy SĐT ẩn: {so_dien_thoai}")
                    except Exception as e:
                        so_dien_thoai = ad_dt.get('phone', '')
                        print(f"   ⚠️ Lỗi Robot, lấy SĐT ẩn: {so_dien_thoai}")

                tieu_de = ad_dt.get('subject', 'Tuyển dụng Lào Cai')
                muc_luong = ad_dt.get('price_string', 'Thỏa thuận')
                cong_ty = ad_dt.get('company_name', 'Đang cập nhật')
                dia_diem = ad_dt.get('area_name', 'Lào Cai')
                
                ai_data = ai_analyze_job(text_tho)
                
                if ai_data:
                    slug = tao_slug(tieu_de)[:50] + "-" + str(int(time.time()))
                    so_luong = ai_data.get("so_luong")
                    if isinstance(so_luong, str) and not str(so_luong).isdigit(): so_luong = 1

                    data_to_save = {
                        "tieu_de": tieu_de, "slug": slug, "cong_ty": cong_ty,
                        "muc_luong": muc_luong, "vi_tri": dia_diem, 
                        "so_dien_thoai": so_dien_thoai, 
                        "hinh_thuc": "Full-time", "kinh_nghiem": ai_data.get("kinh_nghiem", "Không yêu cầu"),
                        "so_luong": int(so_luong) if so_luong else 1, "han_nop": ai_data.get("han_nop", "Đang mở"),
                        "nhan_fomo": ai_data.get("nhan_fomo", ""), "hinh_anh": hinh_anh,
                        "mo_ta": ai_data.get("html_clean", text_tho), "link_goc": detail_url, "trang_thai": "Chờ duyệt"
                    }

                    supabase.table("viec_lam").insert(data_to_save).execute()
                    danh_sach_link_cu.add(detail_url)
                    da_xu_ly += 1
                    print(f"✅ ĐÃ LƯU THÀNH CÔNG!")
                    
        except Exception as e:
            print(f"❌ Lỗi: {str(e)}")

        print(f"\n🎉 XONG! Thu hoạch: {da_xu_ly} jobs.")

if __name__ == "__main__":
    run_bot()
