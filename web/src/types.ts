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
  products: Product[];
  total_estimated_refund: number;
  parse_warnings: string[];
  extraction_method: string;
  documents: DocumentFile[];
  generated: GeneratedFile[];
}
