import os, sys, re, time, requests, io, json, cloudinary, cloudinary.uploader
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. CẤU HÌNH HỆ THỐNG =================
def check_config():
    required_keys = ["GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "CLOUDINARY_URL"]
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"❌ THIẾU CẤU HÌNH SECRETS: {', '.join(missing)}")
        sys.exit(1)

check_config()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
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

# ================= 2. AI BIÊN TẬP (GIẢM TẢI CHO AI) =================
def ai_analyze_bds(tieu_de, ngu_canh_tho):
    print(f"🤖 Đang gửi mô tả sang AI (Độ dài: {len(ngu_canh_tho)} ký tự)...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    # [ĐÃ TỐI ƯU]: AI giờ chỉ cần lo phân loại và viết lại HTML cho mượt, không cần tìm thông số nữa
    prompt = (
        f"Bạn là chuyên gia BĐS Lào Cai. Hãy đọc bài đăng thô và trả về ĐÚNG định dạng JSON sau:\n"
        f"{{\n"
        f"  \"loai_bds\": \"Phân loại BĐS (vd: villa, hotel, land, nhà phố...)\",\n"
        f"  \"html_clean\": \"Viết lại nội dung mô tả BĐS bằng mã HTML sạch (<p>, <ul>, <li>), TUYỆT ĐỐI XÓA SẠCH SĐT, link và tên môi giới\"\n"
        f"}}\n\n"
        f"Nội dung thô: {ngu_canh_tho}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": { "type": "json_object" },
        "temperature": 0.1
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        ai_res = json.loads(res.json()['choices'][0]['message']['content'])
        print("✅ AI đã xử lý nội dung xong.")
        return ai_res
    except Exception as e:
        print(f"⚠️ Lỗi AI Groq: {str(e)}")
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
            # [ĐÃ FIX]: Ép con bot dùng Upload Preset để đóng dấu logo
            up = cloudinary.uploader.upload(buffer, folder="sapa_bds", public_id=slug, upload_preset="laocaiview_upload")
            print(f"    + Đã tải ảnh lên mây: {up['secure_url'][:40]}...")
            return up['secure_url']
    except Exception as e:
        print(f"    ⚠️ Lỗi xử lý ảnh: {str(e)}")
        return ""

# ================= 4. QUY TRÌNH QUÉT CHÍNH (ĐA TRANG) =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 BẮT ĐẦU CHẾ ĐỘ CÀO DIỆN RỘNG (KẾT HỢP BÓC TÁCH BẢNG)")
    
    da_xu_ly = 0
    trang_bat_dau = 1
    trang_ket_thuc = 5 

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
            
            if not cards: break

            print(f"📋 Tìm thấy {len(cards)} tin trên trang {page}.")

            for card in cards:
                link_tag = card.select_one('a.js__product-link-for-product-id')
                if not link_tag: continue
                detail_url = "https://batdongsan.com.vn" + link_tag['href']
                title = card.select_one('h3').get_text(strip=True) if card.select_one('h3') else "Không tiêu đề"

                print(f"\n--- 🔎 ĐANG SOI TIN: {title[:40]}... ---")

                try:
                    check_dup = supabase.table("bds_ban").select("id").eq("tieu_de", title).execute()
                    if len(check_dup.data) > 0:
                        print("⏭️ TIN ĐÃ TỒN TẠI. BỎ QUA!")
                        continue
                except Exception as e:
                    pass

                try:
                    res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
                    soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
                    
                    desc_body = soup_dt.select_one('.re__section-body.re__detail-content.js__section-body, .re__detail-content, .js__section-body')
                    raw_desc = desc_body.get_text(separator="\n", strip=True) if desc_body else ""
                    
                    # [ĐÃ NÂNG CẤP]: Bóc tách trực tiếp bằng Code từ bảng "Đặc điểm bất động sản"
                    dic_thong_so = {}
                    bang_thong_so = soup_dt.select('.re__pr-specs-content-item')
                    for item in bang_thong_so:
                        tieu_de_ts = item.select_one('.re__pr-specs-content-item-title')
                        gia_tri_ts = item.select_one('.re__pr-specs-content-item-value')
                        if tieu_de_ts and gia_tri_ts:
                            dic_thong_so[tieu_de_ts.get_text(strip=True)] = gia_tri_ts.get_text(strip=True)
                    
                    print(f"📍 Đã bóc trực tiếp từ Bảng: {dic_thong_so}")

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

                    # Gửi AI để làm sạch HTML
                    ai_data = ai_analyze_bds(title, raw_desc)
                    
                    if ai_data:
                        slug = tao_slug(title)[:50] + "-" + str(int(time.time()))
                        
                        print("⏳ Đang nén và đưa ảnh lên Cloudinary...")
                        final_images = []
                        for idx, url in enumerate(raw_img_urls):
                            img_slug = f"{slug}-img{idx}"
                            up_url = process_image(url, img_slug)
                            if up_url:
                                final_images.append(up_url)

                        price_tag = card.select_one('span.re__card-config-price')
                        area_tag = card.select_one('span.re__card-config-area')

                        # Ánh xạ từ Dictionary vừa bóc được vào Supabase
                        data_to_save = {
                            "tieu_de": title,
                            "slug": slug,
                            "gia": price_tag.get_text(strip=True) if price_tag else "Thỏa thuận",
                            "dien_tich": extract_number(area_tag.get_text()) if area_tag else 0,
                            "loai_bds": ai_data.get("loai_bds", "land"),
                            "phong_ngu": extract_number(dic_thong_so.get("Số phòng ngủ")) if dic_thong_so.get("Số phòng ngủ") else None,
                            "phong_tam": extract_number(dic_thong_so.get("Số phòng tắm, vệ sinh")) if dic_thong_so.get("Số phòng tắm, vệ sinh") else None,
                            "he_so_tang": str(extract_number(dic_thong_so.get("Số tầng"))) if dic_thong_so.get("Số tầng") else None,
                            "huong_nha": dic_thong_so.get("Hướng nhà", None),
                            "phap_ly": dic_thong_so.get("Pháp lý", None),
                            "hinh_anh": final_images,
                            "mo_ta": ai_data.get("html_clean"),
                            "vi_tri_hien_thi": [detail_url],
                            "trang_thai": "Bản nháp"
                        }

                        supabase.table("bds_ban").insert(data_to_save).execute()
                        da_xu_ly += 1
                        print(f"✅ Đã lưu thành công tin thứ {da_xu_ly} (Trạng thái: BẢN NHÁP).")
                    
                    time.sleep(10)

                except Exception as e:
                    print(f"❌ Lỗi xử lý tin {title[:20]}...: {str(e)}")

            print(f"Đã xong trang {page}. Đang nghỉ 20s...")
            time.sleep(20)

        except Exception as e:
            print(f"❌ Lỗi khi quét trang {page}: {e}")

    print(f"\n🎉 KẾT THÚC CÀO DIỆN RỘNG. Tổng số tin đã lưu: {da_xu_ly}")

if __name__ == "__main__":
    run_bot()
