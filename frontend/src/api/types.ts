export interface User { id: number; name: string; email: string; role: string }
export interface TokenResponse { access_token: string; token_type: string; user: User }

export interface Report {
  id: number; report_code: string; item_name: string; category: string; description: string | null;
  status: string; created_at: string; has_image: boolean; custody_status: string | null;
}
export interface MyReports { lost: Report[]; found: Report[] }
export interface ReportCreated { message: string; report_code: string; matches_created: number; custody_status: string | null }

export interface Match {
  id: number; lost_report: Report; found_item_name: string; found_category: string;
  fusion_score: number | null; image_similarity: number | null; text_similarity: number | null;
  location_similarity: number | null; rank: number | null; interest_status: string | null;
}
export interface RecoveryRequest { id: number; match_id: number; status: string }
export interface Notification { id: number; title: string; message: string; is_read: boolean; related_report_id: number | null; created_at: string }
export interface PendingDeposit { id: number; report_code: string; item_name: string; category: string; custody_status: string; created_at: string }

export interface ApiErrorBody { error: { code: string; message: string; details?: { field: string; message: string }[] } }
