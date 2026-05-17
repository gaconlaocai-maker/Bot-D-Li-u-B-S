import os
import sys
import unittest
from datetime import datetime, timezone
import auto_duplicate_guard

# Configure standard output encoding to utf-8 for displaying Vietnamese text beautifully
sys.stdout.reconfigure(encoding='utf-8')

# =========================================================================
#                    MOCK SUPABASE & DATABASE CLIENT
# =========================================================================

class MockResponse:
    def __init__(self, data):
        self.data = data

class MockQueryBuilder:
    def __init__(self, table_name, mock_db):
        self.table_name = table_name
        self.mock_db = mock_db
        self.filters = []
        self.update_payload = None
        self.insert_payload = None

    def select(self, columns="*"):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, values))
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def execute(self):
        if self.table_name == "bds_ban":
            if self.update_payload is not None:
                # Simulating updates to data
                updated_count = 0
                for row in self.mock_db.bds_ban_data:
                    # Apply filters
                    match = True
                    for f_type, col, val in self.filters:
                        if f_type == "eq" and row.get(col) != val:
                            match = False
                        elif f_type == "in" and row.get(col) not in val:
                            match = False
                    if match:
                        row.update(self.update_payload)
                        updated_count += 1
                return MockResponse([self.update_payload] * updated_count)
            else:
                # Query/Read operation
                data = list(self.mock_db.bds_ban_data)
                for f_type, col, val in self.filters:
                    if f_type == "eq":
                        data = [row for row in data if row.get(col) == val]
                    elif f_type == "in":
                        data = [row for row in data if row.get(col) in val]
                return MockResponse(data)
        elif self.table_name == "bds_bot_actions":
            if self.insert_payload:
                self.mock_db.logged_actions.append(self.insert_payload)
                return MockResponse([self.insert_payload])
        return MockResponse([])

class MockSupabaseClient:
    def __init__(self, bds_ban_data=None):
        self.bds_ban_data = bds_ban_data or []
        self.logged_actions = []

    def table(self, table_name):
        return MockQueryBuilder(table_name, self)

# =========================================================================
#                         TEST SUITE IMPLEMENTATION
# =========================================================================

class TestAutoDuplicateGuard(unittest.TestCase):
    def setUp(self):
        # Prepare Mock DB Client
        self.mock_db = MockSupabaseClient()
        # Override get_db_client function in auto_duplicate_guard module
        self.original_get_db_client = auto_duplicate_guard.get_db_client
        auto_duplicate_guard.get_db_client = lambda: self.mock_db

    def tearDown(self):
        # Restore original function
        auto_duplicate_guard.get_db_client = self.original_get_db_client

    def test_all_scenarios(self):
        results = []

        # -----------------------------------------------------------------
        # KỊCH BẢN 1: Hai tin giống hệt nhau về ảnh đại diện (Auto Block)
        # -----------------------------------------------------------------
        active_listing_1 = {
            "id": 101,
            "tieu_de": "Bán đất Sa Pa view thung lũng Mường Hoa",
            "slug": "ban-dat-sa-pa-view-thung-lung-muong-hoa",
            "loai_bds": "land",
            "gia": "3.5 tỷ",
            "gia_tri_so": 3500000000,
            "dien_tich": 150,
            "vi_tri": "Sa Pa, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/sapa-land-1.webp"],
            "mo_ta": "Cơ hội sở hữu mảnh đất cực đẹp view thung lũng Mường Hoa thơ mộng. Giao thông thuận tiện...",
            "trang_thai": "Mở bán"
        }
        self.mock_db.bds_ban_data = [active_listing_1]

        new_listing_1 = {
            "tieu_de": "Mảnh đất Sa Pa view siêu đẹp thung lũng Mường Hoa",
            "slug": "manh-dat-sa-pa-view-sieu-dep-thung-lung-muong-hoa",
            "loai_bds": "land",
            "gia": "3.5 tỷ",
            "gia_tri_so": 3500000000,
            "dien_tich": 150,
            "vi_tri": "Sa Pa, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/sapa-land-1.webp"], # thumbnail match
            "mo_ta": "Cơ hội vàng sở hữu mảnh đất cực đẹp view thung lũng Mường Hoa thơ mộng. Đường ô tô vào tận nơi...",
            "trang_thai": "Bản nháp"
        }

        res_new_1, bot_action_1, _ = auto_duplicate_guard.guard_new_listing(new_listing_1, mode="safe-auto")
        score_1 = res_new_1["duplicate_score"]
        status_1 = res_new_1["trang_thai"]
        action_type_1 = bot_action_1["action_type"] if bot_action_1 else "allow_insert"
        passed_1 = (score_1 >= 90 and status_1 == "Bản nháp" and action_type_1 == "auto_block_duplicate")
        results.append((
            "Kịch bản 1: Trùng ảnh đại diện (Thumbnail Match)",
            f"Score: {score_1} | Status: {status_1} | Action: {action_type_1}",
            "ĐẠT" if passed_1 else "KHÔNG ĐẠT"
        ))

        # -----------------------------------------------------------------
        # KỊCH BẢN 2: Cùng dự án nhưng số phòng/mã căn hộ khác nhau (Cho phép)
        # -----------------------------------------------------------------
        active_listing_2 = {
            "id": 102,
            "tieu_de": "Bán căn hộ chung cư 2 phòng ngủ tòa A1 - Tecco",
            "slug": "ban-can-ho-chung-cu-2-phong-ngu-toa-a1-tecco",
            "loai_bds": "nhà phố",
            "gia": "1.5 tỷ",
            "gia_tri_so": 1500000000,
            "dien_tich": 65,
            "vi_tri": "Cốc Lếu, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/tecco-1.webp"],
            "mo_ta": "Căn hộ 2 phòng ngủ, 1 vệ sinh, nội thất cơ bản, ban công hướng mát tòa A1 Tecco...",
            "trang_thai": "Mở bán"
        }
        self.mock_db.bds_ban_data = [active_listing_2]

        # Different area/price by more than 15% (90m2 vs 65m2 is ~38% difference, 2.2B vs 1.5B is ~46% difference)
        # Quick pruning should immediately discard this pair and assign score 0.
        new_listing_2 = {
            "tieu_de": "Bán căn hộ chung cư 3 phòng ngủ tòa A1 - Tecco",
            "slug": "ban-can-ho-chung-cu-3-phong-ngu-toa-a1-tecco",
            "loai_bds": "nhà phố",
            "gia": "2.2 tỷ",
            "gia_tri_so": 2200000000,
            "dien_tich": 90,
            "vi_tri": "Cốc Lếu, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/tecco-2.webp"],
            "mo_ta": "Căn hộ 3 phòng ngủ rộng rãi tòa A1 Tecco, ban công hướng Nam cực mát mẻ...",
            "trang_thai": "Bản nháp"
        }

        res_new_2, bot_action_2, _ = auto_duplicate_guard.guard_new_listing(new_listing_2, mode="safe-auto")
        score_2 = res_new_2["duplicate_score"]
        status_2 = res_new_2["trang_thai"]
        action_type_2 = bot_action_2["action_type"] if bot_action_2 else "allow_insert"
        passed_2 = (score_2 < 80 and action_type_2 == "allow_insert")
        results.append((
            "Kịch bản 2: Cùng dự án nhưng khác căn hộ/phòng",
            f"Score: {score_2} | Status: {status_2} | Action: {action_type_2}",
            "ĐẠT" if passed_2 else "KHÔNG ĐẠT"
        ))

        # -----------------------------------------------------------------
        # KỊCH BẢN 3: Tin mới trùng hoàn toàn tin đang Mở bán (Auto Block)
        # -----------------------------------------------------------------
        active_listing_3 = {
            "id": 103,
            "tieu_de": "Bán nhà mặt phố Hoàng Liên Lào Cai kinh doanh cực tốt",
            "slug": "ban-nha-mat-pho-hoang-lien-lao-cai-kinh-doanh-cuc-tot",
            "loai_bds": "nhà phố",
            "gia": "8.5 tỷ",
            "gia_tri_so": 8500000000,
            "dien_tich": 120,
            "vi_tri": "Kim Tân, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/hoang-lien-1.webp"],
            "mo_ta": "Nhà mặt phố Hoàng Liên kinh doanh tấp nập sầm uất ngày đêm, mặt tiền 6m cực hiếm...",
            "trang_thai": "Mở bán"
        }
        self.mock_db.bds_ban_data = [active_listing_3]

        new_listing_3 = active_listing_3.copy()
        new_listing_3["id"] = None
        new_listing_3["trang_thai"] = "Bản nháp"

        res_new_3, bot_action_3, _ = auto_duplicate_guard.guard_new_listing(new_listing_3, mode="safe-auto")
        score_3 = res_new_3["duplicate_score"]
        status_3 = res_new_3["trang_thai"]
        action_type_3 = bot_action_3["action_type"] if bot_action_3 else "allow_insert"
        passed_3 = (score_3 >= 95 and status_3 == "Bản nháp" and action_type_3 == "auto_block_duplicate")
        results.append((
            "Kịch bản 3: Tin trùng 100% tin đang Mở bán",
            f"Score: {score_3} | Status: {status_3} | Action: {action_type_3}",
            "ĐẠT" if passed_3 else "KHÔNG ĐẠT"
        ))

        # -----------------------------------------------------------------
        # KỊCH BẢN 4: Tin nháp đạt chuẩn 100% checklist (Auto Publish)
        # -----------------------------------------------------------------
        self.mock_db.bds_ban_data = [] # No active listings for duplicate check
        valid_draft = {
            "id": 204,
            "tieu_de": "Bán lô góc đất nền trung tâm thị trấn Sa Pa",
            "slug": "ban-lo-goc-dat-nen-trung-tam-thi-tran-sa-pa",
            "gia": "5 tỷ",
            "gia_tri_so": 5000000000,
            "dien_tich": 100,
            "loai_bds": "land",
            "vi_tri": "Sa Pa, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/valid-land.webp"],
            "mo_ta": "Lô góc 2 mặt tiền cực hiếm trung tâm thị trấn Sa Pa phù hợp xây dựng nhà hàng khách sạn...",
            "trang_thai": "Bản nháp"
        }
        self.mock_db.bds_ban_data = [valid_draft]

        actions_4 = auto_duplicate_guard.patrol_auto_publish_drafts(mode="safe-auto", dry_run=False)
        passed_4 = (len(actions_4) == 1 and actions_4[0]["action_type"] == "auto_publish" and actions_4[0]["new_status"] == "Mở bán")
        results.append((
            "Kịch bản 4: Tin nháp đạt chuẩn 100% checklist",
            f"Actions size: {len(actions_4)} | Action: {actions_4[0]['action_type'] if actions_4 else 'none'}",
            "ĐẠT" if passed_4 else "KHÔNG ĐẠT"
        ))

        # -----------------------------------------------------------------
        # KỊCH BẢN 5: Tin nháp chứa từ khóa cấm quảng cáo (Keep Draft)
        # -----------------------------------------------------------------
        forbidden_draft = {
            "id": 205,
            "tieu_de": "Siêu phẩm biệt thự Sa Pa view mây cực chất", # 'Siêu phẩm' is forbidden
            "slug": "sieu-pham-biet-thu-sa-pa-view-may-cuc-chat",
            "gia": "12 tỷ",
            "gia_tri_so": 12000000000,
            "dien_tich": 300,
            "loai_bds": "villa",
            "vi_tri": "Sa Pa, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/forbidden.webp"],
            "mo_ta": "Cam kết sinh lời không rủi ro tốt nhất thị trường...", # 'Cam kết', 'sinh lời' are forbidden
            "trang_thai": "Bản nháp"
        }
        self.mock_db.bds_ban_data = [forbidden_draft]

        actions_5 = auto_duplicate_guard.patrol_auto_publish_drafts(mode="safe-auto", dry_run=False)
        passed_5 = (len(actions_5) == 0)
        results.append((
            "Kịch bản 5: Chứa từ khóa cấm quảng cáo",
            f"Actions size: {len(actions_5)} (Draft kept)",
            "ĐẠT" if passed_5 else "KHÔNG ĐẠT"
        ))

        # -----------------------------------------------------------------
        # KỊCH BẢN 6: Tin nháp thiếu ảnh hoặc mô tả quá ngắn (Keep Draft)
        # -----------------------------------------------------------------
        short_draft = {
            "id": 206,
            "tieu_de": "Bán đất Sa Pa giá siêu rẻ",
            "slug": "ban-dat-sa-pa-gia-sieu-re",
            "gia": "1 tỷ",
            "gia_tri_so": 1000000000,
            "dien_tich": 100,
            "loai_bds": "land",
            "vi_tri": "Sa Pa, Lào Cai",
            "hinh_anh": [], # No image
            "mo_ta": "Mô tả siêu ngắn.", # Under 30 chars
            "trang_thai": "Bản nháp"
        }
        self.mock_db.bds_ban_data = [short_draft]

        actions_6 = auto_duplicate_guard.patrol_auto_publish_drafts(mode="safe-auto", dry_run=False)
        passed_6 = (len(actions_6) == 0)
        results.append((
            "Kịch bản 6: Thiếu ảnh hoặc mô tả quá ngắn",
            f"Actions size: {len(actions_6)} (Draft kept)",
            "ĐẠT" if passed_6 else "KHÔNG ĐẠT"
        ))

        # -----------------------------------------------------------------
        # KỊCH BẢN 7: Tin nháp thiếu diện tích hoặc diện tích <= 0 (Keep Draft)
        # -----------------------------------------------------------------
        zero_area_draft = {
            "id": 207,
            "tieu_de": "Bán đất Sa Pa vị trí trung tâm",
            "slug": "ban-dat-sa-pa-vi-tri-trung-tam",
            "gia": "2 tỷ",
            "gia_tri_so": 2000000000,
            "dien_tich": 0, # zero area
            "loai_bds": "land",
            "vi_tri": "Sa Pa, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/img.webp"],
            "mo_ta": "Cần bán mảnh đất thổ cư diện tích rộng thích hợp làm homestay hoặc biệt thự vườn...",
            "trang_thai": "Bản nháp"
        }
        self.mock_db.bds_ban_data = [zero_area_draft]

        actions_7 = auto_duplicate_guard.patrol_auto_publish_drafts(mode="safe-auto", dry_run=False)
        passed_7 = (len(actions_7) == 0)
        results.append((
            "Kịch bản 7: Thiếu diện tích hoặc diện tích <= 0",
            f"Actions size: {len(actions_7)} (Draft kept)",
            "ĐẠT" if passed_7 else "KHÔNG ĐẠT"
        ))

        # -----------------------------------------------------------------
        # KỊCH BẢN 8: Tin nháp thiếu giá (Keep Draft)
        # -----------------------------------------------------------------
        no_price_draft = {
            "id": 208,
            "tieu_de": "Bán đất Sa Pa trung tâm thị xã",
            "slug": "ban-dat-sa-pa-trung-tam-thi-xa",
            "gia": "", # empty price
            "gia_tri_so": None,
            "dien_tich": 120,
            "loai_bds": "land",
            "vi_tri": "Sa Pa, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/img.webp"],
            "mo_ta": "Cần bán mảnh đất thổ cư diện tích rộng thích hợp làm homestay hoặc biệt thự vườn...",
            "trang_thai": "Bản nháp"
        }
        self.mock_db.bds_ban_data = [no_price_draft]

        actions_8 = auto_duplicate_guard.patrol_auto_publish_drafts(mode="safe-auto", dry_run=False)
        passed_8 = (len(actions_8) == 0)
        results.append((
            "Kịch bản 8: Thiếu giá trị tiền (giá trống)",
            f"Actions size: {len(actions_8)} (Draft kept)",
            "ĐẠT" if passed_8 else "KHÔNG ĐẠT"
        ))

        # -----------------------------------------------------------------
        # KỊCH BẢN 9: Tin nháp có slug không hợp lệ (Keep Draft)
        # -----------------------------------------------------------------
        invalid_slug_draft = {
            "id": 209,
            "tieu_de": "Bán đất Sa Pa cực đẹp",
            "slug": "-ban-dat-sa-pa--cuc-dep-", # starting/ending with dash or containing double dashes
            "gia": "3 tỷ",
            "gia_tri_so": 3000000000,
            "dien_tich": 120,
            "loai_bds": "land",
            "vi_tri": "Sa Pa, Lào Cai",
            "hinh_anh": ["https://res.cloudinary.com/demo/image/upload/v1/sapa_bds/img.webp"],
            "mo_ta": "Cần bán mảnh đất thổ cư diện tích rộng thích hợp làm homestay hoặc biệt thự vườn...",
            "trang_thai": "Bản nháp"
        }
        self.mock_db.bds_ban_data = [invalid_slug_draft]

        actions_9 = auto_duplicate_guard.patrol_auto_publish_drafts(mode="safe-auto", dry_run=False)
        passed_9 = (len(actions_9) == 0)
        results.append((
            "Kịch bản 9: Slug không hợp lệ (dấu gạch nối lỗi)",
            f"Actions size: {len(actions_9)} (Draft kept)",
            "ĐẠT" if passed_9 else "KHÔNG ĐẠT"
        ))

        # Print the testing report in a gorgeous ASCII Table format
        print("\n" + "="*80)
        print("          🛡️ LAOCAIVIEW AUTO DUPLICATE GUARD SYSTEM - TEST SUITE REPORT 🛡️")
        print("="*80)
        print(f"{'Kịch Bản Kiểm Thử':<50} | {'Thông Tin Chi Tiết / Trạng Thái':<40} | {'Kết Quả':<10}")
        print("-"*108)
        for name, details, status in results:
            color = "🟢" if status == "ĐẠT" else "🔴"
            print(f"{name:<50} | {details:<40} | {color} {status}")
        print("="*80 + "\n")

if __name__ == "__main__":
    unittest.main()
