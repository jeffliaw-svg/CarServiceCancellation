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
  question: string;
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
  documents: DocumentFile[];
  generated: GeneratedFile[];
}
