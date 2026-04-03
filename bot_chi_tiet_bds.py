# ================= CẬP NHẬT PHẦN LẤY CHI TIẾT =================
def run_bot():
    base_url = "https://batdongsan.com.vn/nha-dat-ban-sa-pa-lca"
    print("🚀 Đang quét dữ liệu chuyên sâu cho Sa Pa...")

    for page in range(1, 4):
        url = base_url if page == 1 else f"{base_url}/p{page}"
        res = curl_requests.get(url, impersonate="chrome", timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        cards = soup.select('div.re__card-full-compact, div.js__card')

        for card in cards:
            link_tag = card.select_one('a.js__product-link-for-product-id')
            if not link_tag: continue
            detail_url = "https://batdongsan.com.vn" + link_tag['href']

            # Kiểm tra trùng lặp (dùng contains cho kiểu Array)
            check = supabase.table("bds_ban").select("id").contains("vi_tri_hien_thi", [detail_url]).execute()
            if len(check.data) > 0: continue

            print(f"🔍 Đang bóc tách chi tiết: {detail_url[-15:]}")
            res_dt = curl_requests.get(detail_url, impersonate="chrome", timeout=30)
            soup_dt = BeautifulSoup(res_dt.content, 'html.parser')
            
            # --- CẬP NHẬT SELECTOR MỚI TẠI ĐÂY ---
            # 1. Lấy mô tả (Tìm ở nhiều lớp fallback)
            desc_body = soup_dt.select_one('div.re__detail-content, div.js__section-body, div.re__section-body')
            raw_desc = desc_body.get_text(separator="\n", strip=True) if desc_body else ""
            
            # 2. Lấy đặc điểm (Pháp lý, Mặt tiền...) để bổ trợ cho AI
            specs = soup_dt.select('div.re__pr-specs-content-item')
            raw_specs = "\n".join([s.get_text(strip=True) for s in specs])
            
            # Gộp dữ liệu để AI phân tích
            full_context = f"MÔ TẢ:\n{raw_desc}\n\nĐẶC ĐIỂM:\n{raw_specs}"
            
            if not raw_desc:
                print(f"⚠️ Không lấy được mô tả cho bài: {detail_url}")
                continue
            
            # AI xử lý dữ liệu (Dùng prompt JSON Mode của bạn)
            ai_data = ai_analyze_bds(card.select_one('h3').get_text(), full_context)
            if not ai_data: continue

            # Xử lý hình ảnh và lưu trữ (Giữ nguyên phần logic cũ của bạn)
            title = card.select_one('h3').get_text(strip=True)
            slug = re.sub(r'\W+', '-', title.lower())[:50] + "-" + str(int(time.time()))
            
            img_tag = soup_dt.select_one('div.re__pr-image-item img, div.re__pr-image-item-main img')
            img_url = img_tag.get('data-src') or img_tag.get('src') if img_tag else ""
            final_img = upload_cloudinary(img_url, slug)

            data_to_save = {
                "tieu_de": title,
                "slug": slug,
                "gia": card.select_one('span.re__card-config-price').get_text(strip=True),
                "dien_tich": extract_number(card.select_one('span.re__card-config-area').get_text()),
                "vi_tri": "Sa Pa, Lào Cai",
                "loai_bds": ai_data.get("loai_bds"),
                "hinh_anh": [final_img] if final_img else [],
                "mo_ta": ai_data.get("html_clean"),
                "phap_ly": ai_data.get("phap_ly") or "Đang cập nhật",
                "huong_nha": ai_data.get("huong_nha"),
                "phong_ngu": extract_number(ai_data.get("phong_ngu")),
                "phong_tam": extract_number(ai_data.get("phong_tam")),
                "meta_title": ai_data.get("meta_title"),
                "meta_desc": ai_data.get("meta_desc"),
                "vi_tri_hien_thi": [detail_url]
            }

            try:
                supabase.table("bds_ban").insert(data_to_save).execute()
                print(f"✅ Đã lưu: {title[:30]}...")
                time.sleep(20) # Tăng thời gian nghỉ để tránh bị phát hiện
            except Exception as e:
                print(f"❌ Lỗi Database: {e}")
