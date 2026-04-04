import os, requests, time, random
from supabase import create_client

# ================= 1. CẤU HÌNH HỆ THỐNG =================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")

if not RAPIDAPI_KEY:
    print("❌ LỖI: Chưa có RAPIDAPI_KEY")
    exit()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
headers = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "booking-com.p.rapidapi.com"
}

# Danh sách nhãn FOMO mồi nhử khách
DANH_SACH_FOMO = [
    "🔥 Đang bán chạy ở Sa Pa",
    "⚡ Chỉ còn 2 phòng ở giá này",
    "👀 15 người đang xem phòng này",
    "⏱️ Khách vừa đặt cách đây 10 phút",
    "💎 Lựa chọn hàng đầu của khách du lịch"
]

def lam_giau_du_lieu_phong_nghi():
    print("🚀 KHỞI ĐỘNG BOT VÉT MÁNG BOOKING.COM (FULL DATA)")
    print("="*50)

    # Lấy các phòng chưa có hình ảnh xịn (Hoặc giá đang để 'Liên hệ')
    try:
        response = supabase.table("phong_nghi").select("id, tieu_de").limit(10).execute() # Đang test 10 cái
        danh_sach_phong = response.data
    except Exception as e:
        print("❌ Lỗi Supabase:", e)
        return

    for phong in danh_sach_phong:
        id_phong = phong['id']
        ten_phong = phong['tieu_de']
        print(f"\n🔍 Đang xử lý: {ten_phong}")

        try:
            # 1. TÌM HOTEL ID TRÊN BOOKING
            url_search = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
            res_search = requests.get(url_search, headers=headers, params={"name": ten_phong, "locale": "vi"}).json()
            
            hotel_id = None
            if isinstance(res_search, list):
                for item in res_search:
                    if item.get('dest_type') == 'hotel':
                        hotel_id = item.get('dest_id')
                        break
            
            if not hotel_id:
                print("⚠️ Không tìm thấy trên Booking. Bỏ qua.")
                continue

            # 2. LẤY HÌNH ẢNH HD
            url_photos = "https://booking-com.p.rapidapi.com/v1/hotels/photos"
            res_photos = requests.get(url_photos, headers=headers, params={"hotel_id": hotel_id, "locale": "vi"}).json()
            hinh_anh_moi = []
            if isinstance(res_photos, list):
                for photo in res_photos[:6]: # Lấy 6 ảnh đẹp nhất
                    url_anh = photo.get('url_max') or photo.get('url_square60', '')
                    if url_anh: hinh_anh_moi.append(url_anh.replace('square60', 'max1280x900'))

            # 3. LẤY MÔ TẢ CHI TIẾT
            url_desc = "https://booking-com.p.rapidapi.com/v1/hotels/description"
            res_desc = requests.get(url_desc, headers=headers, params={"hotel_id": hotel_id, "locale": "vi"}).json()
            mo_ta = res_desc.get('description', f'Trải nghiệm tuyệt vời tại {ten_phong} với đầy đủ tiện nghi, view check-in cực đẹp dành cho du khách.')

            # 4. TỰ ĐỘNG SINH DỮ LIỆU SEO & FOMO & PHÒNG CHUẨN
            nhan_fomo = random.choice(DANH_SACH_FOMO)
            meta_title = f"Đặt phòng {ten_phong} - Giá tốt nhất, View cực Chill"
            meta_desc = (f"Khám phá {ten_phong} tại Lào Cai. Đặt phòng ngay hôm nay để nhận ưu đãi. " + mo_ta)[:155] + "..." # Chuẩn độ dài Google
            
            # Đóng gói toàn bộ data để nhét vào Két sắt
            data_update = {
                "hinh_anh": hinh_anh_moi if hinh_anh_moi else None,
                "mo_ta": mo_ta,
                "nhan_fomo": nhan_fomo,
                "meta_title": meta_title,
                "meta_desc": meta_desc,
                "gia": "Tử 450.000 đ/đêm",       # Mặc định chờ Sale update
                "dien_tich": random.choice([20, 25, 30, 40]), # Cột int4 (Số nguyên)
                "loai_phong": "Phòng Tiêu Chuẩn (Standard)",
                "suc_chua": "2 người lớn",
                "loai_giuong": "1 giường đôi lớn (King size)"
            }

            # Lọc bỏ các trường None để tránh lỗi
            data_update = {k: v for k, v in data_update.items() if v is not None}

            # 5. CẬP NHẬT VÀO DATABASE
            supabase.table("phong_nghi").update(data_update).eq("id", id_phong).execute()
            print(f"✅ Bơm dữ liệu thành công! (Đã đắp Ảnh, Mô tả, SEO, Fomo, Cấu hình phòng)")

        except Exception as e:
            print("❌ Lỗi xử lý:", e)

        time.sleep(1.5) # Nghỉ ngơi giữ mạng

    print("\n🏁 HOÀN TẤT CHIẾN DỊCH VÉT MÁNG!")

if __name__ == "__main__":
    lam_giau_du_lieu_phong_nghi()
