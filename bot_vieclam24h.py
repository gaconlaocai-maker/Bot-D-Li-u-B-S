import os, sys, re, time, requests, json, traceback
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

# ================= 2. VŨ KHÍ TỐI THƯỢNG: TRÌNH DUYỆT ẢO =================
def lay_html_vuot_rao(url):
    print(f"   [+] Mở Chrome ẩn danh lách Cloudflare: {url[-40:]}...")
    html_content = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000) # Đợi 5 giây giải toán Cloudflare
            html_content = page.content()
        except Exception as e:
            print(f"   [!] Lỗi khi load trang: {str(e)}")
        finally:
            browser.close()
    return html_content

# ================= 3. AI BIÊN TẬP =================
def ai_analyze_job(url_goc, text_tho):
    print(f"🤖 Đang gửi dữ liệu ({len(text_tho)} ký tự) nhờ AI bóc tách...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    prompt = (
        f"Bạn là một Headhunter chuyên nghiệp. Hãy đọc thông tin trang tuyển dụng và trích xuất dữ liệu.\n"
        f"KHÔNG ĐƯỢC BỊA ĐẶT THÔNG TIN.\n\n"
        f"Hãy trả về JSON chính xác với cấu trúc sau:\n"
        f"{{\n"
        f"  \"tieu_de_moi\": \"Tên vị trí tuyển dụng (VD: Nhân viên Lễ tân Khách sạn)\",\n"
        f"  \"cong_ty\": \"Tên công ty hoặc nhà tuyển dụng (nếu có)\",\n"
        f"  \"muc_luong\": \"VD: 7 - 10 Triệu, hoặc Thỏa thuận\",\n"
        f"  \"dia_diem\": \"Địa điểm làm việc cụ thể (VD: Sa Pa, Lào Cai)\",\n"
        f"  \"hinh_thuc\": \"Chỉ chọn: Full-time hoặc Part-time\",\n"
        f"  \"kinh_nghiem\": \"VD: 1 năm, hoặc Không yêu cầu\",\n"
        f"  \"so_luong\": \"Số lượng tuyển (VD: 2) - Điền số nguyên\",\n"
        f"  \"han_nop\": \"Ngày hết hạn (VD: 30/05/2026, hoặc Đang mở)\",\n"
        f"  \"nhan_fomo\": \"Nhãn ngắn gọn (VD: Tuyển gấp, Lương cao, Chế độ tốt)\",\n"
        f"  \"html_clean\": \"Viết lại phần Mô tả công việc, Yêu cầu, Quyền lợi cực kỳ chuyên nghiệp và rõ ràng bằng HTML. Dùng <h3> cho tiêu đề và <ul>, <li> để liệt kê.\"\n"
        f"}}\n\n"
        f"--- NỘI DUNG RAW ---\n{text_tho[:8000]}"
    )
    
    danh_sach_models = [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "llama-3.1-8b-instant"
    ]

    for api_key in GROQ_KEYS:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        for model_name in danh_sach_models:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": { "type": "json_object" },
                "temperature": 0.2 
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=35)
                res_json = res.json()
                if res.status_code == 200 and 'choices' in res_json:
                    ai_res = json.loads(res_json['choices'][0]['message']['content'])
                    print(f"  ✅ AI [{model_name}] đã trích xuất thành công!")
                    return ai_res
                elif res.status_code == 429:
                    print(f"  ⚠️ Key/Model [{model_name}] bị Rate Limit. Đang chuyển súng...")
                    continue 
                else:
                    continue
            except Exception:
                continue 

    print("⏳ Toàn bộ băng đạn AI đều đã cạn kiệt, ép Bot ngủ 60s hồi máu...")
    time.sleep(60)
    return None

# ================= 4. QUY TRÌNH QUÉT CHÍNH =================
def run_bot():
    print("🚀 BẮT ĐẦU CÀO VIỆC LÀM 24H (CHẾ ĐỘ TRÌNH DUYỆT ẢO)")
    print(f"🔫 Số lượng API Key đã nạp: {len(GROQ_KEYS)} keys.")
    
    print("🗄️ Đang tải dữ liệu Két sắt để dựng khiên...")
    danh_sach_link_cu = set()
    try:
        res_db = supabase.table("viec_lam").select("link_goc").execute()
        for row in res_db.data:
            if row.get("link_goc"): danh_sach_link_cu.add(row["link_goc"])
        print(f"🛡️ Khiên đã bật! Ghi nhớ {len(danh_sach_link_cu)} job cũ.")
    except Exception as e:
        print(f"⚠️ Lỗi tải khiên: {e}")

    base_url = "https://vieclam24h.vn/viec-lam-lao-cai-p78.html"
    da_xu_ly = 0

    for page in range(1, 2): 
        url_page = f"{base_url}?page={page}"
        print(f"\n🌍 ĐANG QUÉT TRANG {page}: {url_page}")
        
        try:
            html_page = lay_html_vuot_rao(url_page)
            soup = BeautifulSoup(html_page, 'html.parser')
            
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href'].split('?')[0] 
                if re.search(r'id\d+\.html$', href) and 'danh-sach-tin-tuyen-dung' not in href:
                    full_link = "https://vieclam24h.vn" + href if href.startswith('/') else href
                    if full_link not in links: links.append(full_link)

            print(f"📋 Tìm thấy {len(links)} tin trên trang {page}.")

            for detail_url in links:
                if detail_url in danh_sach_link_cu:
                    print(f"⏭️ TIN ĐÃ CÓ: {detail_url[-30:]} -> BỎ QUA!")
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
                        tieu_de = ai_data.get("tieu_de_moi", "Tuyển dụng Việc làm Lào Cai")
                        slug = tao_slug(tieu_de)[:50] + "-" + str(int(time.time()))
                        so_luong = ai_data.get("so_luong")
                        if isinstance(so_luong, str) and not str(so_luong).isdigit(): so_luong = 1

                        data_to_save = {
                            "tieu_de": tieu_de,
                            "slug": slug,
                            "cong_ty": ai_data.get("cong_ty", "Đang cập nhật"),
                            "muc_luong": str(ai_data.get("muc_luong", "Thỏa thuận")),
                            "dia_diem": ai_data.get("dia_diem", "Lào Cai"),
                            "hinh_thuc": ai_data.get("hinh_thuc", "Full-time"),
                            "kinh_nghiem": ai_data.get("kinh_nghiem", "Không yêu cầu"),
                            "so_luong": int(so_luong) if so_luong else 1,
                            "han_nop": ai_data.get("han_nop", "Đang mở"),
                            "nhan_fomo": ai_data.get("nhan_fomo", ""),
                            "hinh_anh": hinh_anh,
                            "mo_ta": ai_data.get("html_clean", ""),
                            "link_goc": detail_url,
                            "trang_thai": "Chờ duyệt"
                        }

                        supabase.table("viec_lam").insert(data_to_save).execute()
                        danh_sach_link_cu.add(detail_url)
                        da_xu_ly += 1
                        print(f"✅ ĐÃ LƯU: {tieu_de[:40]}...")
                        
                except Exception as e:
                    print(f"❌ Lỗi xử lý tin: {str(e)}")
                    traceback.print_exc()

        except Exception as e:
            print(f"❌ Lỗi quét trang {page}: {str(e)}")
            traceback.print_exc()

    print(f"\n🎉 XONG! Đã thu hoạch: {da_xu_ly} jobs.")

if __name__ == "__main__":
    run_bot()
