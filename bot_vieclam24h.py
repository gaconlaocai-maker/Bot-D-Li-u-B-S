import os, sys, re, time, requests, json
from supabase import create_client

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

vi_tri_groq_key = 0 # Biến toàn cục theo dõi Key hiện tại

# Băng đạn 4 Model cực phẩm của Groq (Xếp từ thông minh nhất đến nhanh nhất)
DANH_SACH_MODELS_AI = [
    "openai/gpt-oss-120b",     # Quái vật 120 tỷ tham số, thông minh số 1
    "llama-3.3-70b-versatile", # Quái vật 70 tỷ của Meta, văn phong mượt mà
    "openai/gpt-oss-20b",      # Đệ cứng 20 tỷ tham số
    "llama-3.1-8b-instant"     # Máy bay phản lực 8 tỷ tham số, cứu cánh cuối cùng
]

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

# ================= 2. AI BIÊN TẬP (AUTO-SWITCH KEYS & MODELS) =================
def ai_analyze_job(text_tho):
    global vi_tri_groq_key
    if len(text_tho) < 50: return None
    print(f"🤖 Đang chuẩn bị gửi dữ liệu Job (Độ dài: {len(text_tho)} ký tự) cho AI...")
    
    prompt = (
        f"Bạn là Headhunter chuyên nghiệp. Đọc mô tả công việc thô này và trích xuất dữ liệu. KHÔNG BỊA ĐẶT.\n\n"
        f"JSON Format:\n"
        f"{{\n"
        f"  \"kinh_nghiem\": \"VD: 1 năm, hoặc Không yêu cầu\",\n"
        f"  \"so_luong\": \"Số lượng (Điền số nguyên)\",\n"
        f"  \"han_nop\": \"Ngày hết hạn (VD: Đang mở)\",\n"
        f"  \"nhan_fomo\": \"VD: Tuyển gấp, Lương cao, Việc nhẹ...\",\n"
        f"  \"html_clean\": \"Viết lại Mô tả công việc, Yêu cầu, Quyền lợi chuyên nghiệp, rõ ràng bằng HTML. Dùng <h3> và <ul>, <li>.\"\n"
        f"}}\n\n"
        f"--- NỘI DUNG RAW ---\n{text_tho[:8000]}"
    )
    
    url = "https://api.groq.com/openai/v1/chat/completions"

    # Vòng lặp quét qua từng Model
    for model_name in DANH_SACH_MODELS_AI:
        so_key_da_thu = 0
        
        # Vòng lặp quét qua từng Key cho Model hiện tại
        while so_key_da_thu < len(GROQ_KEYS):
            key = GROQ_KEYS[vi_tri_groq_key]
            print(f"  👉 Đang nhờ AI [{model_name}] (dùng Key số {vi_tri_groq_key + 1}) biên tập Job...")
            
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = { 
                "model": model_name, 
                "messages": [{"role": "user", "content": prompt}], 
                "response_format": { "type": "json_object" }, 
                "temperature": 0.2 
            }
            
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=35)
                
                if res.status_code == 200:
                    res_json = res.json()
                    ai_res = json.loads(res_json['choices'][0]['message']['content'])
                    print(f"  ✅ AI [{model_name}] đã tút tát Job xong!")
                    return ai_res
                else:
                    res_json = res.json()
                    error_msg = res_json.get('error', {}).get('message', str(res.status_code))
                    print(f"  ⚠️ Lỗi Key {vi_tri_groq_key + 1}: {error_msg}")
                    # Đổi sang Key tiếp theo
                    vi_tri_groq_key = (vi_tri_groq_key + 1) % len(GROQ_KEYS)
                    so_key_da_thu += 1
                    time.sleep(1) # Nghỉ 1 nhịp trước khi thử Key mới
                    
            except Exception as e:
                print(f"  ⚠️ Lỗi mạng với Key {vi_tri_groq_key + 1}: {str(e)}")
                vi_tri_groq_key = (vi_tri_groq_key + 1) % len(GROQ_KEYS)
                so_key_da_thu += 1
                time.sleep(1)

    print("⏳ Oảng rồi! Toàn bộ 4 Model và tất cả các Key đều sập. Trả về rỗng để Bot bỏ qua Job này...")
    return None

# ================= 3. QUY TRÌNH HÚT DATA & MOI SĐT TỪ API =================
def run_bot():
    print("🚀 BẮT ĐẦU CÀO DATA VÀ ÉP CHỢ TỐT NHẢ SĐT THẬT TỪ API (AUTO-SWITCH AI)")
    
    danh_sach_link_cu = set()
    try:
        res_db = supabase.table("viec_lam").select("link_goc").execute()
        for row in res_db.data:
            if row.get("link_goc"): danh_sach_link_cu.add(row["link_goc"])
        print(f"🛡️ Khiên đã bật! Ghi nhớ {len(danh_sach_link_cu)} job cũ.")
    except: pass

    api_list = "https://gateway.chotot.com/v1/public/ad-listing?cg=13000&q=Lào%20Cai&limit=20"
    da_xu_ly = 0

    # Bóc tách Token từ Cookie của sếp
    id_token = ""
    private_token = ""
    if CHOTOT_COOKIE:
        match_id = re.search(r'idToken=([^;]+)', CHOTOT_COOKIE)
        if match_id: id_token = match_id.group(1)
        
        match_private = re.search(r'privateToken=([^;]+)', CHOTOT_COOKIE)
        if match_private: private_token = match_private.group(1)

    try:
        res = requests.get(api_list, timeout=10)
        ads = res.json().get('ads', [])
        print(f"📋 Tìm thấy {len(ads)} tin.")

        headers_chotot = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Cookie": CHOTOT_COOKIE,
            # Bơm 2 cái khóa bảo mật này vào thì nó mới chịu nhả SĐT thật
            "Authorization": f"Bearer {id_token}" if id_token else "",
            "cgg": "1"
        }

        for ad in ads:
            list_id = ad.get('list_id')
            account_oid = ad.get('account_oid') # Cần cái này để hỏi SĐT
            
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
            
            # 1. Quét thẳng vào mô tả trước (Cách nhanh nhất)
            text_clean = text_tho.replace('.', '').replace(' ', '').replace('-', '')
            phone_match = re.search(r'(0[3|5|7|8|9][0-9]{8})', text_clean)
            
            if phone_match:
                so_dien_thoai = phone_match.group(1)
                print(f"   🎯 Bắt được SĐT thật trong mô tả: {so_dien_thoai}")
            else:
                # 2. Gọi API KÍN của Chợ Tốt để moi SĐT thật
                if account_oid and private_token:
                    print("   🕵️‍♂️ Đang dùng Thẻ VIP đột nhập kho số...")
                    api_phone = f"https://gateway.chotot.com/v1/public/profile/{account_oid}"
                    headers_phone = headers_chotot.copy()
                    headers_phone["Authorization"] = f"Bearer {private_token}"
                    
                    try:
                        res_phone = requests.get(api_phone, headers=headers_phone, timeout=5)
                        if res_phone.status_code == 200:
                            so_dien_thoai = res_phone.json().get('phone', '')
                            if '*' not in so_dien_thoai and len(so_dien_thoai) >= 10:
                                print(f"   ✅ Đã ép API nhả SĐT thật: {so_dien_thoai}")
                            else:
                                so_dien_thoai = ad_dt.get('phone', '')
                                print(f"   ⚠️ VIP hết hạn, đành lấy SĐT ẩn: {so_dien_thoai}")
                        else:
                            so_dien_thoai = ad_dt.get('phone', '')
                            print(f"   ⚠️ VIP hết hạn, đành lấy SĐT ẩn: {so_dien_thoai}")
                    except:
                        so_dien_thoai = ad_dt.get('phone', '')
                else:
                    so_dien_thoai = ad_dt.get('phone', '')
                    print(f"   ⚠️ Lấy SĐT ẩn từ bài viết: {so_dien_thoai}")

            tieu_de = ad_dt.get('subject', 'Tuyển dụng Lào Cai')
            muc_luong = ad_dt.get('price_string', 'Thỏa thuận')
            cong_ty = ad_dt.get('company_name', 'Đang cập nhật')
            dia_diem = ad_dt.get('area_name', 'Lào Cai')
            
            # GỌI HÀM AI XÀO NẤU MỚI
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
                
            time.sleep(1.5)
                    
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")

    print(f"\n🎉 XONG! Thu hoạch: {da_xu_ly} jobs.")

if __name__ == "__main__":
    run_bot()
