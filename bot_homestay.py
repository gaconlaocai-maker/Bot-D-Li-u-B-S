import os, requests, time, re
from supabase import create_client

# ================= 1. CẤU HÌNH HỆ THỐNG =================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")

if not RAPIDAPI_KEY:
    print("❌ LỖI: Chưa có RAPIDAPI_KEY. Sếp nhớ lên RapidAPI lấy mã bỏ vào GitHub Secrets nhé!")
    exit()

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

# ================= 2. QUY TRÌNH GỌI RAPIDAPI (MIỄN PHÍ) =================
def fetch_homestay_rapidapi(query="Homestay tại Sa Pa"):
    print(f"🚀 KHỞI ĐỘNG LÍNH ĐÁNH THUÊ (RAPIDAPI) CÀO GOOGLE MAPS")
    print(f"🎯 Mục tiêu: '{query}'\n" + "="*40)
    
    danh_sach_link_cu = set()
    try:
        res_db = supabase.table("phong_nghi").select("map_url").execute()
        for row in res_db.data:
            if row.get("map_url"): danh_sach_link_cu.add(row["map_url"])
    except: pass

    da_xu_ly = 0

    url = "https://local-business-data.p.rapidapi.com/search"
    querystring = {
        "query": query,
        "language": "vi",
        "region": "vn",
        "limit": "20" # Lấy 20 kết quả 1 lần để đỡ tốn Request
    }

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "local-business-data.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        
        # Nếu API báo hết tiền hoặc lỗi
        if 'data' not in data:
            print("❌ LỖI TỪ API:", data.get('message', 'Không rõ nguyên nhân. Có thể sếp chưa Subscribe gói Free.'))
            return

        results = data.get('data', [])
        print(f"🎯 API trả về {len(results)} mục tiêu. Bắt đầu bơm vào Két sắt...\n")

        for place in results:
            name = place.get('name', 'Đang cập nhật')
            phone = place.get('phone_number', '')
            address = place.get('full_address', 'Lào Cai')
            map_url = place.get('place_link', '')
            website = place.get('website', '') # Lấy thêm Website nếu có

            if map_url in danh_sach_link_cu:
                print(f"⏭️ BỎ QUA: {name} (Đã có trong Két sắt)")
                continue
            
            print(f"🏠 Tên phòng: {name}")
            print(f"📞 Số điện thoại: {phone}")
            print(f"📍 Địa chỉ: {address}")

            slug = tao_slug(name)[:50] + "-" + str(int(time.time()))
            
            # Gom Website vào Tiện ích (để sau này Sale có cái xem thêm)
            tien_ich_demo = ["Wifi miễn phí", "Điều hòa"]
            if website: tien_ich_demo.append(f"Website: {website}")

            data_to_save = {
                "tieu_de": name,
                "slug": slug,
                "vi_tri": address,
                "so_dien_thoai": phone,
                "map_url": map_url,
                "loai_bds": "Homestay",
                "trang_thai": "Chờ duyệt",
                "gia": "Liên hệ",
                "tien_ich": tien_ich_demo,
                "hinh_anh": ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=1200&q=80"]
            }

            supabase.table("phong_nghi").insert(data_to_save).execute()
            danh_sach_link_cu.add(map_url)
            da_xu_ly += 1
            print(f"✅ Đã lưu vào Supabase!")
            print("-" * 40)
            
            time.sleep(0.5) 

    except Exception as e:
        print("❌ Lỗi đường truyền gọi API:", e)

    print(f"\n🎉 XONG! Húp trọn {da_xu_ly} Homestay hoàn toàn MIỄN PHÍ!")

if __name__ == "__main__":
    fetch_homestay_rapidapi()
