from curl_cffi import requests
from bs4 import BeautifulSoup

def cao_du_lieu_nha_dat_sapa():
    url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print(f"🚀 Khởi động Bot BĐS - Đóng giả trình duyệt Chrome truy cập: {url}")
    
    try:
        response = requests.get(
            url, 
            impersonate="chrome", 
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Thất bại! Mã lỗi: {response.status_code}")
            return
            
        print("✅ Status 200 OK! Đang kiểm tra nội dung thực sự...\n")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. BẮT BỆNH: In ra tiêu đề trang để xem có bị kẹt ở màn hình CAPTCHA không
        title = soup.title.string if soup.title else "Không có thẻ title"
        print(f"🔍 Tiêu đề trang nhận được: {title}")
        
        if "Just a moment" in title or "Cloudflare" in title or "Attention Required" in title:
            print("⚠️ BÁO ĐỘNG CHÍ MẠNG: Đã bị Cloudflare chặn bằng trang thử thách CAPTCHA (Dù mã lỗi là 200)!")
            return
            
        # 2. DÒ TÌM RỘNG HƠN: Thử tìm với các class phổ biến khác của batdongsan.com.vn
        # Web này thường xuyên đổi class giữa: js__pr-item, js__card, re__card, pr-container
        danh_sach_tin = soup.find_all("div", class_=lambda x: x and ('js__pr-item' in x or 'js__card' in x or 're__card' in x or 'js__pr-card' in x))
        
        if not danh_sach_tin:
            print("⚠️ Vẫn không tìm thấy bài đăng. Cấu trúc HTML đã bị mã hóa hoặc giấu đi.")
            print("Đây là 500 ký tự đầu tiên của mã HTML để phân tích:")
            print("-" * 50)
            print(soup.prettify()[:500])
            print("-" * 50)
            return

        print(f"📌 Đã tìm thấy {len(danh_sach_tin)} bất động sản. Test thành công 100%!\n" + "-"*50)
        
        for tin in danh_sach_tin[:5]: 
            try:
                # Dùng text thay vì tìm class cụ thể để tránh lỗi nếu cấu trúc con bên trong cũng đổi
                tieu_de_tag = tin.find(["h3", "span"], class_=lambda x: x and "title" in x.lower())
                tieu_de = tieu_de_tag.get_text(strip=True) if tieu_de_tag else "Không có tiêu đề"
                
                print(f"🏠 BĐS Tìm thấy: {tieu_de}")
                
            except Exception as e:
                print(f"⚠️ Lỗi bóc tách 1 tin: {e}")
                
    except Exception as e:
        print(f"❌ Lỗi kết nối mạng: {e}")

if __name__ == "__main__":
    cao_du_lieu_nha_dat_sapa()
