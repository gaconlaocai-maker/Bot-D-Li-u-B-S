-- =========================================================================
--      🛡️ LAOCAIVIEW AUTO DUPLICATE GUARD SYSTEM - SQL MIGRATION SCHEMA 🛡️
-- =========================================================================
-- Hướng dẫn: Copy và Paste toàn bộ nội dung file này vào Supabase SQL Editor
-- rồi bấm nút RUN để kích hoạt hệ thống Auto Duplicate Guard!
-- =========================================================================

-- 1. Bổ sung các cột metadata bảo vệ trùng lặp cho bảng chính 'bds_ban'
ALTER TABLE bds_ban ADD COLUMN IF NOT EXISTS duplicate_score NUMERIC DEFAULT 0;
ALTER TABLE bds_ban ADD COLUMN IF NOT EXISTS duplicate_warning BOOLEAN DEFAULT FALSE;
ALTER TABLE bds_ban ADD COLUMN IF NOT EXISTS duplicate_review BOOLEAN DEFAULT FALSE;
ALTER TABLE bds_ban ADD COLUMN IF NOT EXISTS possible_duplicate_of INTEGER REFERENCES bds_ban(id) ON DELETE SET NULL;
ALTER TABLE bds_ban ADD COLUMN IF NOT EXISTS duplicate_checked_at TIMESTAMPTZ;
ALTER TABLE bds_ban ADD COLUMN IF NOT EXISTS duplicate_status TEXT DEFAULT 'clean';

-- Tạo index để tăng tốc độ truy vấn lọc tin và so khớp
CREATE INDEX IF NOT EXISTS idx_bds_ban_duplicate_status ON bds_ban(duplicate_status);
CREATE INDEX IF NOT EXISTS idx_bds_ban_trang_thai ON bds_ban(trang_thai);

-- 2. Tạo bảng nhật ký hành động tự động của Bot 'bds_bot_actions'
CREATE TABLE IF NOT EXISTS bds_bot_actions (
    id BIGSERIAL PRIMARY KEY,
    action_type TEXT NOT NULL,                     -- 'auto_block_duplicate', 'auto_hide_duplicate', 'auto_publish', 'warning'
    primary_id INTEGER REFERENCES bds_ban(id) ON DELETE SET NULL,   -- ID tin chính giữ lại
    duplicate_id INTEGER REFERENCES bds_ban(id) ON DELETE SET NULL, -- ID tin phụ bị ẩn/chặn
    duplicate_score NUMERIC,                        -- Điểm trùng lặp
    reason TEXT,                                    -- Lý do chi tiết và breakdown điểm
    old_status TEXT,                                -- Trạng thái cũ (vd: Mở bán, Bản nháp)
    new_status TEXT,                                -- Trạng thái mới sau khi xử lý (vd: Ẩn, Bản nháp)
    old_slug TEXT,                                  -- Slug tin phụ
    redirect_to_slug TEXT,                          -- Slug tin chính redirect tới
    backup_json JSONB,                              -- Bản lưu trữ dữ liệu gốc phòng hờ rollback
    rollback_status TEXT DEFAULT 'active',         -- 'active', 'rollbacked'
    resolved_at TIMESTAMPTZ,                        -- Thời điểm rollback hoàn tất
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Thêm index cho bảng bds_bot_actions
CREATE INDEX IF NOT EXISTS idx_bds_bot_actions_type ON bds_bot_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_bds_bot_actions_dup ON bds_bot_actions(duplicate_id);

-- 3. Tạo bảng duyệt trùng lặp thủ công cho Admin 'bds_duplicate_reviews'
CREATE TABLE IF NOT EXISTS bds_duplicate_reviews (
    id BIGSERIAL PRIMARY KEY,
    duplicate_id INTEGER REFERENCES bds_ban(id) ON DELETE CASCADE,  -- ID tin trùng nghi vấn
    possible_duplicate_of INTEGER REFERENCES bds_ban(id) ON DELETE CASCADE, -- ID tin đối chiếu
    duplicate_score NUMERIC,                        -- Điểm trùng lặp
    duplicate_reason TEXT,                          -- Lý do nghi trùng
    status TEXT DEFAULT 'warning',                  -- 'warning' (chờ duyệt), 'approved' (đồng ý trùng), 'rejected' (tin sạch), 'auto_resolved'
    resolved_by TEXT,                               -- Người xử lý (admin/bot)
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bds_dup_reviews_status ON bds_duplicate_reviews(status);

-- 4. Bật Row Level Security (RLS) an toàn
ALTER TABLE bds_bot_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bds_duplicate_reviews ENABLE ROW LEVEL SECURITY;

-- Tạo chính sách cho phép Service Role truy cập toàn quyền bypass RLS
CREATE POLICY "Allow service_role full access on bot_actions" 
ON bds_bot_actions 
FOR ALL 
TO service_role 
USING (true) 
WITH CHECK (true);

CREATE POLICY "Allow service_role full access on duplicate_reviews" 
ON bds_duplicate_reviews 
FOR ALL 
TO service_role 
USING (true) 
WITH CHECK (true);

-- Báo cáo kích hoạt thành công
SELECT 'Hệ thống Auto Duplicate Guard đã sẵn sàng hoạt động!' as status;
