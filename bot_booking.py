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

# Tách chuỗi thành danh sách các Key (bỏ khoảng trắng thừa nếu có)
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

# ================= CƠ CHẾ THAY ĐẠN TỰ ĐỘNG =================
def request_thong_minh(url, params):
    global vi_tri_key_hien_tai
    
    while True:
        headers = {
            "x-rapidapi-key": DANH_SACH_KEYS[vi_tri_key_hien_tai],
            "x-rapidapi-host": "booking-com.p.rapidapi.com"
        }
        
        try:
            res = requests.get(url, headers=headers, params=params)
            
            # 429 là mã lỗi "Too Many Requests" (Hết hạn ngạch)
            if res.status_code == 429 or (res.status_code == 403 and "exceeded" in res.text.lower()):
                print(f"⚠️ API Key số {vi_tri_key_hien_tai + 1} đã CẠN KIỆT!")
                vi_tri_key_hien_tai += 1
                
                if vi_tri_key_hien_tai >= len(DANH_SACH_KEYS):
                    print("❌ TOÀN BỘ API KEYS ĐÃ HẾT ĐẠN. Dừng chiến dịch!")
                    return None
                
                print(f"🔄 TỰ ĐỘNG THAY ĐẠN: Chuyển sang API Key số {vi_tri_key_hien_tai + 1}...")
                continue # Vòng lại gọi API với Key mới
            
            return res.json()
            
        except Exception as e:
            print("❌ Lỗi mạng hoặc kết nối:", e)
            return None

# ================= 2. QUY TRÌNH MÁY XÚC CÀO SẠCH SA PA =================
def cao_truc_tiep_booking(dia_diem, max_hotels=9999):
    print(f"\n🚀 KHỞI ĐỘNG MÁY XÚC VÀO THỊ TRƯỜNG: {dia_diem.upper()}")
    print(f"🔫 Đã nạp {len(DANH_SACH_KEYS)} băng đạn API!")
    print("="*60)

    # 1. Lấy mã định danh khu vực
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

    if not dest_id:
        print(f"❌ Không tìm thấy mã khu vực cho {dia_diem}")
        return

    ngay_in = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    ngay_out = (datetime.datetime.now() + datetime.timedelta(days=8)).strftime("%Y-%m-%d")

    tong_da_lay = 0
    page_number = 0

    # 2. Vòng lặp Lật trang (Pagination)
    while tong_da_lay < max_hotels:
        print(f"\n📄 Đang quét trang số {page_number + 1} của {dia_diem}...")
        
        url_search = "https://booking-com.p.rapidapi.com/v1/hotels/search"
        querystring = {
            "dest_id": dest_id, "search_type": dest_type,
            "checkin_date": ngay_in, "checkout_date": ngay_out,
            "adults_number": "2", "room_number": "1",
            "locale": "vi", "units": "metric",
            "order_by": "popularity", 
            "filter_by_currency": "VND", "page_number": str(page_number) 
        }

        res_search = request_thong_minh(url_search, params=querystring)
        if not res_search: break # Nếu hết sạch API Key thì thoát
        
        hotels = res_search.get('result', [])

        # Nếu trang này không còn khách sạn nào -> Thoát vòng lặp
        if not hotels:
            print(f"🏁 Đã vét cạn kiệt cơ sở lưu trú tại {dia_diem}!")
            break

        # 3. Cào chi tiết từng Khách sạn trong trang
        for hotel in hotels:
            if tong_da_lay >= max_hotels: break

            hotel_id = hotel.get('hotel_id')
            ten_phong = hotel.get('hotel_name', 'Chưa rõ tên')
            vi_tri = hotel.get('address', dia_diem) + ", " + hotel.get('city_trans', dia_diem)
            gia_tien = hotel.get('min_total_price', 0)
            gia_text = f"{int(gia_tien):,} đ/đêm" if gia_tien > 0 else "Liên hệ"
            loai_bds = hotel.get('accommodation_type_name', 'Khách sạn')
            link_goc = hotel.get('url', '')

            print(f"\n🏠 Đang xử lý ({tong_da_lay + 1}): {ten_phong}")

            # Chống trùng lặp
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
                    print("   ☁️ Đang bơm ảnh lên Cloudinary...")
                    for photo in res_photos[:7]: 
                        url_anh = photo.get('url_max') or photo.get('url_square60', '')
                        if url_anh: hinh_anh_moi.append(upload_len_cloud(url_anh.replace('square60', 'max1280x900')))

                # ---> MOI MÔ TẢ
                url_desc = "https://booking-com.p.rapidapi.com/v1/hotels/description"
                res_desc = request_thong_minh(url_desc, params={"hotel_id": hotel_id, "locale": "vi"})
                mo_ta = res_desc.get('description', f'Kỳ nghỉ dưỡng tuyệt vời tại {ten_phong}.') if res_desc else ""

                # ---> MOI LOẠI PHÒNG
                url_rooms = "https://booking-com.p.rapidapi.com/v1/hotels/room-list"
                params_room = {"hotel_id": hotel_id, "checkin_date": ngay_in, "checkout_date": ngay_out, "currency": "VND", "locale": "vi", "adults_number_array": "2"}
                res_rooms = request_thong_minh(url_rooms, params=params_room)

                tap_hop_ten_phong, tap_hop_giuong = set(), set()
                max_nguoi = 2
                if isinstance(res_rooms, list):
                    for room in res_rooms:
                        if room.get('room_name'): tap_hop_ten_phong.add(room.get('room_name'))
                        if room.get('max_persons', 0) > max_nguoi: max_nguoi = room.get('max_persons')
                        if room.get('bed_configurations'):
                            for bed in room['bed_configurations'][0].get('bed_types', []):
                                tap_hop_giuong.add(bed.get('name_with_count', 'Giường đôi'))

                chuoi_loai_phong = ", ".join(list(tap_hop_ten_phong))[:200] if tap_hop_ten_phong else "Đa dạng các hạng phòng"
                chuoi_suc_chua = f"Từ 1 đến {max_nguoi} người/phòng"
                chuoi_loai_giuong = ", ".join(list(tap_hop_giuong))[:150] if tap_hop_giuong else "Giường đơn, Giường đôi tiêu chuẩn"

                # ---> ĐÓNG GÓI INSERT
                slug = tao_slug(ten_phong)[:50] + "-" + str(int(time.time()))
                data_insert = {
                    "tieu_de": ten_phong, "slug": slug, "vi_tri": vi_tri, "loai_bds": loai_bds,
                    "gia": gia_text, "hinh_anh": hinh_anh_moi if hinh_anh_moi else ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267"],
                    "mo_ta": mo_ta, "nhan_fomo": random.choice(DANH_SACH_FOMO),
                    "meta_title": f"Đặt phòng {ten_phong} - Giá Rẻ Nhất",
                    "meta_desc": (f"Trải nghiệm {ten_phong} tại {vi_tri}. " + mo_ta)[:155] + "...",
                    "loai_phong": chuoi_loai_phong, "suc_chua": chuoi_suc_chua, "loai_giuong": chuoi_loai_giuong,
                    "map_url": link_goc, "trang_thai": "Còn phòng", "dien_tich": random.choice([20, 25, 30, 40])
                }

                supabase.table("phong_nghi").insert(data_insert).execute()
                tong_da_lay += 1
                print(f"   ✅ Két sắt đã ghi nhận! (Tiến độ: {tong_da_lay})")

            except Exception as e:
                print("❌ Lỗi khi bóc tách chi tiết:", e)

            # Check xem đã hết sạch API Key chưa để thoát vòng lặp nhỏ
            if vi_tri_key_hien_tai >= len(DANH_SACH_KEYS): break
            time.sleep(1.5)

        # Check xem đã hết sạch API Key chưa để thoát vòng lặp lật trang
        if vi_tri_key_hien_tai >= len(DANH_SACH_KEYS): break
        page_number += 1
        time.sleep(2)

if __name__ == "__main__":
    # Chiến full Sa Pa trước, giới hạn số lượng đặt cực lớn để vét cạn!
    cao_truc_tiep_booking("Sa Pa", max_hotels=9999)
