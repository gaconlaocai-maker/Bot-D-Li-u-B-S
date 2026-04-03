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

# ================= 2. QUY TRÌNH GỌI RAPIDAPI CÔNG NGHIỆP =================
# Sếp muốn cào thêm gì cứ ném thêm vào danh sách này nhé!
DANH_SACH_TU_KHOA = [
    "Khách sạn tại Sa Pa Lào Cai",
    "Nhà nghỉ tại Sa Pa Lào Cai",
    "Homestay tại thành phố Lào Cai",
    "Khách sạn tại thành phố Lào Cai",
    "Nhà nghỉ tại thành phố Lào Cai"
]

def phan_loai_bds(query):
    q = query.lower()
    if "khách sạn" in q: return "Khách sạn"
    if "nhà nghỉ" in q: return "Nhà nghỉ"
    return "Homestay"

def fetch_homestay_rapidapi():
    print(f"🚀 KHỞI ĐỘNG MÁY HÚT BỤI CÔNG NGHIỆP")
    print(f"🎯 Sẽ quét {len(DANH_SACH_TU_KHOA)} thị trường!\n" + "="*40)
    
    danh_sach_link_cu = set()
    try:
        res_db = supabase.table("phong_nghi").select("map_url").execute()
        for row in res_db.data:
            if row.get("map_url"): danh_sach_link_cu.add(row["map_url"])
    except: pass

    tong_da_xu_ly = 0

    for query in DANH_SACH_TU_KHOA:
        print(f"\n⏳ ĐANG QUÉT TỪ KHÓA: '{query}'")
        
        url = "https://local-business-data.p.rapidapi.com/search"
        querystring = {
            "query": query,
            "language": "vi",
            "region": "vn",
            "limit": "20" # Lấy 20 cái mỗi từ khóa, tổng sẽ được khoảng 100 cái
        }

        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "local-business-data.p.rapidapi.com"
        }

        try:
            response = requests.get(url, headers=headers, params=querystring)
            data = response.json()
            
            if 'data' not in data:
                print(f"❌ LỖI TỪ API ({query}):", data.get('message', 'API lỗi'))
                continue

            results = data.get('data', [])
            loai_bds = phan_loai_bds(query)
            da_xu_ly_truong_hop_nay = 0

            for place in results:
                name = place.get('name', 'Đang cập nhật')
                phone = place.get('phone_number', '')
                address = place.get('full_address', 'Lào Cai')
                map_url = place.get('place_link', '')
                website = place.get('website', '')

                if map_url in danh_sach_link_cu:
                    continue
                
                print(f"🏠 [+ {loai_bds}] {name} - 📞 {phone}")

                slug = tao_slug(name)[:50] + "-" + str(int(time.time()))
                
                tien_ich_demo = ["Wifi miễn phí", "Điều hòa"]
                if website: tien_ich_demo.append(f"Website: {website}")

                data_to_save = {
                    "tieu_de": name,
                    "slug": slug,
                    "vi_tri": address,
                    "so_dien_thoai": phone,
                    "map_url": map_url,
                    "loai_bds": loai_bds, # Gán tự động theo từ khóa
                    "trang_thai": "Chờ duyệt",
                    "gia": "Liên hệ",
                    "tien_ich": tien_ich_demo,
                    "hinh_anh": ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=1200&q=80"]
                }

                supabase.table("phong_nghi").insert(data_to_save).execute()
                danh_sach_link_cu.add(map_url)
                da_xu_ly_truong_hop_nay += 1
                tong_da_xu_ly += 1
                
                time.sleep(0.5) 
            
            print(f"✅ Vét xong {da_xu_ly_truong_hop_nay} data cho '{query}'.")
            time.sleep(2) # Nghỉ 2 giây trước khi quét từ khóa tiếp theo cho an toàn

        except Exception as e:
            print(f"❌ Lỗi đường truyền '{query}':", e)

    print(f"\n🎉 TỔNG KẾT: Đêm nay hút trọn {tong_da_xu_ly} cơ sở lưu trú vào Két sắt!")

if __name__ == "__main__":
    fetch_homestay_rapidapi()
