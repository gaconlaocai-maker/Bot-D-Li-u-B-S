import os, sys, re, time, requests, io, json, cloudinary, cloudinary.uploader
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. CẤU HÌNH HỆ THỐNG & DÀN API KEYS =================
def check_config():
    required_keys = ["GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "CLOUDINARY_URL"]
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"❌ THIẾU CẤU HÌNH SECRETS: {', '.join(missing)}")
        sys.exit(1)

check_config()

# Lấy dàn Key và tách thành list
GROQ_KEYS_STR = os.environ.get("GROQ_API_KEY", "")
DANH_SACH_GROQ_KEYS = [k.strip() for k in GROQ_KEYS_STR.split(",") if k.strip()]

if not DANH_SACH_GROQ_KEYS:
    print("❌ LỖI: Chưa có API Key nào trong GROQ_API_KEY!")
    sys.exit(1)

vi_tri_groq_key = 0 # Biến toàn cục theo dõi Key hiện tại

# Băng đạn 4 Model cực phẩm của Groq (Xếp từ thông minh nhất đến nhanh nhất)
DANH_SACH_MODELS_AI = [
    "openai/gpt-oss-120b",     # Quái vật 120 tỷ tham số, thông minh số 1
    "llama-3.3-70b-versatile", # Quái vật 70 tỷ của Meta, văn phong mượt mà
    "openai/gpt-oss-20b",      # Đệ cứng 20 tỷ tham số, cân bằng giữa tốc độ & trí tuệ
    "llama-3.1-8b-instant"     # Máy bay phản lực 8 tỷ tham số, cứu cánh cuối cùng
]

supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
cloudinary.config(cloudinary_url=os.environ.get("CLOUDINARY_URL"))

def extract_number(text):
    if not text: return 0
    match = re.search(r'\d+([.,]\d+)?', str(text))
    if match:
        num_str = match.group().replace(',', '.')
        return int(float(num_str)) 
    return 0

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
def ai_analyze_bds(tieu_de, ngu_canh_tho):
    global vi_tri_groq_key
    print(f"🤖 Đang chuẩn bị gửi dữ liệu (Độ dài: {len(ngu_canh_tho)} ký tự) cho AI...")
    
    prompt = (
        f"Bạn là một Siêu Cò BĐS và Chuyên gia Copywriter tại Lào Cai. Hãy đọc kỹ thông tin bài rao bán dưới đây.\n"
        f"Lệnh TUYỆT ĐỐI:\n"
        f"- KHÔNG ĐƯỢC TÓM TẮT QUÁ NGẮN. KHÔNG ĐƯỢC BỎ SÓT BẤT KỲ CON SỐ NÀO (Giá, Diện tích, Số phòng, Mặt tiền, Tiện ích xung quanh).\n"
        f"- KHÔNG ĐƯỢC BỊA ĐẶT THÔNG TIN TRÁI VỚI BẢN GỐC.\n\n"
        f"Hãy trả về JSON chính xác với cấu trúc sau:\n"
        f"{{\n"
        f"  \"loai_bds\": \"Chỉ chọn 1: villa, hotel, land, nhà phố\",\n"
        f"  \"vi_tri\": \"Trích xuất khu vực (vd: Thạch Sơn, Sa Pa)\",\n"
        f"  \"tieu_de_moi\": \"Viết 1 tiêu đề giật tít, đầy đủ thông tin, DÀI TỪ 60 - 100 KÝ TỰ. KHÔNG ĐƯỢC VIẾT CỤT NGỦN.\",\n"
        f"  \"meta_desc\": \"Mô tả SEO hấp dẫn khoảng 150 ký tự, tóm tắt điểm ăn tiền nhất.\",\n"
        f"  \"nhan_fomo\": \"Nhãn tối đa 5 từ (vd: Dòng Tiền Khủng, Lô Góc Siêu Hiếm, Kinh Doanh Sầm Uất...).\",\n"
        f"  \"html_clean\": \"Viết bài PR cực kỳ CHI TIẾT, DÀI DẶN, văn phong đẳng cấp, lôi cuốn người mua. BẮT BUỘC giữ lại toàn bộ giá trị, thông số, ưu điểm từ bản gốc. Trình bày đẹp mắt bằng HTML. BẮT BUỘC dùng các thẻ <h3> để chia đoạn rõ ràng. Dùng thẻ <ul>, <li> để liệt kê các tiện ích, điểm nổi bật. XÓA SẠCH SĐT và tên môi giới cũ.\"\n"
        f"}}\n\n"
        f"--- Tiêu đề gốc: {tieu_de}\n"
        f"--- Mô tả gốc: {ngu_canh_tho}"
    )
    
    for model_name in DANH_SACH_MODELS_AI:
        so_key_da_thu = 0
        while so_key_da_thu < len(DANH_SACH_GROQ_KEYS):
            key = DANH_SACH_GROQ_KEYS[vi_tri_groq_key]
            print(f"  👉 Đang nhờ AI [{model_name}] (dùng Key số {vi_tri_groq_key + 1}) vắt óc viết bài...")
            
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": { "type": "json_object" },
                "temperature": 0.3 
            }
            
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=35)
                
                if res.status_code == 200:
                    res_json = res.json()
                    ai_res = json.loads(res_json['choices'][0]['message']['content'])
                    print(f"  ✅ AI [{model_name}] đã sáng tác xong siêu phẩm!")
                    return ai_res
                else:
                    res_json = res.json()
                    error_msg = res_json.get('error', {}).get('message', str(res.status_code))
                    print(f"  ⚠️ Lỗi Key {vi_tri_groq_key + 1}: {error_msg}")
                    vi_tri_groq_key = (vi_tri_groq_key + 1) % len(DANH_SACH_GROQ_KEYS)
                    so_key_da_thu += 1
                    time.sleep(1)
                    
            except Exception as e:
                print(f"  ⚠️ Lỗi mạng với Key {vi_tri_groq_key + 1}: {str(e)}")
                vi_tri_groq_key = (vi_tri_groq_key + 1) % len(DANH_SACH_GROQ_KEYS)
                so_key_da_thu += 1
                time.sleep(1)

    print("⏳ Oảng rồi! Toàn bộ 4 Model và tất cả các Key đều sập. Trả về rỗng để Bot bỏ qua bài này...")
    return None

# ================= 3. XỬ LÝ HÌNH ẢNH =================
def process_image(url_goc, slug):
    try:
        if not url_goc: 
            return ""
        res = curl_requests.get(url_goc, impersonate="chrome", timeout=20)
        img_data = io.BytesIO(res.content)
        
        with Image.open(img_data) as img:
            rgb_img = img.convert("RGB")
            buffer = io.BytesIO()
            rgb_img.save(buffer, format="WEBP", quality=75)
            buffer.seek(0)
            up = cloudinary.uploader.upload(buffer, folder="sapa_bds", public_id=slug, upload_preset="laocaiview_upload")
            print(f"    + Đã tải ảnh lên mây: {up['secure_url'][:40]}...")
            return up['secure_url']
    except Exception as e:
        print(f"    ⚠️ Lỗi xử lý ảnh: {str(e)}")
        return ""

# ================= 4. QUY TRÌNH QUÉT CHÍNH (ĐA TRANG) =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-tinh-lao-cai"
    print("🚀 BẮT ĐẦU CHẾ ĐỘ CÀO TOÀN BỘ BĐS LÀO CAI (THÁO GIỚI HẠN THỜI GIAN, CÓ CẢM BIẾN TỰ NGẮT)")
    
    da_xu_ly = 0
    trang_bat_dau = 1
    trang_ket_thuc = 100 # Tăng giới hạn lên 100 trang để tự do càn quét

    # CẢM BIẾN CHỐNG NGÁO TRANG ẢO
    so_tin_trung_lien_tiep = 0
    NGUONG_DUNG_BOT = 15 
    
    for page in range(trang_bat_dau, trang_ket_thuc + 1):
        url_hien_tai = base_url if page == 1 else f"{base_url}/p{page}"
        print(f"\n=======================================================")
        print(f"🌍 ĐANG QUÉT TRANG {page}: {url_hien_tai}")
        print(f"=======================================================")

        try:
            res = curl_requests.get(url_hien_tai, impersonate="chrome", timeout=30)
            if res.status_code != 200: continue

            soup = BeautifulSoup(res.content, 'html.parser')
            cards = soup.select('div.re__card-full-compact, div.js__card')
            
            if not cards: 
                print("🛑 HẾT DỮ LIỆU! Đã quét sạch đến trang cuối cùng của web.")
                break

            print(f"📋 Tìm thấy {len(cards)} tin trên trang {page}.")

            for card in cards:
                link_tag = card.select_one('a.js__product-link-for-product-id')
                if not link_tag: continue
                detail_url = "https://batdongsan.com.vn" + link_tag['href']
                tieu_de_goc = card.select_one('h3').get_text(strip=True) if card.select_one('h3') else "Không tiêu đề"

                print(f"\n--- 🔎 ĐANG SOI TIN: {tieu_de_goc[:40]}... ---")

                try:
                    check_dup = supabase.table("bds_ban").select("id").cs("vi_tri_hien_thi", [detail_url]).execute()
                    if len(check_dup.data) > 0:
                        print("⏭️ TIN ĐÃ TỒN TẠI TRONG KÉT. BỎ QUA TÌM TIN MỚI!")
                        so_tin_trung_lien_tiep += 1
                        
                        if so_tin_trung_lien_tiep >= NGUONG_DUNG_BOT:
                            print(f"\n🚨 CẢM BIẾN KÍCH HOẠT: Đã gặp {so_tin_trung_lien_tiep} tin cũ liên tiếp.")
                            print("🚨 KẾT LUẬN: Đã cào hết tin mới hoặc web đang xoay vòng trang ảo.")
                            print("🏁 BOT CHÍNH THỨC RÚT QUÂN ĐI NGỦ! 🏁")
                            return 
                        continue
                except Exception:
                    pass

                # Reset cảm biến nếu gặp tin mới
                so_tin_trung_lien_tiep = 0

                try:
                    res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
                    soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
                    
                    desc_body = soup_dt.select_one('.re__section-body.re__detail-content.js__section-body, .re__detail-content, .js__section-body')
                    raw_desc = desc_body.get_text(separator="\n", strip=True) if desc_body else ""
                    
                    dic_thong_so = {}
                    bang_thong_so = soup_dt.select('.re__pr-specs-content-item')
                    for item in bang_thong_so:
                        tieu_de_ts = item.select_one('.re__pr-specs-content-item-title')
                        gia_tri_ts = item.select_one('.re__pr-specs-content-item-value')
                        if tieu_de_ts and gia_tri_ts:
                            dic_thong_so[tieu_de_ts.get_text(strip=True)] = gia_tri_ts.get_text(strip=True)

                    raw_img_urls = []
                    raw_html_text = res_dt.text 
                    cdn_links = re.findall(r'https?://file\d*\.batdongsan\.com\.vn/[^"\',;\s\\]+', raw_html_text)
                    
                    for link in cdn_links:
                        if link.lower().endswith(('.jpg', '.jpeg', '.png')):
                            high_res = re.sub(r'/(crop|resize)/\d+x\d+', '', link)
                            if high_res not in raw_img_urls:
                                raw_img_urls.append(high_res)
                    
                    if not raw_img_urls:
                        meta_img = soup_dt.find("meta", property="og:image")
                        if meta_img and meta_img.get("content"):
                            raw_img_urls.append(meta_img.get("content"))
                    
                    raw_img_urls = raw_img_urls[:10] 

                    full_context_cho_ai = f"NỘI DUNG MÔ TẢ:\n{raw_desc}\n\nTHÔNG SỐ KỸ THUẬT (PHẢI GIỮ NGUYÊN):\n" + "\n".join([f"- {k}: {v}" for k, v in dic_thong_so.items()])
                    
                    ai_data = ai_analyze_bds(tieu_de_goc, full_context_cho_ai)
                    
                    if ai_data:
                        tieu_de_moi = ai_data.get("tieu_de_moi", tieu_de_goc)
                        slug = tao_slug(tieu_de_moi)[:50] + "-" + str(int(time.time()))
                        
                        print("⏳ Đang nén và đưa ảnh lên Cloudinary...")
                        final_images = []
                        for idx, url in enumerate(raw_img_urls):
                            img_slug = f"{slug}-img{idx}"
                            up_url = process_image(url, img_slug)
                            if up_url:
                                final_images.append(up_url)

                        price_tag = card.select_one('span.re__card-config-price')
                        area_tag = card.select_one('span.re__card-config-area')

                        data_to_save = {
                            "tieu_de": tieu_de_moi, 
                            "slug": slug,
                            "gia": price_tag.get_text(strip=True) if price_tag else "Thỏa thuận",
                            "dien_tich": extract_number(area_tag.get_text()) if area_tag else 0,
                            "loai_bds": ai_data.get("loai_bds", "land"),
                            "vi_tri": ai_data.get("vi_tri", "Sa Pa, Lào Cai"), 
                            "phong_ngu": extract_number(dic_thong_so.get("Số phòng ngủ")) if dic_thong_so.get("Số phòng ngủ") else None,
                            "phong_tam": extract_number(dic_thong_so.get("Số phòng tắm, vệ sinh")) if dic_thong_so.get("Số phòng tắm, vệ sinh") else None,
                            "he_so_tang": str(extract_number(dic_thong_so.get("Số tầng"))) if dic_thong_so.get("Số tầng") else None,
                            "huong_nha": dic_thong_so.get("Hướng nhà", None),
                            "phap_ly": dic_thong_so.get("Pháp lý", None),
                            "hinh_anh": final_images,
                            "mo_ta": ai_data.get("html_clean"), 
                            "meta_title": tieu_de_moi, 
                            "meta_desc": ai_data.get("meta_desc", ""), 
                            "nhan_fomo": ai_data.get("nhan_fomo", ""), 
                            "vi_tri_hien_thi": [detail_url],
                            "trang_thai": "Bản nháp"
                        }

                        supabase.table("bds_ban").insert(data_to_save).execute()
                        da_xu_ly += 1
                        print(f"✅ Đã lưu tin thứ {da_xu_ly} (Tiêu đề: {tieu_de_moi[:50]}...)")
                    
                    time.sleep(5)

                except Exception as e:
                    print(f"❌ Lỗi xử lý tin {tieu_de_goc[:20]}...: {str(e)}")

            print(f"Đã xong trang {page}. Đang nghỉ 20s...")
            time.sleep(20)

        except Exception as e:
            print(f"❌ Lỗi khi quét trang {page}: {e}")

    print(f"\n🎉 KẾT THÚC CÀO BĐS. Tổng số tin đã lưu: {da_xu_ly}")

if __name__ == "__main__":
    run_bot()
