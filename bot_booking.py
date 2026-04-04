import os, requests, time, random, datetime, re
import cloudinary
import cloudinary.uploader
from supabase import create_client

# ================= 1. CẤU HÌNH HỆ THỐNG & DÀN API KEYS =================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
RAPIDAPI_KEYS_STR = os.environ.get("RAPIDAPI_KEY", "")

if not RAPIDAPI_KEYS_STR:
    print("❌ LỖI: Chưa có RAPIDAPI_KEY. Sếp nhớ nạp đạn vào Github Secrets nhé!")
    exit()

DANH_SACH_KEYS = [k.strip() for k in RAPIDAPI_KEYS_STR.split(",") if k.strip()]
vi_tri_key_hien_tai = 0
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

DANH_SACH_FOMO = [
    "🔥 Đang bán chạy ở Sa Pa", "⚡ Chỉ còn 2 phòng ở giá này",
    "👀 15 người đang xem phòng này", "⏱️ Khách vừa chốt đơn cách đây 10 phút",
    "💎 Lựa chọn hàng đầu của khách du lịch"
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

# ================= CƠ CHẾ THAY ĐẠN =================
def request_thong_minh(url, params):
    global vi_tri_key_hien_tai
    while True:
        headers = {
            "x-rapidapi-key": DANH_SACH_KEYS[vi_tri_key_hien_tai],
            "x-rapidapi-host": "booking-com.p.rapidapi.com"
        }
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 429 or (res.status_code == 403 and "exceeded" in res.text.lower()):
                print(f"⚠️ API Key số {vi_tri_key_hien_tai + 1} đã CẠN KIỆT!")
                vi_tri_key_hien_tai += 1
                if vi_tri_key_hien_tai >= len(DANH_SACH_KEYS): return None
                continue 
            
            if res.status_code == 403 and "subscribe" in res.text.lower():
                vi_tri_key_hien_tai += 1
                if vi_tri_key_hien_tai >= len(DANH_SACH_KEYS): return None
                continue

            if res.status_code != 200: return None
            return res.json()
        except:
            return None

# ================= 2. MÁY XÚC VÉT CẠN =================
def cao_truc_tiep_booking(dia_diem, max_hotels=9999):
    print(f"\n🚀 KHỞI ĐỘNG MÁY XÚC: {dia_diem.upper()} (ĐÃ TỐI ƯU CÀO GIƯỜNG)")
    print("="*60)

    url_loc = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
    res_loc = request_thong_minh(url_loc, params={"name": dia_diem, "locale": "vi"})
    if not res_loc: return
    
    dest_id, dest_type = None, None
    if isinstance(res_loc, list):
        for item in res_loc:
            if item.get('dest_type') in ['city', 'region']:
                dest_id = item.get('dest_id')
                dest_type = item.get('dest_type')
                break
    if not dest_id: return

    # 🔥 CHIẾN THUẬT MỚI: Đẩy ngày Check-in ra xa 30 ngày để đảm bảo 100% Khách sạn còn phòng trống
    ngay_in = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    ngay_out = (datetime.datetime.now() + datetime.timedelta(days=31)).strftime("%Y-%m-%d")

    tong_da_lay = 0
    page_number = 0

    while tong_da_lay < max_hotels:
        print(f"\n📄 Đang quét trang số {page_number + 1}...")
        
        url_search = "https://booking-com.p.rapidapi.com/v1/hotels/search"
        querystring = {
            "dest_id": dest_id, "dest_type": dest_type,
            "checkin_date": ngay_in, "checkout_date": ngay_out,
            "adults_number": "2", "room_number": "1",
            "locale": "vi", "units": "metric",
            "order_by": "popularity", "filter_by_currency": "VND", "page_number": str(page_number) 
        }

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
            gia_text = f"{int(gia_tien):,} đ/đêm" if gia_tien > 0 else "Liên hệ"
            loai_bds = hotel.get('accommodation_type_name', 'Khách sạn')
            
            lat = hotel.get('latitude')
            lng = hotel.get('longitude')
            link_map = f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else hotel.get('url', '')

            print(f"\n🏠 Đang xử lý: {ten_phong}")

            try:
                check = supabase.table("phong_nghi").select("id").eq("tieu_de", ten_phong).execute()
                if len(check.data) > 0:
                    print("⚠️ Đã có trong Két sắt. Bỏ qua.")
                    continue
            except: pass

            try:
                # ---> MOI ẢNH
                url_photos = "https://booking-com.p.rapidapi.com/v1/hotels/photos"
                res_photos = request_thong_minh(url_photos, params={"hotel_id": hotel_id, "locale": "vi"})
                hinh_anh_moi = []
                if isinstance(res_photos, list):
                    for photo in res_photos: 
                        url_anh = photo.get('url_max') or photo.get('url_square60', '')
                        if url_anh: hinh_anh_moi.append(upload_len_cloud(url_anh.replace('square60', 'max1280x900')))

                # ---> MOI MÔ TẢ
                url_desc = "https://booking-com.p.rapidapi.com/v1/hotels/description"
                res_desc = request_thong_minh(url_desc, params={"hotel_id": hotel_id, "locale": "vi"})
                mo_ta = res_desc.get('description', f'Kỳ nghỉ tuyệt vời tại {ten_phong}.') if isinstance(res_desc, dict) else ""

                # ---> MOI TIỆN ÍCH
                url_facilities = "https://booking-com.p.rapidapi.com/v1/hotels/facilities"
                res_fac = request_thong_minh(url_facilities, params={"hotel_id": hotel_id, "locale": "vi"})
                tap_hop_tien_ich = set()
                if isinstance(res_fac, list):
                    for f in res_fac:
                        name = f.get('facility_name') or f.get('name')
                        if name: tap_hop_tien_ich.add(name)
                chuoi_tien_ich = ", ".join(list(tap_hop_tien_ich)) if tap_hop_tien_ich else "Wifi miễn phí, Chỗ để xe, Lễ tân 24h"

                # ---> 🔥 BÓC TÁCH PHÒNG & GIƯỜNG (SIÊU CẤP)
                url_rooms = "https://booking-com.p.rapidapi.com/v1/hotels/room-list"
                params_room = {
                    "hotel_id": hotel_id, "checkin_date": ngay_in, "checkout_date": ngay_out, 
                    "currency": "VND", "locale": "vi", "units": "metric", "adults_number_by_rooms": "2"
                }
                res_rooms = request_thong_minh(url_rooms, params=params_room)

                tap_hop_ten_phong, tap_hop_giuong = set(), set()
                max_nguoi = 2
                
                if isinstance(res_rooms, list):
                    for room in res_rooms:
                        # 1. Lấy Tên phòng
                        r_name = room.get('room_name')
                        if r_name: tap_hop_ten_phong.add(r_name)
                        
                        # 2. Lấy Sức chứa lớn nhất
                        if room.get('max_persons', 0) > max_nguoi: 
                            max_nguoi = room.get('max_persons')
                        
                        # 3. Lấy cấu hình Giường (Đào sâu vào list)
                        has_bed = False
                        if room.get('bed_configurations'):
                            for bed_config in room['bed_configurations']:
                                for bed in bed_config.get('bed_types', []):
                                    b_name = bed.get('name_with_count') or bed.get('description') or bed.get('name')
                                    if b_name:
                                        tap_hop_giuong.add(b_name)
                                        has_bed = True
                        
                        # Vét cạn: Nếu API giấu giường, tự nội suy từ Tên phòng
                        if not has_bed and r_name:
                            name_lower = r_name.lower()
                            if 'king' in name_lower or 'cực lớn' in name_lower: tap_hop_giuong.add('1 giường đôi cực lớn (King)')
                            elif 'queen' in name_lower: tap_hop_giuong.add('1 giường đôi lớn (Queen)')
                            elif 'đôi' in name_lower or 'double' in name_lower: tap_hop_giuong.add('1 giường đôi')
                            elif 'đơn' in name_lower or 'twin' in name_lower or '2 giường' in name_lower: tap_hop_giuong.add('2 giường đơn')

                # Gộp chuỗi hiển thị
                chuoi_loai_phong = ", ".join(list(tap_hop_ten_phong)) if tap_hop_ten_phong else "Đa dạng các hạng phòng"
                chuoi_suc_chua = f"Từ 1 đến {max_nguoi} người/phòng"
                chuoi_loai_giuong = ", ".join(list(tap_hop_giuong)) if tap_hop_giuong else "1 giường đôi lớn hoặc 2 giường đơn"

                # ---> ĐÓNG GÓI INSERT
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
                print(f"   ✅ Đã bóc tách giường & tiện ích! (Tiến độ: {tong_da_lay})")

            except Exception as e:
                print("❌ Lỗi khi bóc tách chi tiết:", e)

            if vi_tri_key_hien_tai >= len(DANH_SACH_KEYS): break
            time.sleep(1.5)

        if vi_tri_key_hien_tai >= len(DANH_SACH_KEYS): break
        page_number += 1
        time.sleep(2)

if __name__ == "__main__":
    cao_truc_tiep_booking("Sa Pa", max_hotels=9999)
