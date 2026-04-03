from curl_cffi import requests
from bs4 import BeautifulSoup
import time

def bóc_tách_trang(url, so_trang):
    print(f"📡 Đang quét Trang {so_trang}: {url}")
    try:
        res = requests.get(url, impersonate="chrome", timeout=30)
        if res.status_code != 200:
            print(f"❌ Lỗi truy cập trang {so_trang}: {res.status_code}")
            return []
        
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Ống ngắm chuẩn: Chỉ lấy các card tin đăng chính chủ/môi giới
        # Class re__card-full-compact là chuẩn nhất hiện tại cho danh sách
        cards = soup.select('div.re__card-full-compact, div.js__card')
        
        ket_qua = []
        for card in cards:
            # Lấy Tiêu đề
            title_tag = card.select_one('h3.re__card-title span, span.pr-title')
            tieu_de = title_tag.get_text(strip=True) if title_tag else "Không có tiêu đề"
            
            # Lấy Giá
            price_tag = card.select_one('span.re__card-config-price')
            gia = price_tag.get_text(strip=True) if price_tag else "Thỏa thuận"
            
            # Lấy Diện tích
            area_tag = card.select_one('span.re__card-config-area')
            dt = area_tag.get_text(strip=True) if area_tag else "N/A"
            
            # Lấy Link (để sau này AI vào đọc chi tiết)
            link_tag = card.select_one('a.js__product-link-for-product-id')
            link = "https://batdongsan.com.vn" + link_tag['href'] if link_tag else ""
            
            if tieu_de != "Không có tiêu đề":
                ket_qua.append({
                    "tieu_de": tieu_de,
                    "gia": gia,
                    "dien_tich": dt,
                    "link": link
                })
        
        return ket_qua
    except Exception as e:
        print(f"⚠️ Lỗi tại trang {so_trang}: {e}")
        return []

def chay_bot_da_trang(tong_so_trang=3):
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    tat_ca_bds = []
    
    for i in range(1, tong_so_trang + 1):
        # Trang 1 giữ nguyên, từ trang 2 thêm /p2
        url_hien_tai = base_url if i == 1 else f"{base_url}/p{i}"
        
        tin_trang_nay = bóc_tách_trang(url_hien_tai, i)
        tat_ca_bds.extend(tin_trang_nay)
        
        print(f"✅ Đã lấy được {len(tin_trang_nay)} tin từ trang {i}")
        time.sleep(5) # Nghỉ để không bị quét IP
        
    print("-" * 50)
    print(f"🎉 TỔNG KẾT: Đã thu thập {len(tat_ca_bds)} bất động sản từ {tong_so_trang} trang.")
    
    # In thử 10 tin đầu tiên
    for idx, item in enumerate(tat_ca_bds[:10], 1):
        print(f"{idx}. {item['tieu_de']} | {item['gia']} | {item['dien_tich']}")

if __name__ == "__main__":
    chay_bot_da_trang(3) # Bạn có thể đổi số trang muốn quét ở đây
