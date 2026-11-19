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
  directions?: string | null; location: string | null; latitude: number | null; longitude: number | null; occurred_at: string | null;
  match_count: number; timeline: Timeline | null; claim_status: string | null;
}
export interface MyReports { lost: Report[]; found: Report[] }
export interface ReportCreated { message: string; report_code: string; matches_created: number; custody_status: string | null }

export interface Collection {
  name: string | null; address: string | null; latitude: number | null; longitude: number | null;
  instructions: string | null; maps_url: string | null; osm_url: string | null; set_at: string | null;
}
export interface Claim {
  id: number; match_id: number; status: string; proof: string | null; claim_features: string | null; claim_notes: string | null;
  created_at: string; verified_at: string | null; completed_at: string | null; handed_over_at: string | null;
  staff_message: string | null; rejection_reason: string | null; evidence_count: number; collection: Collection | null;
}
export interface Evidence { id: number; note: string | null; has_image: boolean; created_at: string; added_by: string | null }
export interface ClaimEvent {
  id: number; action: string; from_status: string | null; to_status: string | null; note: string | null;
  internal: boolean; actor_name: string; actor_role: string; created_at: string;
}
export interface ClaimDetail extends Claim { lost_report: Report; found: FoundCandidate; evidence: Evidence[]; events: ClaimEvent[] }
export interface ClaimInput { proof?: string; distinguishing_features?: string; additional_info?: string }
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
  owner: Party; finder: Party; handed_over_at: string | null; staff_message: string | null;
  rejection_reason: string | null; evidence_count: number; claim_features: string | null; claim_notes: string | null;
}
export interface Signal { key: string; label: string; value: number | null; weight_note: string }
export interface CaseDetail extends RecoveryCase {
  claimant: { name: string; email: string; role: string; account_created_at: string; lost_reports: number;
    found_reports: number; claims_total: number; claims_completed: number; claims_rejected: number };
  match: { fusion_score: number | null; signals: Signal[]; explanation: string; distance_m: number | null };
  found_directions: string | null; evidence: Evidence[]; events: ClaimEvent[]; collection: Collection | null;
  handed_over_by: string | null; allowed_actions: string[];
}
export interface StaffSummary {
  claims_to_verify: number; verified_awaiting_handover: number; deposits_to_confirm: number;
  finders_holding_items: number; active_lost: number; active_found: number; users: number;
  total_lost: number; total_found: number; pending_requests: number; under_review: number; evidence_requested: number;
  approved_claims: number; rejected_claims: number; completed_recoveries: number;
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
  generated_at: string | null; range_days: number;
  funnel: { stage: string; count: number; share: number | null }[];
  decision_rate: { approved?: number; rejected?: number; cancelled?: number; approval_rate?: number | null };
  review_times: { avg_hours_to_first_response?: number | null; waiting_for_review?: number; oldest_waiting_hours?: number | null };
  match_quality: { avg_score?: number | null; high_confidence?: number; high_confidence_share?: number | null; dismissed?: number; claim_conversion?: number | null };
  evidence_stats: { claims_with_evidence?: number; share_with_evidence?: number | null; evidence_requested?: number };
  report_status: { lost: Record<string, number>; found: Record<string, number> };
  custody: Record<string, number>; top_locations: { place: string; count: number }[];
  weekday: { label: string; count: number }[]; hours: { label: string; count: number }[];
  staff_workload: { staff: string; actions: number }[]; open_aging: Record<string, number>;
}

export interface ApiErrorBody { error: { code: string; message: string; details?: { field: string; message: string }[] } }

export interface ActivityItem { at: string; kind: "lost" | "found" | "claim" | "staff"; title: string; code: string; detail: string; actor: string }
export interface Hotspot { place: string; lost: number; found: number; total: number; recovered: number; lat: number | null; lng: number | null; map_url: string | null }
export interface AttentionItem { kind: string; severity: "high" | "medium" | "low"; title: string; code: string; detail: string; age_hours: number; claim_id: number | null }
export interface Attention { rules: Record<string, number>; counts: Record<string, number>; items: AttentionItem[] }
export interface Community {
  top_finders: { name: string; reported: number; returned: number }[]; top_owners: { name: string; reported: number; recovered: number }[];
  members: number; returned_total: number;
}
export interface Profile {
  user: { id: number; name: string; email: string; role: string; member_since: string };
  lost: { total: number; active: number; recovered: number };
  found: { total: number; active: number; returned: number; with_staff: number };
  matches: { total: number; best_score: number | null; strong: number; dismissed: number };
  claims: { total: number; by_status: Record<string, number> };
  recovery_rate: number | null; avg_hours_to_recover: number | null;
  categories: { category: string; count: number }[]; unread_notifications: number;
  timeline: { at: string; kind: string; title: string; detail: string }[];
}