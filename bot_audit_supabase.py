import os
import json
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import requests
from unidecode import unidecode

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
APPLY_FIXES = os.getenv("APPLY_FIXES", "false").lower() == "true"
MAX_ROWS = int(os.getenv("MAX_ROWS_PER_TABLE", "200"))
USE_AI_AUDIT = os.getenv("USE_AI_AUDIT", "false").lower() == "true"
AUDIT_ONLY_TABLES = os.getenv("AUDIT_ONLY_TABLES", "")
MIN_LOCAL_SCORE = int(os.getenv("MIN_LOCAL_SCORE", "50"))

# Allowed locations for BĐS & Việc làm
LAO_CAI_LOCATIONS = [
    "lào cai", "sa pa", "sapa", "bắc hà", "bảo thắng", "bảo yên", "văn bàn",
    "bát xát", "mường khương", "si ma cai", "cam đường", "cốc lếu", "bắc cường",
    "mường hoa", "tả van", "y tý"
]

SUSPICIOUS_LOCATIONS = [
    "đông anh", "thủ dầu một", "bảo lộc", "quận 1", "tp.hcm", "hồ chí minh",
    "hà nội", "bình dương", "đồng nai", "yên bái", "nghĩa lộ"
]

report_stats = {
    "total_tables": 0,
    "total_rows": 0,
    "total_issues": 0,
    "issues_by_type": {
        "source_url_leaked": 0,
        "missing_location": 0,
        "suspicious_area": 0,
        "missing_image": 0,
        "off_region": 0,
        "low_relevance_news": 0,
        "invalid_slug": 0,
        "invalid_area_value": 0
    },
    "rows_to_fix": 0,
    "rows_fixed": 0,
    "errors": 0
}

audit_logs = []

def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        exit(1)
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def is_source_url(text):
    if not text:
        return False
    text = str(text).lower()
    return any(domain in text for domain in ["http", "https", "batdongsan.com.vn", "alonhadat.com.vn", "nhatot.com", "chotot.com"])

def clean_text_array(arr):
    if not arr:
        return []
    if isinstance(arr, str):
        try:
            arr = json.loads(arr)
        except:
            if arr.startswith("{") and arr.endswith("}"):
                # Postgres text[] like '{a,b}'
                arr_inner = arr[1:-1]
                arr = [x.strip(' "') for x in arr_inner.split(',')] if arr_inner else []
            else:
                arr = [arr]
    if not isinstance(arr, list):
        return []
    return [x for x in arr if x and not is_source_url(x)]

def get_columns(supabase: Client, table_name: str):
    try:
        res = supabase.table(table_name).select("*").limit(1).execute()
        if len(res.data) > 0:
            return list(res.data[0].keys())
        return None
    except Exception as e:
        print(f"Error checking table {table_name}: {e}")
        return None

def create_slug(text):
    if not text:
        return f"post-{int(time.time())}"
    text = unidecode(text).lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def check_location(text):
    if not text: return False
    text = text.lower()
    return any(loc in text for loc in LAO_CAI_LOCATIONS)

def call_groq_audit(title, desc):
    if not GROQ_API_KEY:
        return None
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = f"""You are an auditor for LaoCaiView, a local news/real estate site for Lao Cai and Sa Pa (Vietnam).
Analyze the following article. Is it relevant to Lao Cai/Sa Pa local news (real estate, tourism, local jobs, local infrastructure)?
Return ONLY valid JSON (no markdown):
{{
  "is_relevant": true|false,
  "local_score": 0-100,
  "topic_type": "string",
  "issues": ["list of strings"],
  "suggested_action": "keep|hide|review",
  "reason": "string"
}}
Title: {title}
Content snippet: {desc[:500] if desc else ''}
"""
        payload = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        content = r.json()['choices'][0]['message']['content'].strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content)
    except Exception as e:
        print(f"Groq API error: {e}")
        return None

def apply_update(supabase: Client, table, row_id, updates, reason):
    report_stats["rows_to_fix"] += 1
    log_entry = {
        "table": table,
        "id": row_id,
        "reason": reason,
        "updates": updates,
        "timestamp": datetime.now().isoformat()
    }
    audit_logs.append(log_entry)
    print(f"[ACTION] Updating {table} (id: {row_id}): {updates} - {reason}")
    if APPLY_FIXES and not DRY_RUN:
        try:
            supabase.table(table).update(updates).eq("id", row_id).execute()
            report_stats["rows_fixed"] += 1
            print(" -> Update successful")
        except Exception as e:
            report_stats["errors"] += 1
            print(f" -> Update failed: {e}")
    else:
        print(" -> Dry run, skipped")

def audit_bds_ban(supabase: Client, columns):
    table = "bds_ban"
    res = supabase.table(table).select("*").limit(MAX_ROWS).execute()
    rows = res.data
    report_stats["total_rows"] += len(rows)

    for row in rows:
        updates = {}
        issues = []
        
        # 1. vi_tri leaked URL
        if 'vi_tri' in columns and is_source_url(row.get('vi_tri')):
            issues.append("vi_tri leaked URL")
            report_stats["issues_by_type"]["source_url_leaked"] += 1
            if 'source_url' in columns and not row.get('source_url'):
                updates['source_url'] = row['vi_tri']
            updates['vi_tri'] = 'Lào Cai - Sa Pa'
            if 'needs_review' in columns: updates['needs_review'] = True
            
        # 2. vi_tri_hien_thi leaked URL
        if 'vi_tri_hien_thi' in columns and is_source_url(row.get('vi_tri_hien_thi')):
            issues.append("vi_tri_hien_thi leaked URL")
            report_stats["issues_by_type"]["source_url_leaked"] += 1
            if 'source_url' in columns and not row.get('source_url'):
                updates['source_url'] = row['vi_tri_hien_thi']
            updates['vi_tri_hien_thi'] = None # Clear it
            
        # 3. vi_tri empty
        if 'vi_tri' in columns and not row.get('vi_tri') and 'vi_tri' not in updates:
            tieu_de = str(row.get('tieu_de', '')).lower()
            mo_ta = str(row.get('mo_ta', '')).lower()
            found_loc = next((loc for loc in LAO_CAI_LOCATIONS if loc in tieu_de or loc in mo_ta), None)
            if found_loc:
                updates['vi_tri'] = found_loc.title()
                issues.append("vi_tri inferred")
                report_stats["issues_by_type"]["missing_location"] += 1
            else:
                issues.append("vi_tri empty & not inferrable")
                report_stats["issues_by_type"]["missing_location"] += 1
                updates['vi_tri'] = 'Lào Cai - Sa Pa'
                if 'needs_review' in columns: updates['needs_review'] = True
                
        # 4. Off region
        vi_tri_check = (updates.get('vi_tri') or row.get('vi_tri') or "").lower()
        if any(loc in vi_tri_check for loc in SUSPICIOUS_LOCATIONS):
            issues.append("suspicious region")
            report_stats["issues_by_type"]["suspicious_area"] += 1
            if 'show_on_home' in columns: updates['show_on_home'] = False
            if 'needs_review' in columns: updates['needs_review'] = True
            if 'trang_thai' in columns: updates['trang_thai'] = 'Ẩn'

        # 5. Missing image
        if 'hinh_anh' in columns:
            ha = row.get('hinh_anh')
            if not ha or ha == '[]' or ha == []:
                issues.append("missing image")
                report_stats["issues_by_type"]["missing_image"] += 1
                if 'needs_review' in columns: updates['needs_review'] = True

        # 6. Slug
        if 'slug' in columns and not row.get('slug'):
            issues.append("missing slug")
            report_stats["issues_by_type"]["invalid_slug"] += 1
            base_slug = create_slug(row.get('tieu_de'))
            updates['slug'] = f"{base_slug}-{row['id']}" if 'id' in row else f"{base_slug}-{int(time.time())}"

        # 7. Area parsing error
        if 'dien_tich' in columns:
            dt = row.get('dien_tich')
            if dt and isinstance(dt, (int, float)) and dt < 10:
                tieu_de = str(row.get('tieu_de', ''))
                mo_ta = str(row.get('mo_ta', ''))
                match = re.search(r'(\d+[\.\,]\d+|\d+)\s*(m2|m²)', tieu_de + ' ' + mo_ta, re.IGNORECASE)
                if match:
                    issues.append("invalid area value")
                    report_stats["issues_by_type"]["invalid_area_value"] += 1
                    if 'needs_review' in columns: updates['needs_review'] = True

        if issues:
            report_stats["total_issues"] += 1
            if updates:
                apply_update(supabase, table, row['id'], updates, ", ".join(issues))

def audit_viec_lam(supabase: Client, columns):
    table = "viec_lam"
    res = supabase.table(table).select("*").limit(MAX_ROWS).execute()
    rows = res.data
    report_stats["total_rows"] += len(rows)

    for row in rows:
        updates = {}
        issues = []
        
        dia_diem = str(row.get('dia_diem', '')).lower()
        if any(loc in dia_diem for loc in SUSPICIOUS_LOCATIONS) and not check_location(dia_diem):
            issues.append("job off region")
            report_stats["issues_by_type"]["off_region"] += 1
            if 'show_on_home' in columns: updates['show_on_home'] = False
            if 'trang_thai' in columns: updates['trang_thai'] = 'Ẩn'
            if 'needs_review' in columns: updates['needs_review'] = True
            
        if 'slug' in columns and not row.get('slug'):
            issues.append("missing slug")
            report_stats["issues_by_type"]["invalid_slug"] += 1
            base_slug = create_slug(row.get('tieu_de'))
            updates['slug'] = f"{base_slug}-{row['id']}" if 'id' in row else f"{base_slug}-{int(time.time())}"

        if issues:
            report_stats["total_issues"] += 1
            if updates:
                apply_update(supabase, table, row['id'], updates, ", ".join(issues))

def audit_tin_tuc(supabase: Client, columns):
    table = "tin_tuc"
    res = supabase.table(table).select("*").limit(MAX_ROWS).execute()
    rows = res.data
    report_stats["total_rows"] += len(rows)

    for row in rows:
        updates = {}
        issues = []
        
        tieu_de = str(row.get('tieu_de', '')).lower()
        noi_dung = str(row.get('noi_dung', '')).lower()
        
        is_local = check_location(tieu_de) or check_location(noi_dung)
        
        if not is_local:
            off_topics = ["giá vàng", "chứng khoán", "spacex", "iran", "mỹ", "showbiz", "bóng đá"]
            if any(t in tieu_de for t in off_topics):
                issues.append("low relevance news")
                report_stats["issues_by_type"]["low_relevance_news"] += 1
                if 'show_on_home' in columns: updates['show_on_home'] = False
                if 'trang_thai' in columns: updates['trang_thai'] = 'Ẩn'
                if 'needs_review' in columns: updates['needs_review'] = True
            elif USE_AI_AUDIT:
                ai_result = call_groq_audit(tieu_de, noi_dung)
                if ai_result:
                    score = ai_result.get('local_score', 100)
                    if score < MIN_LOCAL_SCORE:
                        issues.append(f"AI: Low local score {score}. Reason: {ai_result.get('reason')}")
                        report_stats["issues_by_type"]["low_relevance_news"] += 1
                        if 'show_on_home' in columns: updates['show_on_home'] = False
                        if 'trang_thai' in columns: updates['trang_thai'] = 'Ẩn'
                        if 'needs_review' in columns: updates['needs_review'] = True
                        
        if 'slug' in columns and not row.get('slug'):
            issues.append("missing slug")
            report_stats["issues_by_type"]["invalid_slug"] += 1
            base_slug = create_slug(row.get('tieu_de'))
            updates['slug'] = f"{base_slug}-{row['id']}" if 'id' in row else f"{base_slug}-{int(time.time())}"

        if issues:
            report_stats["total_issues"] += 1
            if updates:
                apply_update(supabase, table, row['id'], updates, ", ".join(issues))

def write_reports():
    with open("audit_report.json", "w", encoding="utf-8") as f:
        json.dump({"stats": report_stats, "logs": audit_logs}, f, ensure_ascii=False, indent=2)
        
    with open("audit_report.md", "w", encoding="utf-8") as f:
        f.write("# Supabase Audit Report\n\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n")
        f.write(f"**Mode:** {'DRY RUN (No changes applied)' if DRY_RUN else 'APPLY FIXES'}\n\n")
        f.write("## Statistics\n")
        f.write(f"- Tables Checked: {report_stats['total_tables']}\n")
        f.write(f"- Rows Scanned: {report_stats['total_rows']}\n")
        f.write(f"- Total Issues Found: {report_stats['total_issues']}\n")
        f.write(f"- Rows Flagged to Fix: {report_stats['rows_to_fix']}\n")
        f.write(f"- Rows Fixed: {report_stats['rows_fixed']}\n")
        f.write(f"- Errors encountered: {report_stats['errors']}\n\n")
        
        f.write("## Issues By Type\n")
        for k, v in report_stats['issues_by_type'].items():
            f.write(f"- {k}: {v}\n")
            
        f.write("\n## Audit Logs (Samples)\n")
        for log in audit_logs[:50]:
            f.write(f"- **{log['table']} (ID: {log['id']})**: {log['reason']}\n")
            f.write(f"  - Action: `{log['updates']}`\n")
            
def main():
    print(f"Starting audit... DRY_RUN={DRY_RUN}, APPLY_FIXES={APPLY_FIXES}")
    supabase = get_supabase_client()
    tables_to_check = ["bds_ban", "tin_tuc", "viec_lam", "phong_nghi", "mat_bang_thue"]
    
    if AUDIT_ONLY_TABLES:
        tables_to_check = [t.strip() for t in AUDIT_ONLY_TABLES.split(',')]
        
    for table in tables_to_check:
        print(f"Checking table: {table}")
        columns = get_columns(supabase, table)
        if not columns:
            print(f" -> Table {table} does not exist or empty. Skipping.")
            continue
            
        report_stats["total_tables"] += 1
        try:
            if table == "bds_ban":
                audit_bds_ban(supabase, columns)
            elif table == "viec_lam":
                audit_viec_lam(supabase, columns)
            elif table == "tin_tuc":
                audit_tin_tuc(supabase, columns)
            else:
                # Generic audit for others if needed
                print(f" -> No specific audit rules for {table}. Checked columns.")
        except Exception as e:
            print(f"Error auditing table {table}: {e}")
            report_stats["errors"] += 1
            
    write_reports()
    print("\n--- AUDIT COMPLETE ---")
    print(f"Scanned {report_stats['total_rows']} rows across {report_stats['total_tables']} tables.")
    print(f"Found {report_stats['total_issues']} issues.")
    if not DRY_RUN and APPLY_FIXES:
        print(f"Fixed {report_stats['rows_fixed']} rows.")
    else:
        print(f"Proposed fixes for {report_stats['rows_to_fix']} rows (DRY RUN).")

if __name__ == "__main__":
    main()
