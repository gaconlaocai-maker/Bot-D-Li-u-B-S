import os, sys, re, time
from playwright.sync_api import sync_playwright
from supabase import create_client

# ================= 1. CẤU HÌNH HỆ THỐNG =================
# Lấy Keys từ môi trường (Nếu chạy ở máy tính sếp nhớ set biến môi trường, hoặc thay thẳng chuỗi vào đây để test)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://dprvinsavidjupuxccyu.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_9QcVDFuS2iqexselGNqK0w_efx6fKam") # Lấy đúng key sếp đang dùng

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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

# ================= 2. QUY TRÌNH CÀO GOOGLE MAPS =================
def scrape_and_save_homestays(query="Homestay Sapa"):
    print(f"🚀 KHỞI ĐỘNG CỖ MÁY CÀO DATA GOOGLE MAPS")
    print(f"🎯 Mục tiêu: '{query}'\n" + "="*40)
    
    # Lấy danh sách link gốc đã cào để tránh trùng lặp
    danh_sach_link_cu = set()
    try:
        res_db = supabase.table("phong_nghi").select("map_url").execute()
        for row in res_db.data:
            if row.get("map_url"): danh_sach_link_cu.add(row["map_url"])
        print(f"🛡️ Khiên chống trùng lặp đã bật! Ghi nhớ {len(danh_sach_link_cu)} địa điểm cũ.")
    except: pass

    da_xu_ly = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Để True cho nó chạy ngầm, nếu muốn xem nó bấm bấm thì để False
        page = browser.new_page(locale="vi-VN") # Ép tiếng Việt để bắt đúng chữ "Sao chép số điện thoại"
        
        print("🌍 Đang thâm nhập vào bản đồ...")
        page.goto(f"https://www.google.com/maps/search/{query.replace(' ', '+')}")

        try:
            # Đợi load danh sách bên trái
            page.wait_for_selector('a[href*="/maps/place/"]', timeout=15000)
            
            # Cuộn chuột một chút để nó load thêm data (Tùy chọn)
            # ...
            
            places = page.locator('a[href*="/maps/place/"]').all()
            print(f"🎯 Rada quét thấy {len(places)} mục tiêu. Bắt đầu trích xuất:\n")

            # Test trước 10 cái cho nhanh
            for i, place in enumerate(places[:10]): 
                try:
                    # Lấy link Maps của địa điểm
                    map_url = place.get_attribute('href')
                    
                    # Cắt bớt link cho sạch (Bỏ các tham số tọa độ rườm rà phía sau)
                    clean_map_url = map_url.split('?')[0] if map_url else ""
                    
                    if clean_map_url in danh_sach_link_cu:
                        print(f"⏭️ BỎ QUA: Mục tiêu thứ {i+1} đã có trong Database.")
                        continue

                    # Bấm vào địa điểm
                    place.click()
                    page.wait_for_timeout(3000) # Đợi panel chi tiết mở ra hoàn toàn

                    # Gắp Tên Homestay
                    name_locator = page.locator('h1.DUwDvf')
                    name = name_locator.inner_text() if name_locator.count() > 0 else ""
                    
                    if not name: continue

                    # Gắp Số điện thoại
                    phone_locator = page.locator('button[data-tooltip="Sao chép số điện thoại"]')
                    phone = phone_locator.inner_text() if phone_locator.count() > 0 else ""

                    # Gắp Địa chỉ
                    address_locator = page.locator('button[data-tooltip="Sao chép địa chỉ"]')
                    address = address_locator.inner_text() if address_locator.count() > 0 else "Lào Cai"

                    print(f"🏠 Tên phòng: {name}")
                    print(f"📞 Số điện thoại: {phone}")
                    
                    # Đẩy vào Database
                    slug = tao_slug(name)[:50] + "-" + str(int(time.time()))
                    data_to_save = {
                        "tieu_de": name,
                        "slug": slug,
                        "vi_tri": address,
                        "so_dien_thoai": phone,
                        "map_url": clean_map_url,
                        "loai_bds": "Homestay",
                        "trang_thai": "Chờ duyệt",
                        "gia": "Liên hệ", # Mặc định chờ Sale update
                        "hinh_anh": ["https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80"] # Ảnh demo cho web đỡ trống
                    }

                    supabase.table("phong_nghi").insert(data_to_save).execute()
                    danh_sach_link_cu.add(clean_map_url)
                    da_xu_ly += 1
                    print(f"✅ Đã lưu thành công vào Supabase!")
                    print("-" * 40)
                    
                except Exception as e:
                    print(f"⚠️ Bỏ qua mục tiêu {i+1} vì lỗi trích xuất.")

        except Exception as e:
            print("❌ Lỗi cấu trúc Google Maps hoặc mạng chậm:", e)

        browser.close()
        print(f"\n🎉 XONG! Thu hoạch được {da_xu_ly} Homestay. Dữ liệu đã vào Két sắt!")

if __name__ == "__main__":
    scrape_and_save_homestays()
