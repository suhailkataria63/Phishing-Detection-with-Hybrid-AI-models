import { BatchInputRow } from "@/lib/types";

function parseCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];

    if (ch === '"') {
      const next = line[i + 1];
      if (inQuotes && next === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (ch === "," && !inQuotes) {
      values.push(current.trim());
      current = "";
      continue;
    }

    current += ch;
  }

  values.push(current.trim());
  return values;
}

function normalizeKey(raw: string): string {
  return raw.trim().toLowerCase().replace(/\s+/g, "_");
}

export function parseCsvToRows(csvText: string): BatchInputRow[] {
  const lines = csvText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length < 2) return [];

  const headers = parseCsvLine(lines[0]).map(normalizeKey);
  const rows: BatchInputRow[] = [];

  for (let i = 1; i < lines.length; i += 1) {
    const cols = parseCsvLine(lines[i]);
    const raw: Record<string, string> = {};
    headers.forEach((header, idx) => {
      raw[header] = cols[idx] ?? "";
    });

    const caseId = raw.case_id || raw.id || `row-${i}`;
    const urlsRaw = raw.urls || raw.url_list || raw.links || "";
    const urlSingle = raw.url || raw.link || "";

    rows.push({
      rowIndex: i,
      caseId,
      subject: raw.subject || "",
      body: raw.body || raw.email_body || raw.message || "",
      sender: raw.sender || raw.sender_name || raw.from || "",
      urlsRaw,
      urlSingle,
      expectedLabel: raw.expected_joint_label || raw.expected_label || "",
      raw,
    });
  }

  return rows;
}

export function exportRowsToCsv(headers: string[], rows: string[][]): string {
  const escape = (value: string) => {
    if (/[",\n]/.test(value)) return `"${value.replaceAll('"', '""')}"`;
    return value;
  };

  const body = rows.map((row) => row.map((cell) => escape(cell)).join(",")).join("\n");
  return `${headers.join(",")}\n${body}`;
}
