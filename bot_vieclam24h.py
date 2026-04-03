import os, sys, re, time, requests, json
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client

# ================= 1. CẤU HÌNH HỆ THỐNG =================
def check_config():
    required_keys = ["GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"❌ THIẾU CẤU HÌNH SECRETS: {', '.join(missing)}")
        sys.exit(1)

check_config()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
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

# ================= 2. AI BIÊN TẬP (CHUYÊN GIA NHÂN SỰ) =================
def ai_analyze_job(url_goc, text_tho):
    print(f"🤖 Đang gửi dữ liệu ({len(text_tho)} ký tự) nhờ AI bóc tách...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
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
            if 'choices' in res_json:
                ai_res = json.loads(res_json['choices'][0]['message']['content'])
                print(f"  ✅ AI [{model_name}] đã trích xuất thành công!")
                return ai_res
        except Exception:
            continue 

    print("⏳ AI quá tải, ép Bot ngủ 60s...")
    time.sleep(60)
    return None

# ================= 3. QUY TRÌNH QUÉT =================
def run_bot():
    print("🚀 BẮT ĐẦU CÀO VIỆC LÀM 24H (LÀO CAI)")
    
    # 1. Dựng khiên chống trùng lặp bằng link_goc
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

    for page in range(1, 4): # Quét 3 trang đầu
        url_page = f"{base_url}?page={page}"
        print(f"\n🌍 ĐANG QUÉT TRANG {page}: {url_page}")
        
        try:
            res = curl_requests.get(url_page, impersonate="chrome", timeout=30)
            soup = BeautifulSoup(res.content, 'html.parser')
            
            # Tìm tất cả các thẻ a có chứa /tuyen-dung/
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/tuyen-dung/' in href and href.endswith('.html'):
                    full_link = "https://vieclam24h.vn" + href if href.startswith('/') else href
                    if full_link not in links: links.append(full_link)

            print(f"📋 Tìm thấy {len(links)} tin trên trang {page}.")

            for detail_url in links:
                if detail_url in danh_sach_link_cu:
                    print(f"⏭️ TIN ĐÃ CÓ: {detail_url[-30:]} -> BỎ QUA!")
                    continue
                
                print(f"\n--- 🔎 ĐANG SOI: {detail_url[-50:]} ---")
                try:
                    res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
                    soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
                    
                    # Lấy text thô để ném cho AI đọc hiểu
                    text_tho = soup_dt.get_text(separator="\n", strip=True)
                    
                    # Lấy ảnh đại diện (og:image)
                    meta_img = soup_dt.find("meta", property="og:image")
                    hinh_anh = [meta_img["content"]] if meta_img and meta_img.get("content") else []

                    ai_data = ai_analyze_job(detail_url, text_tho)
                    
                    if ai_data:
                        tieu_de = ai_data.get("tieu_de_moi", "Tuyển dụng Việc làm Lào Cai")
                        slug = tao_slug(tieu_de)[:50] + "-" + str(int(time.time()))
                        so_luong = ai_data.get("so_luong")
                        if isinstance(so_luong, str) and not so_luong.isdigit(): so_luong = 1

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
                            "trang_thai": "Chờ duyệt" # Vào mục Chờ duyệt để sếp lọc
                        }

                        supabase.table("viec_lam").insert(data_to_save).execute()
                        danh_sach_link_cu.add(detail_url)
                        da_xu_ly += 1
                        print(f"✅ ĐÃ LƯU: {tieu_de[:40]}...")
                        
                    time.sleep(5) # Tránh bị khoá IP
                except Exception as e:
                    print(f"❌ Lỗi xử lý tin: {str(e)}")

            print(f"Đã xong trang {page}. Nghỉ mệt 10s...")
            time.sleep(10)

        except Exception as e:
            print(f"❌ Lỗi trang {page}: {e}")

    print(f"\n🎉 XONG! Đã thu hoạch: {da_xu_ly} jobs.")

if __name__ == "__main__":
    run_bot()
