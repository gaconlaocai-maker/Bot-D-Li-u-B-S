import os, sys, io, re, time, requests, feedparser, cloudinary, cloudinary.uploader
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. CẤU HÌNH HỆ THỐNG & BIẾN TOÀN CỤC =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

NGUON_TIN = [
    {"ten": "CafeLand", "url": "https://cafeland.vn/tin-tuc/rss/", "chu_de": "Bất động sản"},
    {"ten": "VnEconomy", "url": "https://vneconomy.vn/bat-dong-san.rss", "chu_de": "Bất động sản"},
    {"ten": "VietnamNet BĐS", "url": "https://vietnamnet.vn/bat-dong-san.rss", "chu_de": "Bất động sản"},
    {"ten": "VnExpress BĐS", "url": "https://vnexpress.net/rss/bat-dong-san.rss", "chu_de": "Bất động sản"},
    {"ten": "Reatimes", "url": "https://reatimes.vn/rss/thi-truong-2.rss", "chu_de": "Bất động sản"},
    {"ten": "VnExpress Du Lịch", "url": "https://vnexpress.net/rss/du-lich.rss", "chu_de": "Du lịch"},
    {"ten": "Dân Trí Du Lịch", "url": "https://dantri.com.vn/rss/du-lich.rss", "chu_de": "Du lịch"},
    {"ten": "Tuổi Trẻ Du Lịch", "url": "https://dulich.tuoitre.vn/rss/du-lich.rss", "chu_de": "Du lịch"},
    {"ten": "Thanh Niên Du Lịch", "url": "https://thanhnien.vn/rss/du-lich.rss", "chu_de": "Du lịch"},
    {"ten": "VietnamNet Du Lịch", "url": "https://vietnamnet.vn/du-lich.rss", "chu_de": "Du lịch"}
]

# Quản lý Trạng thái Thông minh
TONG_LOI_HE_THONG = 0
GIOI_HAN_LOI_MAX = 50

def kiem_tra_gioi_han_loi():
    """Chốt chặn an toàn: Dừng toàn bộ bot nếu lỗi vượt 50 lần"""
    global TONG_LOI_HE_THONG
    if TONG_LOI_HE_THONG >= GIOI_HAN_LOI_MAX:
        print(f"🚨 CẢNH BÁO: Đã chạm mốc {GIOI_HAN_LOI_MAX} lỗi toàn cục. Tự động tắt Bot!")
        sys.exit(1)

# ================= 2. GỌI API GROQ (SIÊU TỐC ĐỘ) =================
def goi_ai_groq(prompt):
    global TONG_LOI_HE_THONG
    
    # CẬP NHẬT MODEL MỚI: Sử dụng Llama 3.3 70B Versatile
    model_name = "llama-3.3-70b-versatile" 
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        data = res.json()
        
        if "choices" in data:
            print(f"🪄 Groq (Llama 3.3) đã phản hồi thành công!")
            return data["choices"][0]["message"]["content"].replace("```html", "").replace("```", "").strip()
        else:
            msg = data.get('error', {}).get('message', 'Lỗi không xác định từ Groq')
            print(f"⚠️ Lỗi từ Groq API: {msg}")
            TONG_LOI_HE_THONG += 1
            kiem_tra_gioi_han_loi()
            return None
            
    except Exception as e:
        print(f"⚠️ Lỗi kết nối mạng đến Groq: {e}")
        TONG_LOI_HE_THONG += 1
        kiem_tra_gioi_han_loi()
        return None

# ================= 3. XỬ LÝ ẢNH WEBP =================
def xu_ly_anh_webp(url_goc, slug):
    global TONG_LOI_HE_THONG
    try:
        if not url_goc: return "https://images.unsplash.com/photo-1560518883-ce09059eeffa"
        res = requests.get(url_goc, timeout=15)
        img_data = io.BytesIO(res.content)
        
        with Image.open(img_data) as img:
            rgb_img = img.convert("RGB")
            buffer = io.BytesIO()
            rgb_img.save(buffer, format="WEBP", quality=75)
            buffer.seek(0)
            
            up = cloudinary.uploader.upload(buffer, folder="laocai_bds", public_id=slug)
            return up['secure_url']
    except Exception as e:
        print(f"⚠️ Lỗi tải ảnh: {e}")
        TONG_LOI_HE_THONG += 1
        kiem_tra_gioi_han_loi()
        return "https://images.unsplash.com/photo-1560518883-ce09059eeffa"

# ================= 4. LOGIC CHẠY BOT =================
def thuc_thi():
    global TONG_LOI_HE_THONG
    print("🚀 Khởi động Bot - Chế độ: GROQ LLAMA 3.3 & BẮT BUỘC LẤY ĐỦ 5 TIN")
    so_luong_can_lay = 5
    so_luong_da_lay = 0

    for nguon in NGUON_TIN:
        if so_luong_da_lay >= so_luong_can_lay:
            break

        print(f"\n📡 Đang quét nguồn: {nguon['ten']} ({nguon['chu_de']})")
        
        try:
            feed = feedparser.parse(nguon['url'])
        except Exception:
            TONG_LOI_HE_THONG += 1
            continue
            
        if not feed.entries: 
            continue
        
        loi_tren_mot_nguon = 0
        
        for p in feed.entries:
            if so_luong_da_lay >= so_luong_can_lay:
                break
                
            if loi_tren_mot_nguon >= 3:
                print(f"⏭️ BỎ QUA NGUỒN: {nguon['ten']} đang gặp sự cố. Chuyển nguồn khác!")
                break
                
            try:
                check = supabase.table("tin_tuc").select("id").eq("nguon_bai", p.link).execute()
                if len(check.data) > 0:
                    continue 
            except Exception as e:
                print(f"⚠️ Lỗi kết nối DB: {e}")
                TONG_LOI_HE_THONG += 1
                loi_tren_mot_nguon += 1
                kiem_tra_gioi_han_loi()
                continue

            try:
                res = requests.get(p.link, timeout=15)
                soup = BeautifulSoup(res.content, 'html.parser')
                body = "\n".join([t.get_text() for t in soup.find_all('p') if len(t.get_text()) > 60])
                
                if not body.strip():
                    loi_tren_mot_nguon += 1
                    continue
                    
                img_tag = soup.find("meta", property="og:image")
                url_anh = img_tag["content"] if img_tag else ""
                
                prompt = (
                    f"Đóng vai một chuyên gia biên tập tin tức {nguon['chu_de']}. "
                    f"Hãy viết lại bài báo sau để chuẩn SEO, hướng tới thị trường Lào Cai. "
                    "QUY TẮC: CHỈ TRẢ VỀ NỘI DUNG BẰNG MÃ HTML (bắt đầu luôn bằng thẻ <p> hoặc <h2>). "
                    "KHÔNG thêm câu chào hỏi, lời bình luận, hay kết luận của AI.\n\n"
                    f"Nội dung bài gốc: {body[:2500]}"
                )
                
                noi_dung_ai = goi_ai_groq(prompt)
                
                if not noi_dung_ai:
                    print(f"❌ Bỏ qua bài: {p.title[:30]}...")
                    loi_tren_mot_nguon += 1
                    continue
                
                loi_tren_mot_nguon = 0 
                
                slug = re.sub(r'\W+', '-', p.title.lower())[:50] + "-" + str(int(time.time()))
                anh_final = xu_ly_anh_webp(url_anh, slug)
                
                supabase.table("tin_tuc").insert({
                    "tieu_de": p.title,
                    "slug": slug,
                    "noi_dung_html": noi_dung_ai,
                    "anh_bia": anh_final,
                    "nguon_bai": p.link,
                    "chuyen_muc": nguon['chu_de']
                }).execute()
                
                so_luong_da_lay += 1
                print(f"✅ [{so_luong_da_lay}/{so_luong_can_lay}] Đã đăng thành công: {p.title[:40]}...")
                
                time.sleep(20)
                
            except Exception as e:
                print(f"❌ Lỗi xử lý dữ liệu: {e}")
                TONG_LOI_HE_THONG += 1
                loi_tren_mot_nguon += 1
                kiem_tra_gioi_han_loi()
                continue

    print(f"\n🎉 KẾT THÚC. Số bài đã đăng: {so_luong_da_lay}/{so_luong_can_lay}. Tổng lỗi toàn hệ thống: {TONG_LOI_HE_THONG}")

if __name__ == "__main__":
    thuc_thi()
