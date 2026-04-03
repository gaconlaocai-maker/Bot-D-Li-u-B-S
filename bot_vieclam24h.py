import os, sys, re, time, requests, json, traceback, urllib.parse
from bs4 import BeautifulSoup
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

# ================= 2. NINJA STEALTH (TỰ CHẾ) & PROXY =================
def lay_html_vuot_rao(url):
    print(f"   [+] Mở xe tăng bọc thép húc cổng: {url[-40:]}...")
    html_content = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, 
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # Tự tay tiêm thuốc tàng hình (Xóa dấu vết Bot)
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            """)
            
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.mouse.wheel(0, 1000) # Lăn chuột giả người thật
            page.wait_for_timeout(5000) # Chờ 5s cho Cloudflare nó check xong
            
            html_content = page.content()
            browser.close()

            # Nhận diện nếu bị chặn Checkbox
            if "Just a moment" in html_content or "Cloudflare" in html_content:
                print("   ⚠️ Lộ bài rồi! Đang chui hầm ngầm Proxy...")
                encoded_url = urllib.parse.quote(url)
                proxy_url = f"https://api.allorigins.win/raw?url={encoded_url}"
                res = requests.get(proxy_url, timeout=30)
                if res.status_code == 200:
                    html_content = res.text
                    print("   ✅ Chui hầm thành công!")
    except Exception as e:
        print(f"   [!] Lỗi kết nối: {str(e)}")
        
    return html_content

# ================= 3. AI BIÊN TẬP =================
def ai_analyze_job(url_goc, text_tho):
    if len(text_tho) < 100: return None
    print(f"🤖 Đang gửi dữ liệu ({len(text_tho)} ký tự) nhờ AI bóc tách...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    prompt = (
        f"Bạn là Headhunter. Đọc thông tin và trích xuất dữ liệu. KHÔNG BỊA ĐẶT.\n\n"
        f"JSON Format:\n"
        f"{{\n"
        f"  \"tieu_de_moi\": \"Tên vị trí (VD: Lễ tân Khách sạn)\",\n"
        f"  \"cong_ty\": \"Tên công ty (nếu có)\",\n"
        f"  \"muc_luong\": \"VD: 7 - 10 Triệu\",\n"
        f"  \"dia_diem\": \"Địa điểm làm việc\",\n"
        f"  \"hinh_thuc\": \"Full-time hoặc Part-time\",\n"
        f"  \"kinh_nghiem\": \"VD: 1 năm\",\n"
        f"  \"so_luong\": \"Số lượng (Điền số)\",\n"
        f"  \"han_nop\": \"Ngày hết hạn\",\n"
        f"  \"nhan_fomo\": \"Tuyển gấp, Lương cao...\",\n"
        f"  \"html_clean\": \"Viết lại Mô tả công việc, Yêu cầu, Quyền lợi cực kỳ chuyên nghiệp bằng HTML. Dùng <h3> và <ul>, <li>.\"\n"
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
                    print(f"  ✅ AI [{model_name}] trích xuất xong!")
                    return json.loads(res.json()['choices'][0]['message']['content'])
                elif res.status_code == 429: continue 
            except: continue 

    print("⏳ Đạn AI cạn kiệt, ngủ 60s...")
    time.sleep(60)
    return None

# ================= 4. QUY TRÌNH QUÉT =================
def run_bot():
    print("🚀 BẮT ĐẦU CÀO VIỆC LÀM 24H (CHẾ ĐỘ TÀNG HÌNH TỰ CHẾ)")
    
    danh_sach_link_cu = set()
    try:
        res_db = supabase.table("viec_lam").select("link_goc").execute()
        for row in res_db.data:
            if row.get("link_goc"): danh_sach_link_cu.add(row["link_goc"])
        print(f"🛡️ Khiên đã bật! Ghi nhớ {len(danh_sach_link_cu)} job cũ.")
    except: pass

    base_url = "https://vieclam24h.vn/viec-lam-lao-cai-p78.html"
    da_xu_ly = 0

    for page in range(1, 2): 
        url_page = f"{base_url}?page={page}"
        print(f"\n🌍 ĐANG QUÉT TRANG {page}...")
        
        html_page = lay_html_vuot_rao(url_page)
        soup = BeautifulSoup(html_page, 'html.parser')
        
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].split('?')[0] 
            if re.search(r'id\d+\.html$', href) and 'danh-sach-tin-tuyen-dung' not in href:
                full_link = "https://vieclam24h.vn" + href if href.startswith('/') else href
                if full_link not in links: links.append(full_link)

        print(f"📋 Tìm thấy {len(links)} tin.")

        for detail_url in links:
            if detail_url in danh_sach_link_cu:
                print(f"⏭️ ĐÃ CÓ: {detail_url[-30:]} -> BỎ QUA!")
                continue
            
            print(f"\n--- 🔎 ĐANG SOI: {detail_url[-50:]} ---")
            try:
                html_dt = lay_html_vuot_rao(detail_url)
                soup_dt = BeautifulSoup(html_dt, 'html.parser')
                text_tho = soup_dt.get_text(separator="\n", strip=True)
                
                meta_img = soup_dt.find("meta", property="og:image")
                hinh_anh = [meta_img["content"]] if meta_img and meta_img.get("content") else []

                ai_data = ai_analyze_job(detail_url, text_tho)
                
                if ai_data:
                    tieu_de = ai_data.get("tieu_de_moi", "Tuyển dụng Lào Cai")
                    slug = tao_slug(tieu_de)[:50] + "-" + str(int(time.time()))
                    so_luong = ai_data.get("so_luong")
                    if isinstance(so_luong, str) and not str(so_luong).isdigit(): so_luong = 1

                    data_to_save = {
                        "tieu_de": tieu_de, "slug": slug, "cong_ty": ai_data.get("cong_ty", "Đang cập nhật"),
                        "muc_luong": str(ai_data.get("muc_luong", "Thỏa thuận")), "dia_diem": ai_data.get("dia_diem", "Lào Cai"),
                        "hinh_thuc": ai_data.get("hinh_thuc", "Full-time"), "kinh_nghiem": ai_data.get("kinh_nghiem", "Không yêu cầu"),
                        "so_luong": int(so_luong) if so_luong else 1, "han_nop": ai_data.get("han_nop", "Đang mở"),
                        "nhan_fomo": ai_data.get("nhan_fomo", ""), "hinh_anh": hinh_anh,
                        "mo_ta": ai_data.get("html_clean", ""), "link_goc": detail_url, "trang_thai": "Chờ duyệt"
                    }

                    supabase.table("viec_lam").insert(data_to_save).execute()
                    danh_sach_link_cu.add(detail_url)
                    da_xu_ly += 1
                    print(f"✅ ĐÃ LƯU: {tieu_de[:40]}...")
                    
            except Exception as e:
                print(f"❌ Lỗi xử lý tin: {str(e)}")

    print(f"\n🎉 XONG! Đã thu hoạch: {da_xu_ly} jobs.")

if __name__ == "__main__":
    run_bot()
