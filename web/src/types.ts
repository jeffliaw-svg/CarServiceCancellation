export interface Estimate {
  can_estimate: boolean;
  net_refund: number;
  gross_refund: number;
  basis: string;
}

export interface Product {
  index: number;
  product_type: string;
  administrator: string;
  contract_number: string;
  price: number;
  term_months: number | null;
  term_miles: number | null;
  estimate: Estimate;
  headline: string;
  detail: string;
  review_fields: string[];
}

export interface RuleNote {
  topic: string;
  rule: string;
  source: string;
  reviewed_on: string;
}

export interface GeneratedFile {
  name: string;
  kind: string;
  description: string;
  download_url: string;
}

export interface DocumentFile {
  name: string;
  original_name: string;
  kind: string;
  size: number;
  download_url: string;
}

export interface FunnelStage {
  stage: string;
  reached: number;
  stalled_here: number;
}

export interface OperatorTotals {
  started: number;
  documents_read: number;
  services_confirmed: number;
  letters_generated: number;
  packets_generated: number;
  needs_review: number;
}

export interface OperatorRow {
  case_id: string;
  seller: string;
  vehicle: string;
  vin: string;
  stage: string;
  stage_num: number;
  products: number;
  estimated_total: number;
  review: Record<string, string[]>;
  packets: number;
  created_at: string;
  updated_at: string;
}

export interface ReviewItem {
  case_id: string;
  seller: string;
  stage: string;
  review: Record<string, string[]>;
  created_at: string;
  updated_at: string;
}

export interface OperatorOverview {
  generated_at: string;
  totals: OperatorTotals;
  funnel: FunnelStage[];
  needs_review: ReviewItem[];
  recent: OperatorRow[];
}

export interface Candidate {
  value: string | number;
  sources: string[];
}

export interface CaseView {
  case_id: string;
  // Returned only by createCase; the client keeps it to authorize
  // every later request for this case.
  access_token?: string;
  status: string;
  seller: {
    legal_name: string;
    address_lines: string[];
    email: string;
    phone: string;
  };
  vehicle: {
    vin: string;
    description: string;
    purchase_date: string | null;
  };
  sale_date: string;
  created_at: string;
  updated_at: string;
  products: Product[];
  total_estimated_refund: number;
  parse_warnings: string[];
  extraction_method: string;
  review_detail: Record<string, Record<string, Candidate[]>>;
  resolution: { resolved_at: string; fields_corrected: number } | null;
  rules_notes: RuleNote[];
  documents: DocumentFile[];
  generated: GeneratedFile[];
}

export interface Correction {
  product_type: string;
  field: string;
  value: string | number;
}
