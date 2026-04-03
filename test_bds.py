from curl_cffi import requests
from bs4 import BeautifulSoup

def cao_du_lieu_nha_dat_sapa():
    url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    
    print(f"🚀 Đang đóng giả trình duyệt Chrome truy cập: {url}")
    
    # Sử dụng impersonate="chrome" để vượt rào Cloudflare
    try:
        response = requests.get(
            url, 
            impersonate="chrome", 
            timeout=15
        )
        
        if response.status_code != 200:
            print(f"❌ Thất bại! Mã lỗi: {response.status_code}")
            return
            
        print("✅ Vượt rào thành công! Đang bóc tách dữ liệu...\n")
        
        # Bóc tách HTML bằng BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Phân tích cấu trúc: Các bài đăng thường nằm trong div có class "js__pr-item" hoặc "pr-container"
        danh_sach_tin = soup.find_all("div", class_=lambda x: x and 'js__pr-item' in x)
        
        if not danh_sach_tin:
            print("⚠️ Không tìm thấy bài đăng nào. Có thể cấu trúc HTML của trang đã thay đổi.")
            return

        print(f"📌 Đã tìm thấy {len(danh_sach_tin)} bất động sản tại Sa Pa:\n" + "-"*50)
        
        for tin in danh_sach_tin[:5]: # Tạm test 5 tin đầu tiên
            try:
                # Lấy Tiêu đề
                title_tag = tin.find("span", class_="pr-title")
                tieu_de = title_tag.get_text(strip=True) if title_tag else "Không có tiêu đề"
                
                # Lấy Giá
                price_tag = tin.find("span", class_="re__bo-contact-info-price")
                gia = price_tag.get_text(strip=True) if price_tag else "Thỏa thuận"
                
                # Lấy Diện tích
                area_tag = tin.find("span", class_="re__bo-contact-info-area")
                dien_tich = area_tag.get_text(strip=True) if area_tag else "Chưa rõ"
                
                # Lấy Link chi tiết
                link_tag = tin.find("a", class_="js__product-link-for-product-id")
                link = "https://batdongsan.com.vn" + link_tag['href'] if link_tag and 'href' in link_tag.attrs else "Không có link"

                print(f"🏠 Tiêu đề: {tieu_de}")
                print(f"💰 Giá: {gia} | 📐 Diện tích: {dien_tich}")
                print(f"🔗 Link: {link}\n")
                
            except Exception as e:
                print(f"Lỗi khi bóc tách 1 tin: {e}")
                
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")

if __name__ == "__main__":
    cao_du_lieu_nha_dat_sapa()
