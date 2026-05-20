import type { CaseView } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const data = await res.json().catch(() => ({}) as unknown);
  if (!res.ok) {
    const message =
      (data as { error?: string }).error || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data as T;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = () => reject(new Error("Could not read that file."));
    reader.readAsDataURL(file);
  });
}

function textToBase64(text: string): string {
  return btoa(unescape(encodeURIComponent(text)));
}

export interface Intake {
  legal_name: string;
  address_lines: string[];
  email: string;
  phone: string;
  vin: string;
  sale_date: string;
}

export const api = {
  createCase: (intake: Intake) =>
    request<CaseView>("/api/cases", {
      method: "POST",
      body: JSON.stringify(intake),
    }),

  getCase: (id: string) => request<CaseView>(`/api/cases/${id}`),

  uploadFile: async (id: string, file: File, kind: string) =>
    request<CaseView>(`/api/cases/${id}/documents`, {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        kind,
        content_base64: await fileToBase64(file),
      }),
    }),

  uploadText: (id: string, text: string, kind: string) =>
    request<CaseView>(`/api/cases/${id}/documents`, {
      method: "POST",
      body: JSON.stringify({
        filename: "contract.txt",
        kind,
        content_base64: textToBase64(text),
      }),
    }),

  confirm: (id: string, keep: number[]) =>
    request<CaseView>(`/api/cases/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ keep }),
    }),

  generate: (id: string) =>
    request<CaseView>(`/api/cases/${id}/generate`, { method: "POST" }),

  fileUrl: (id: string, name: string) =>
    `${BASE}/api/cases/${id}/files/${name}`,
};

export function money(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function moneyExact(value: number): string {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD" });
}
