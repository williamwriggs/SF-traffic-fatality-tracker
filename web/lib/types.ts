export type RecordStatus = "official" | "provisional";

export interface FatalityRecord {
  record_id: string;
  collision_date: string;
  death_date: string | null;
  year: number;
  month: number;
  normalized_mode: string;
  native_victim_role: string | null;
  native_vehicle_type: string | null;
  record_status: RecordStatus;
  classification_status: string | null;
  latitude: number | null;
  longitude: number | null;
  location: string | null;
  neighborhood: string | null;
  supervisor_district: string | null;
  police_district: string | null;
  source_dataset: string | null;
  notes: string | null;
}

export interface TrackerStatus {
  refresh_ok: boolean;
  fetched_at: string;
  source_data_as_of: string;
  source_loaded_at: string;
  provisional_checked_through: string;
  official_records: number;
  open_provisional_records: number;
  snapshot: string;
  raw_snapshot: string;
  raw_manifest: string;
  revisions_detected: number;
  revision_log_rows: number;
}

export interface Revision {
  revision_id: string;
  observed_at: string;
  snapshot_from: string;
  snapshot_to: string;
  record_id: string;
  change_type: string;
  field: string;
  old_value: string;
  new_value: string;
}

export interface ProvisionalAudit {
  provisional_id: string;
  incident_date: string;
  death_date: string | null;
  mode_reported: string;
  normalized_mode: string;
  latitude: number | null;
  longitude: number | null;
  location: string;
  source_url: string;
  source_name: string;
  status: string;
  last_checked: string;
  matched_official_record_id: string | null;
  notes: string;
  possible_official_match: string | null;
}

export interface SnapshotManifest {
  name: string;
  file: string;
  records: number;
  collisionDateMax: string | null;
}

export type SnapshotRecord = Pick<
  FatalityRecord,
  | "record_id"
  | "collision_date"
  | "death_date"
  | "normalized_mode"
  | "native_victim_role"
  | "native_vehicle_type"
  | "latitude"
  | "longitude"
  | "location"
  | "neighborhood"
  | "supervisor_district"
  | "classification_status"
> & { native_party_type?: string | null };

export interface TrackerData {
  schemaVersion: number;
  status: TrackerStatus;
  records: FatalityRecord[];
  revisions: Revision[];
  provisionalAudit: ProvisionalAudit[];
  snapshots: SnapshotManifest[];
}

export interface SnapshotChange {
  record_id: string;
  change_type: string;
  field: string;
  old_value: string;
  new_value: string;
}
