import os, sys, re, time, requests, io, json, cloudinary, cloudinary.uploader
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from supabase import create_client
from PIL import Image

# ================= 1. CẤU HÌNH =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
cloudinary.config(cloudinary_url=os.environ.get("CLOUDINARY_URL"))

def extract_number(text):
    if not text: return 0
    match = re.search(r'\d+', str(text).replace('.', '').replace(',', ''))
    return int(match.group()) if match else 0

# ================= 2. AI PHÂN TÍCH (CÓ LOG CHI TIẾT) =================
def ai_analyze_bds(tieu_de, ngu_canh_tho):
    print(f"🤖 Đang gửi dữ liệu sang AI (Độ dài text: {len(ngu_canh_tho)} ký tự)...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Bạn là chuyên gia BĐS. Hãy đọc dữ liệu sau và trả về JSON chuẩn.\n"
        f"Nội dung thô: {ngu_canh_tho}"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": { "type": "json_object" },
        "temperature": 0.1
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        result = json.loads(res.json()['choices'][0]['message']['content'])
        print("✅ AI đã trả về kết quả JSON.")
        return result
    except Exception as e:
        print(f"❌ Lỗi AI Groq: {str(e)}")
        return None

# ================= 3. QUY TRÌNH THỬ NGHIỆM (CHỈ 2 TIN) =================
def run_bot_test():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 KHỞI ĐỘNG CHẾ ĐỘ THỬ NGHIỆM: LẤY 2 TIN & SOI LỖI")
    
    so_luong_da_thu_nghiem = 0
    gioi_han_thu_nghiem = 2

    # Chỉ quét trang 1 để thử nghiệm
    res = curl_requests.get(base_url, impersonate="chrome", timeout=30)
    soup = BeautifulSoup(res.content, 'html.parser')
    cards = soup.select('div.re__card-full-compact, div.js__card')
    
    print(f"📄 Tìm thấy {len(cards)} tin trên danh sách trang 1.")

    for card in cards:
        if so_luong_da_thu_nghiem >= gioi_han_thu_nghiem:
            break
            
        try:
            link_tag = card.select_one('a.js__product-link-for-product-id')
            if not link_tag: continue
            detail_url = "https://batdongsan.com.vn" + link_tag['href']

            print(f"\n--- 🔎 ĐANG SOI TIN {so_luong_da_thu_nghiem + 1}: {detail_url[-15:]} ---")
            
            res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
            soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
            
            # --- KIỂM TRA MÔ TẢ ---
            desc_body = soup_dt.select_one('.re__section-body.re__detail-content.js__section-body, .re__detail-content, .js__section-body')
            if desc_body:
                raw_desc = desc_body.get_text(separator="\n", strip=True)
                print(f"📍 Mô tả: Đã tìm thấy (đoạn đầu: {raw_desc[:50]}...)")
            else:
                raw_desc = ""
                print("📍 Mô tả: ❌ KHÔNG TÌM THẤY THẺ HTML (Selector có thể đã hỏng)!")

            # --- KIỂM TRA THÔNG SỐ (SPECS) ---
            specs_items = soup_dt.select('.re__pr-specs-content-item')
            print(f"📍 Thông số kỹ thuật: Tìm thấy {len(specs_items)} mục.")
            specs_data = []
            for item in specs_items:
                label = item.select_one('.re__pr-specs-content-item-title')
                value = item.select_one('.re__pr-specs-content-item-value')
                if label and value:
                    specs_data.append(f"{label.get_text(strip=True)}: {value.get_text(strip=True)}")
            raw_specs = "\n".join(specs_data)

            # --- KIỂM TRA HÌNH ẢNH ---
            img_tag = soup_dt.select_one('.re__pr-image-item img, .re__pr-image-item-main img, .js__pr-image-item img')
            if img_tag:
                img_url = img_tag.get('data-src') or img_tag.get('data-original') or img_tag.get('src') or ""
                print(f"📍 Ảnh gốc: {img_url[:60]}...")
            else:
                img_url = ""
                print("📍 Ảnh gốc: ❌ KHÔNG TÌM THẤY THẺ ẢNH!")

            # --- GỬI AI XỬ LÝ ---
            full_context = f"MÔ TẢ:\n{raw_desc}\n\nTHÔNG SỐ:\n{raw_specs}"
            ai_data = ai_analyze_bds(card.select_one('h3').get_text(), full_context)
            
            if ai_data:
                # Lưu thử vào Database để kiểm tra cột mo_ta
                data_to_save = {
                    "tieu_de": card.select_one('h3').get_text(strip=True),
                    "slug": f"test-{int(time.time())}-{so_luong_da_thu_nghiem}",
                    "mo_ta": ai_data.get("html_clean", "AI KHÔNG TRẢ VỀ HTML"),
                    "vi_tri_hien_thi": [detail_url],
                    "hinh_anh": [img_url] # Thử lưu link gốc xem có hiện không
                }
                
                # Chỉ insert nếu bạn muốn xem thực tế trên Supabase, 
                # nếu không chỉ cần xem Log Actions là đủ.
                supabase.table("bds_ban").insert(data_to_save).execute()
                print(f"✅ Đã lưu tin test {so_luong_da_thu_nghiem + 1} vào Supabase.")
            
            so_luong_da_thu_nghiem += 1
            time.sleep(5)

        except Exception as e:
            print(f"❌ Lỗi xử lý tin test: {str(e)}")

    print(f"\n🎉 KẾT THÚC THỬ NGHIỆM. Vui lòng xem kỹ Log ở trên để biết thẻ nào bị thiếu.")

if __name__ == "__main__":
    run_bot_test()
