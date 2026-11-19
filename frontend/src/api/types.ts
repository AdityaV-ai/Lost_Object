export interface User { id: number; name: string; email: string; role: string }
export interface TokenResponse { access_token: string; token_type: string; user: User }

export interface Timeline {
  submitted_at: string; first_match_at: string | null; claimed_at: string | null;
  verified_at: string | null; completed_at: string | null; current_step: number;
}
export interface Report {
  id: number; report_code: string; item_name: string; category: string; description: string | null;
  status: string; created_at: string; has_image: boolean; custody_status: string | null;
  colour: string | null; brand: string | null; model: string | null; distinguishing_features: string | null;
  location: string | null; latitude: number | null; longitude: number | null; occurred_at: string | null;
  match_count: number; timeline: Timeline | null; claim_status: string | null;
}
export interface MyReports { lost: Report[]; found: Report[] }
export interface ReportCreated { message: string; report_code: string; matches_created: number; custody_status: string | null }

export interface Claim { id: number; match_id: number; status: string; proof: string | null; created_at: string; verified_at: string | null; completed_at: string | null }
export interface FoundCandidate {
  item_name: string; category: string; description: string | null; colour: string | null;
  distinguishing_features: string | null; location: string | null; latitude: number | null; longitude: number | null;
  custody_status: string; reported_at: string; occurred_at: string | null; has_image: boolean;
}
export interface Match {
  id: number; lost_report: Report; found: FoundCandidate; found_item_name: string; found_category: string;
  fusion_score: number | null; label: string; image_similarity: number | null; words_photo_similarity: number | null;
  text_similarity: number | null; location_similarity: number | null; distance_m: number | null;
  rank: number | null; dismissed: boolean; interest_status: string | null; claim: Claim | null; created_at: string;
}
export interface Notification { id: number; title: string; message: string; is_read: boolean; related_report_id: number | null; match_id: number | null; created_at: string }

export interface Party { name: string; email: string }
export interface PendingDeposit {
  id: number; report_code: string; item_name: string; category: string; description: string | null;
  custody_status: string; created_at: string; has_image: boolean; location: string | null; finder: Party; match_count: number;
}
export interface RecoveryCase {
  id: number; status: string; proof: string | null; created_at: string; verified_at: string | null; completed_at: string | null;
  match_id: number; fusion_score: number | null; lost_report: Report; found_report: Report; found_location: string | null;
  owner: Party; finder: Party;
}
export interface StaffSummary {
  claims_to_verify: number; verified_awaiting_handover: number; deposits_to_confirm: number;
  finders_holding_items: number; active_lost: number; active_found: number; users: number;
}
export interface MatchRow {
  id: number; created_at: string; lost_code: string; lost_name: string; found_code: string; found_name: string;
  image_similarity: number | null; words_photo_similarity: number | null; text_similarity: number | null;
  location_similarity: number | null; fusion_score: number | null; dismissed: boolean; claim_status: string | null;
}
export interface PersonRow { id: number; name: string; email: string; role: string; created_at: string; lost_count: number; found_count: number }
export interface ReportRow {
  kind: string; id: number; report_code: string; item_name: string; category: string; status: string;
  custody_status: string | null; owner: Party; created_at: string; match_count: number; has_image: boolean;
}
export interface StaffAction { id: number; created_at: string; staff_name: string; action: string; target_type: string; code: string | null; detail: string | null }
export interface Analytics {
  totals: Record<string, number>; recovery_rate: number | null; avg_hours_to_complete: number | null;
  claims_by_status: Record<string, number>; reports_by_category: { category: string; lost: number; found: number }[];
  matches_by_score_band: Record<string, number>; reports_per_day: { date: string; lost: number; found: number }[];
}

export interface ApiErrorBody { error: { code: string; message: string; details?: { field: string; message: string }[] } }
