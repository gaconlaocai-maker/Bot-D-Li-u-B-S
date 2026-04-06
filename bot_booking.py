import os, requests, time, random, datetime, re
import urllib.parse
import cloudinary
import cloudinary.uploader
from supabase import create_client

# ================= 1. CẤU HÌNH HỆ THỐNG & DÀN API KEYS =================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
RAPIDAPI_KEYS_STR = os.environ.get("RAPIDAPI_KEY", "")
GROQ_KEYS_STR = os.environ.get("GROQ_API_KEY", "")

if not RAPIDAPI_KEYS_STR or not GROQ_KEYS_STR:
    print("❌ LỖI: Thiếu RAPIDAPI_KEY hoặc GROQ_API_KEY trong Github Secrets!")
    exit()

DANH_SACH_RAPID_KEYS = [k.strip() for k in RAPIDAPI_KEYS_STR.split(",") if k.strip()]
DANH_SACH_GROQ_KEYS = [k.strip() for k in GROQ_KEYS_STR.split(",") if k.strip()]
DANH_SACH_MODELS_AI = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]

vi_tri_rapid_key = 0
vi_tri_groq_key = 0
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

DANH_SACH_FOMO = [
    "🔥 Đang bán chạy ở Sa Pa", "⚡ Chỉ còn 2 phòng ở giá này",
    "👀 Lựa chọn hàng đầu của khách du lịch", "⏱️ Khách vừa đặt phòng cách đây 15 phút"
]

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

def upload_len_cloud(image_url):
    try:
        result = cloudinary.uploader.upload(image_url, folder="laocaiview_phongnghi")
        return result.get('secure_url')
    except:
        return image_url

# ================= CƠ CHẾ THAY ĐẠN RAPID API =================
def request_thong_minh(url, params):
    global vi_tri_rapid_key
    while True:
        headers = {
            "x-rapidapi-key": DANH_SACH_RAPID_KEYS[vi_tri_rapid_key],
            "x-rapidapi-host": "booking-com.p.rapidapi.com"
        }
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 429 or (res.status_code == 403 and "exceeded" in res.text.lower()):
                vi_tri_rapid_key += 1
                if vi_tri_rapid_key >= len(DANH_SACH_RAPID_KEYS): return None
                continue 
            if res.status_code == 403 and "subscribe" in res.text.lower():
                vi_tri_rapid_key += 1
                if vi_tri_rapid_key >= len(DANH_SACH_RAPID_KEYS): return None
                continue
            if res.status_code != 200: return None
            return res.json()
        except:
            return None

# ================= CƠ CHẾ AI XÀO NẤU CONTENT "CHÍNH CHỦ" =================
def xao_nau_content_bang_ai(ten_phong, vi_tri, mo_ta_goc, chuoi_tien_ich, link_goc):
    global vi_tri_groq_key
    
    # Moi móc mã nguồn Booking
    html_text = ""
    try:
        req_html = requests.get(link_goc, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
        if req_html.status_code == 200:
            clean = re.sub(r'<script.*?</script>', '', req_html.text, flags=re.DOTALL)
            clean = re.sub(r'<style.*?</style>', '', clean, flags=re.DOTALL)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            html_text = re.sub(r'\s+', ' ', clean)[:15000] 
    except: pass

    prompt = f"""Bạn là Giám đốc Kinh doanh của hệ thống đặt phòng LaoCaiView. Hãy viết bài chốt sale cho phòng nghỉ "{ten_phong}" tại "{vi_tri}".
Tiện ích thực tế: {chuoi_tien_ich}
Mô tả thô: {mo_ta_goc[:1000]}
Dữ liệu quét từ web (hãy dò tìm Tên hạng phòng ở đây): {html_text}

NHIỆM VỤ:
1. Viết 1 Tiêu đề SEO (meta_title) (dưới 65 ký tự).
2. Viết 1 Mô tả SEO (meta_desc) (dưới 155 ký tự).
3. Viết Mô tả chi tiết (mo_ta) lôi cuốn, chia đoạn rõ ràng.
   🔥 QUY TẮC SỐNG CÒN: Phải đóng vai chủ sở hữu. Xưng hô là "Chúng tôi", "LaoCaiView hân hạnh mang đến...". TUYỆT ĐỐI KHÔNG DÙNG các từ ngữ người ngoài cuộc như "Khách sạn này cung cấp", "Chỗ nghỉ này có". Phải viết như thể đây là tài sản của chính chúng ta.
4. Trích xuất CHÍNH XÁC các HẠNG PHÒNG từ 'Dữ liệu quét từ web' (Ví dụ: Phòng Deluxe Có Giường Cỡ King, Suite Executive). Cách nhau bằng dấu phẩy. Nếu không tìm thấy chữ nào, hãy đề xuất: Phòng Tiêu Chuẩn, Phòng Deluxe.

BẮT BUỘC trả về đúng định dạng có các tag sau (Không giải thích thêm):
[TITLE]...[/TITLE]
[META]...[/META]
[DESC]...[/DESC]
[ROOMS]...[/ROOMS]"""

    if not DANH_SACH_GROQ_KEYS: return None
    
    so_key_da_thu = 0
    while so_key_da_thu < len(DANH_SACH_GROQ_KEYS):
        key_hien_tai = DANH_SACH_GROQ_KEYS[vi_tri_groq_key]
        
        for model in DANH_SACH_MODELS_AI:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key_hien_tai}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000
            }

            try:
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    text_tra_ve = res.json()['choices'][0]['message']['content'].strip()
                    try:
                        title = re.search(r'\[TITLE\](.*?)\[/TITLE\]', text_tra_ve, re.DOTALL).group(1).strip()
                        meta = re.search(r'\[META\](.*?)\[/META\]', text_tra_ve, re.DOTALL).group(1).strip()
                        desc = re.search(r'\[DESC\](.*?)\[/DESC\]', text_tra_ve, re.DOTALL).group(1).strip()
                        rooms = re.search(r'\[ROOMS\](.*?)\[/ROOMS\]', text_tra_ve, re.DOTALL).group(1).strip()
                        print(f"   🪄 Groq ({model}) xuất thần bằng Key số {vi_tri_groq_key + 1}!")
                        return {"title": title, "meta": meta, "desc": desc, "rooms": rooms}
                    except:
                        continue 
                elif res.status_code in [429, 401, 403]: 
                    continue 
                else:
                    continue 
            except Exception:
                continue
                
        # Nếu kiệt sức cả 3 model, chuyển sang Key khác
        print(f"   ❌ Key số {vi_tri_groq_key + 1} kiệt sức. Lôi Key khác ra xài!")
        vi_tri_groq_key = (vi_tri_groq_key + 1) % len(DANH_SACH_GROQ_KEYS)
        so_key_da_thu += 1
                
    return {
        "title": f"Đặt phòng {ten_phong} - Ưu Đãi Tại LaoCaiView", 
        "meta": (f"LaoCaiView hân hạnh mang đến trải nghiệm tuyệt vời tại {ten_phong} ở {vi_tri}. " + mo_ta_goc)[:150] + "...", 
        "desc": f"Đến với {ten_phong}, chúng tôi mang đến cho bạn không gian nghỉ dưỡng hoàn hảo... " + mo_ta_goc, 
        "rooms": "Phòng Tiêu Chuẩn, Phòng Deluxe, Phòng Gia Đình" 
    }

# ================= 3. MÁY XÚC FULL QUY TRÌNH =================
def cao_truc_tiep_booking(dia_diem, max_hotels=9999):
    print(f"\n🚀 KHỞI ĐỘNG MÁY XÚC: {dia_diem.upper()} (AI NHẬP VAI CHỦ NHÀ & QUÉT SẠCH TÊN PHÒNG)")
    print("="*60)

    url_loc = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
    res_loc = request_thong_minh(url_loc, params={"name": dia_diem, "locale": "vi"})
    if not res_loc: return
    
    dest_id, dest_type = None, None
    if isinstance(res_loc, list):
        for item in res_loc:
            if item.get('dest_type') in ['city', 'region']:
                dest_id, dest_type = item.get('dest_id'), item.get('dest_type')
                break
    if not dest_id: return

    ngay_in = (datetime.datetime.now() + datetime.timedelta(days=15)).strftime("%Y-%m-%d")
    ngay_out = (datetime.datetime.now() + datetime.timedelta(days=16)).strftime("%Y-%m-%d")

    tong_da_lay = 0
    page_number = 0

    while tong_da_lay < max_hotels:
        print(f"\n📄 Đang quét trang số {page_number + 1}...")
        url_search = "https://booking-com.p.rapidapi.com/v1/hotels/search"
        querystring = {"dest_id": dest_id, "dest_type": dest_type, "checkin_date": ngay_in, "checkout_date": ngay_out, "adults_number": "2", "room_number": "1", "locale": "vi", "units": "metric", "order_by": "popularity", "filter_by_currency": "VND", "page_number": str(page_number)}

        res_search = request_thong_minh(url_search, params=querystring)
        if not res_search: break 
        hotels = res_search.get('result', [])
        if not hotels: break

        for hotel in hotels:
            if tong_da_lay >= max_hotels: break

            hotel_id = hotel.get('hotel_id')
            ten_phong = hotel.get('hotel_name', 'Chưa rõ tên')
            vi_tri = hotel.get('address', dia_diem) + ", " + hotel.get('city_trans', dia_diem)
            gia_tien = hotel.get('min_total_price', 0)
            gia_text = f"Chỉ từ {int(gia_tien):,} đ/đêm" if gia_tien > 0 else "Liên hệ để nhận báo giá"
            loai_bds = hotel.get('accommodation_type_name', 'Khách sạn')
            
            # LINK GOOGLE MAPS CHUẨN
            query_map = urllib.parse.quote(f"{ten_phong} {vi_tri} Việt Nam")
            link_map = f"https://www.google.com/maps/search/?api=1&query={query_map}"
            link_goc = hotel.get('url', '')

            print(f"\n🏠 Đang xử lý: {ten_phong}")

            try:
                check = supabase.table("phong_nghi").select("id").eq("tieu_de", ten_phong).execute()
                if len(check.data) > 0:
                    print("   ⚠️ Đã có trong Két sắt. Bỏ qua.")
                    continue
            except: pass

            try:
                # 1. MOI ẢNH
                url_photos = "https://booking-com.p.rapidapi.com/v1/hotels/photos"
                res_photos = request_thong_minh(url_photos, params={"hotel_id": hotel_id, "locale": "vi"})
                hinh_anh_moi = []
                if isinstance(res_photos, list):
                    print("   ☁️ Đang bơm ảnh lên Cloudinary...")
                    for photo in res_photos[:15]: 
                        url_anh = photo.get('url_max') or photo.get('url_square60', '')
                        if url_anh: hinh_anh_moi.append(upload_len_cloud(url_anh.replace('square60', 'max1280x900')))

                # 2. MOI MÔ TẢ GỐC & TIỆN ÍCH
                url_desc = "https://booking-com.p.rapidapi.com/v1/hotels/description"
                res_desc = request_thong_minh(url_desc, params={"hotel_id": hotel_id, "locale": "vi"})
                mo_ta_goc = res_desc.get('description', f'Kỳ nghỉ tuyệt vời tại {ten_phong}.') if isinstance(res_desc, dict) else ""

                url_facilities = "https://booking-com.p.rapidapi.com/v1/hotels/facilities"
                res_fac = request_thong_minh(url_facilities, params={"hotel_id": hotel_id, "locale": "vi"})
                tap_hop_tien_ich = set()
                if isinstance(res_fac, list):
                    for f in res_fac:
                        name = f.get('facility_name') or f.get('name')
                        if name: tap_hop_tien_ich.add(name)
                chuoi_tien_ich = ", ".join(list(tap_hop_tien_ich)) if tap_hop_tien_ich else "Wifi miễn phí, Lễ tân 24h"

                # 3. 🤖 GỌI AI GROQ XÀO NẤU VỚI DỮ LIỆU ĐÃ MỞ RỘNG (15.000 ký tự)
                print("   🤖 AI Groq đang nhập vai chủ nhà & Soi tên hạng phòng...")
                ai_data = xao_nau_content_bang_ai(ten_phong, vi_tri, mo_ta_goc, chuoi_tien_ich, link_goc)
                print(f"   🎯 Hạng phòng gom được: {ai_data['rooms'][:70]}...")

                chuoi_suc_chua = "Tùy hạng phòng (Vui lòng liên hệ)"
                chuoi_loai_giuong = "Giường đơn/đôi cỡ lớn (Tùy chọn)"

                # 4. ĐÓNG GÓI INSERT
                slug = tao_slug(ten_phong)[:50] + "-" + str(int(time.time()))
                data_insert = {
                    "tieu_de": ten_phong, "slug": slug, "vi_tri": vi_tri, "loai_bds": loai_bds,
                    "gia": gia_text, "hinh_anh": hinh_anh_moi if hinh_anh_moi else [],
                    "mo_ta": ai_data['desc'], 
                    "nhan_fomo": random.choice(DANH_SACH_FOMO),
                    "meta_title": ai_data['title'], 
                    "meta_desc": ai_data['meta'],   
                    "loai_phong": ai_data['rooms'], 
                    "suc_chua": chuoi_suc_chua, 
                    "loai_giuong": chuoi_loai_giuong,
                    "tien_ich": chuoi_tien_ich,  
                    "map_url": link_map,         
                    "trang_thai": "Còn phòng", 
                    "dien_tich": random.choice([20, 25, 30, 40, 50])
                }

                supabase.table("phong_nghi").insert(data_insert).execute()
                tong_da_lay += 1
                print(f"   ✅ Đã chốt xong vào Két! (Tiến độ: {tong_da_lay})")

            except Exception as e:
                print("❌ Lỗi khi bóc tách chi tiết:", e)

            if vi_tri_rapid_key >= len(DANH_SACH_RAPID_KEYS): break
            time.sleep(1)

        if vi_tri_rapid_key >= len(DANH_SACH_RAPID_KEYS): break
        page_number += 1
        time.sleep(1.5)

if __name__ == "__main__":
    cao_truc_tiep_booking("Sa Pa", max_hotels=9999)
