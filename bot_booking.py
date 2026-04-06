# Logic xoay vòng CHUẨN: Ưu tiên Key -> sau đó mới thử các Model của Key đó
    so_key_da_thu = 0
    while so_key_da_thu < len(DANH_SACH_GROQ_KEYS):
        key_hien_tai = DANH_SACH_GROQ_KEYS[vi_tri_groq_key]
        
        for model in DANH_SACH_MODELS_AI:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key_hien_tai}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000
            }

            try:
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    text_tra_ve = res.json()['choices'][0]['message']['content'].strip()
                    try:
                        title = re.search(r'\[TITLE\](.*?)\[/TITLE\]', text_tra_ve, re.DOTALL).group(1).strip()
                        meta = re.search(r'\[META\](.*?)\[/META\]', text_tra_ve, re.DOTALL).group(1).strip()
                        desc = re.search(r'\[DESC\](.*?)\[/DESC\]', text_tra_ve, re.DOTALL).group(1).strip()
                        rooms = re.search(r'\[ROOMS\](.*?)\[/ROOMS\]', text_tra_ve, re.DOTALL).group(1).strip()
                        print(f"   🪄 Groq ({model}) xuất thần bằng Key số {vi_tri_groq_key + 1}!")
                        return {"title": title, "meta": meta, "desc": desc, "rooms": rooms}
                    except:
                        continue # Format sai thì thử model tiếp theo của Key này
                elif res.status_code in [429, 401, 403]: 
                    continue # Hết ngạch model này, thử model tiếp theo
                else:
                    continue 
            except Exception:
                continue
                
        # Key hiện tại đã vắt kiệt cả 3 model, chuyển sang Key tiếp theo
        print(f"   ❌ Key số {vi_tri_groq_key + 1} kiệt sức. Lôi Key khác ra xài!")
        vi_tri_groq_key = (vi_tri_groq_key + 1) % len(DANH_SACH_GROQ_KEYS)
        so_key_da_thu += 1
