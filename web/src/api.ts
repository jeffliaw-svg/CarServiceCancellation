import type { CaseView, OperatorOverview } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "";

async function request<T>(
  path: string,
  init?: RequestInit,
  token?: string | null,
  operatorKey?: string | null,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) || {}),
  };
  if (token) headers["X-Case-Token"] = token;
  if (operatorKey) headers["X-Operator-Key"] = operatorKey;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
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
  createCase: (intake: Intake, accessCode?: string) =>
    request<CaseView>("/api/cases", {
      method: "POST",
      body: JSON.stringify(intake),
      headers: accessCode ? { "X-Access-Code": accessCode } : undefined,
    }),

  getCase: (id: string, token: string | null) =>
    request<CaseView>(`/api/cases/${id}`, undefined, token),

  uploadFile: async (
    id: string,
    token: string | null,
    file: File,
    kind: string,
  ) =>
    request<CaseView>(
      `/api/cases/${id}/documents`,
      {
        method: "POST",
        body: JSON.stringify({
          filename: file.name,
          kind,
          content_base64: await fileToBase64(file),
        }),
      },
      token,
    ),

  uploadText: (id: string, token: string | null, text: string, kind: string) =>
    request<CaseView>(
      `/api/cases/${id}/documents`,
      {
        method: "POST",
        body: JSON.stringify({
          filename: "contract.txt",
          kind,
          content_base64: textToBase64(text),
        }),
      },
      token,
    ),

  confirm: (id: string, token: string | null, keep: number[]) =>
    request<CaseView>(
      `/api/cases/${id}/confirm`,
      { method: "POST", body: JSON.stringify({ keep }) },
      token,
    ),

  generate: (id: string, token: string | null) =>
    request<CaseView>(
      `/api/cases/${id}/generate`,
      { method: "POST" },
      token,
    ),

  fileUrl: (id: string, name: string, token: string | null) => {
    const query = token ? `?token=${encodeURIComponent(token)}` : "";
    return `${BASE}/api/cases/${id}/files/${name}${query}`;
  },

  operatorOverview: (operatorKey: string) =>
    request<OperatorOverview>(
      "/api/operator/overview",
      undefined,
      undefined,
      operatorKey,
    ),

  operatorCase: (id: string, operatorKey: string) =>
    request<CaseView>(
      `/api/operator/cases/${id}`,
      undefined,
      undefined,
      operatorKey,
    ),
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
