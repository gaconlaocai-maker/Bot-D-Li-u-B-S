# ================= 1. CẤU HÌNH HỆ THỐNG & BIẾN TOÀN CỤC =================
GROQ_KEYS_STR = os.environ.get("GROQ_API_KEY", "")
DANH_SACH_GROQ_KEYS = [k.strip() for k in GROQ_KEYS_STR.split(",") if k.strip()]
DANH_SACH_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
vi_tri_groq_key = 0 # Lưu lại vị trí key đang dùng

supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# ... (Giữ nguyên danh sách NGUON_TIN và hàm kiem_tra_gioi_han_loi của sếp) ...

# ================= 2. GỌI API GROQ (XOAY VÒNG KEY & MODEL) =================
def goi_ai_groq(prompt):
    global vi_tri_groq_key, TONG_LOI_HE_THONG
    if not DANH_SACH_GROQ_KEYS: return None

    so_key_da_thu = 0
    while so_key_da_thu < len(DANH_SACH_GROQ_KEYS):
        key_hien_tai = DANH_SACH_GROQ_KEYS[vi_tri_groq_key]

        # Thử xoay vòng 3 model trên key hiện tại
        for model in DANH_SACH_MODELS:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key_hien_tai}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data:
                        print(f"🪄 Groq ({model}) xử lý thành công bằng Key số {vi_tri_groq_key + 1}!")
                        return data["choices"][0]["message"]["content"].replace("```html", "").replace("```", "").strip()
                elif res.status_code in [429, 401, 403]:
                    print(f"⚠️ Key {vi_tri_groq_key + 1} nghẽn model {model}. Đổi model tiếp theo...")
                    continue # Thử model tiếp theo
                else:
                    continue
            except Exception as e:
                print(f"⚠️ Lỗi mạng Groq (Model {model}): {e}")
                continue

        # Nếu chạy hết vòng for (cả 3 model) mà vẫn không có kết quả -> Key này đã cạn sạch ngạch
        print(f"❌ Key số {vi_tri_groq_key + 1} đã cạn sạch cả 3 models. Chuyển sang Key tài khoản khác!")
        vi_tri_groq_key = (vi_tri_groq_key + 1) % len(DANH_SACH_GROQ_KEYS)
        so_key_da_thu += 1

    # Nếu chạy hết vòng while (tất cả 4 key đều tử trận)
    TONG_LOI_HE_THONG += 1
    kiem_tra_gioi_han_loi()
    return None
