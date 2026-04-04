import os, requests, time, random, datetime, re
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

# 🔥 ĐÃ CẬP NHẬT 3 MODEL XỊN NHẤT TỪ BẢNG CỦA SẾP
DANH_SACH_MODELS_AI = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]

vi_tri_rapid_key = 0
vi_tri_groq_key = 0
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

DANH_SACH_FOMO = [
    "🔥 Đang bán chạy ở Sa Pa", "⚡ Chỉ còn 2 phòng ở giá này",
    "👀 15 người đang xem phòng này", "⏱️ Khách vừa chốt đơn cách đây 10 phút"
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

# ================= CƠ CHẾ AI GROQ TỰ ĐỘNG CHUYỂN ĐẠN & MODEL =================
def phan_tich_loai_phong_bang_ai(ten_phong, vi_tri, mo_ta, link_goc):
    global vi_tri_groq_key
    
    html_text = ""
    try:
        req_html = requests.get(link_goc, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if req_html.status_code == 200:
            clean = re.sub(r'<[^>]+>', ' ', req_html.text)
            html_text = re.sub(r'\s+', ' ', clean)[:3000] 
    except: pass

    prompt = f"""Bạn là trợ lý AI phân tích dữ liệu khách sạn. Hãy tìm các HẠNG PHÒNG (Room types) của "{ten_phong}" tại "{vi_tri}".
    Mô tả: {mo_ta[:1000]}
    Nội dung web: {html_text}
    Dựa vào thông tin trên, trả về danh sách các hạng phòng. 
    QUY TẮC BẮT BUỘC: CHỈ trả về đúng 1 chuỗi các tên hạng phòng, cách nhau bằng dấu phẩy. KHÔNG gạch đầu dòng, KHÔNG giải thích thêm. (VD: Phòng Deluxe, Suite Executive, Phòng Tiêu Chuẩn)
    """

    for model in DANH_SACH_MODELS_AI:
        so_key_da_thu = 0
        while so_key_da_thu < len(DANH_SACH_GROQ_KEYS):
            key = DANH_SACH_GROQ_KEYS[vi_tri_groq_key]
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1, 
                "max_tokens": 150
            }

            try:
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                
                if res.status_code == 200:
                    data = res.json()
                    text_tra_ve = data['choices'][0]['message']['content'].strip()
                    return text_tra_ve.replace('*', '').replace('\n', '').replace('"', '').strip()
                
                elif res.status_code in [429, 401, 403]: 
                    print(f"   ⚠️ Groq Key {vi_tri_groq_key+1} kiệt sức/lỗi, chuyển key...")
                    vi_tri_groq_key = (vi_tri_groq_key + 1) % len(DANH_SACH_GROQ_KEYS)
                    so_key_da_thu += 1
                else:
                    break 
            except Exception as e:
                vi_tri_groq_key = (vi_tri_groq_key + 1) % len(DANH_SACH_GROQ_KEYS)
                so_key_da_thu += 1
                
    return "Đa dạng các hạng phòng cao cấp và tiêu chuẩn" 

# ================= 3. MÁY XÚC SIÊU TỐC =================
def cao_truc_tiep_booking(dia_diem, max_hotels=9999):
    print(f"\n🚀 KHỞI ĐỘNG MÁY XÚC: {dia_diem.upper()} (GROQ AI ĐỌC TÊN PHÒNG)")
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
            
            lat, lng = hotel.get('latitude'), hotel.get('longitude')
            link_map = f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else hotel.get('url', '')
            link_goc = hotel.get('url', '')

            print(f"\n🏠 Đang xử lý: {ten_phong}")

            try:
                check = supabase.table("phong_nghi").select("id").eq("tieu_de", ten_phong).execute()
                if len(check.data) > 0:
                    print("   ⚠️ Đã có trong Két sắt. Bỏ qua.")
                    continue
            except: pass

            try:
                # 1. MOI ẢNH BẢO VỆ UY TÍN (Giới hạn 15 ảnh xịn nhất)
                url_photos = "https://booking-com.p.rapidapi.com/v1/hotels/photos"
                res_photos = request_thong_minh(url_photos, params={"hotel_id": hotel_id, "locale": "vi"})
                hinh_anh_moi = []
                if isinstance(res_photos, list):
                    print("   ☁️ Đang bơm ảnh lên Cloudinary...")
                    for photo in res_photos[:15]: 
                        url_anh = photo.get('url_max') or photo.get('url_square60', '')
                        if url_anh: hinh_anh_moi.append(upload_len_cloud(url_anh.replace('square60', 'max1280x900')))

                # 2. MOI MÔ TẢ & TIỆN ÍCH
                url_desc = "https://booking-com.p.rapidapi.com/v1/hotels/description"
                res_desc = request_thong_minh(url_desc, params={"hotel_id": hotel_id, "locale": "vi"})
                mo_ta = res_desc.get('description', f'Kỳ nghỉ tuyệt vời tại {ten_phong}.') if isinstance(res_desc, dict) else ""

                url_facilities = "https://booking-com.p.rapidapi.com/v1/hotels/facilities"
                res_fac = request_thong_minh(url_facilities, params={"hotel_id": hotel_id, "locale": "vi"})
                tap_hop_tien_ich = set()
                if isinstance(res_fac, list):
                    for f in res_fac:
                        name = f.get('facility_name') or f.get('name')
                        if name: tap_hop_tien_ich.add(name)
                chuoi_tien_ich = ", ".join(list(tap_hop_tien_ich)) if tap_hop_tien_ich else "Wifi miễn phí, Lễ tân 24h"

                # 3. 🤖 GỌI AI GROQ
                print("   🤖 Đang thả Groq AI đi lùng sục tên phòng...")
                chuoi_loai_phong = phan_tich_loai_phong_bang_ai(ten_phong, vi_tri, mo_ta, link_goc)
                print(f"   🎯 Groq chốt đơn: {chuoi_loai_phong[:70]}...")

                chuoi_suc_chua = "Tùy hạng phòng (Vui lòng liên hệ)"
                chuoi_loai_giuong = "Giường đơn/đôi cỡ lớn (Tùy chọn)"

                # 4. ĐÓNG GÓI INSERT
                slug = tao_slug(ten_phong)[:50] + "-" + str(int(time.time()))
                data_insert = {
                    "tieu_de": ten_phong, "slug": slug, "vi_tri": vi_tri, "loai_bds": loai_bds,
                    "gia": gia_text, "hinh_anh": hinh_anh_moi if hinh_anh_moi else [],
                    "mo_ta": mo_ta, "nhan_fomo": random.choice(DANH_SACH_FOMO),
                    "meta_title": f"Đặt phòng {ten_phong} - Giá Tốt Nhất",
                    "meta_desc": (f"Trải nghiệm {ten_phong} tại {vi_tri}. " + mo_ta)[:155] + "...",
                    "loai_phong": chuoi_loai_phong, "suc_chua": chuoi_suc_chua, "loai_giuong": chuoi_loai_giuong,
                    "tien_ich": chuoi_tien_ich,  
                    "map_url": link_map,         
                    "trang_thai": "Còn phòng", "dien_tich": random.choice([20, 25, 30, 40, 50])
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
