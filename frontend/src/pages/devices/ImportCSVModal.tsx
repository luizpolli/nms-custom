import { useState, type ChangeEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Download, Upload } from 'lucide-react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { api } from '../../lib/api';

interface ImportCSVModalProps {
  open: boolean;
  onClose: () => void;
}

interface ParsedRow {
  name: string;
  host: string;
  vendor: string;
  user: string;
  password: string;
  model?: string;
  site?: string;
  tags: string[];
}

interface RowState {
  index: number;
  raw: Record<string, string>;
  parsed?: ParsedRow;
  error?: string;
}

interface BulkResponse {
  created: number;
  failed: { row: number; name: string; error: string }[];
}

const REQUIRED = ['name', 'host', 'vendor', 'user', 'password'] as const;
const ALLOWED_VENDORS = ['cisco', 'juniper', 'huawei', 'nokia', 'arista', 'other'];

const TEMPLATE_CSV =
  'name,host,vendor,model,user,password,site,tags\n' +
  'MXCMXM01RTDCLFENT11,10.224.18.14,cisco,NCS55A1,CERT_EPNM,MySuperSecretPwd,CMX-DC,core;production\n' +
  'OTRONCS55A1,10.224.18.15,cisco,ASR920,CERT_EPNM,MySuperSecretPwd,CMX-DC,edge\n';

function parseCSVLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      out.push(cur);
      cur = '';
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

function parseCSV(text: string): RowState[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) return [];
  const headers = parseCSVLine(lines[0]).map((h) => h.toLowerCase());

  return lines.slice(1).map((line, i) => {
    const cells = parseCSVLine(line);
    const raw: Record<string, string> = {};
    headers.forEach((h, idx) => {
      raw[h] = cells[idx] ?? '';
    });

    const missing = REQUIRED.filter((k) => !raw[k]);
    if (missing.length > 0) {
      return { index: i, raw, error: `missing required: ${missing.join(', ')}` };
    }

    const vendor = raw.vendor.toLowerCase();
    if (!ALLOWED_VENDORS.includes(vendor)) {
      return { index: i, raw, error: `invalid vendor "${raw.vendor}" (allowed: ${ALLOWED_VENDORS.join(', ')})` };
    }

    const tags = raw.tags ? raw.tags.split(';').map((t) => t.trim()).filter(Boolean) : [];

    return {
      index: i,
      raw,
      parsed: {
        name: raw.name,
        host: raw.host,
        vendor,
        user: raw.user,
        password: raw.password,
        model: raw.model || undefined,
        site: raw.site || undefined,
        tags,
      },
    };
  });
}

export function ImportCSVModal({ open, onClose }: ImportCSVModalProps) {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<RowState[]>([]);
  const [fileName, setFileName] = useState('');
  const [result, setResult] = useState<BulkResponse | null>(null);

  const reset = () => {
    setRows([]);
    setFileName('');
    setResult(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setResult(null);
    const text = await file.text();
    setRows(parseCSV(text));
  };

  const downloadTemplate = () => {
    const blob = new Blob([TEMPLATE_CSV], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'devices_template.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = { rows: rows.filter((r) => r.parsed).map((r) => r.parsed!) };
      const res = await api.post<BulkResponse>('/devices/bulk', payload);
      return res.data;
    },
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });

  const validCount = rows.filter((r) => r.parsed).length;
  const invalidCount = rows.length - validCount;

  return (
    <Modal open={open} onClose={handleClose} title="Import devices from CSV" size="3xl">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={downloadTemplate}>
            <Download className="w-4 h-4 mr-1" /> Download template
          </Button>
          <label className="inline-flex items-center gap-2 cursor-pointer rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-800">
            <Upload className="w-4 h-4" />
            <span>Select CSV file</span>
            <input type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} />
          </label>
          {fileName && <span className="text-sm text-gray-600 dark:text-gray-400">{fileName}</span>}
        </div>

        <p className="text-xs text-gray-500">
          Required columns: <code>name, host, vendor, user, password</code>. Optional: <code>model, site, tags</code> (semicolon-separated).
          Allowed vendors: {ALLOWED_VENDORS.join(', ')}.
        </p>

        {rows.length > 0 && !result && (
          <>
            <div className="flex gap-4 text-sm">
              <span className="text-green-600">Valid: {validCount}</span>
              <span className="text-red-600">Invalid: {invalidCount}</span>
            </div>
            <div className="max-h-80 overflow-auto border border-gray-200 rounded-md dark:border-gray-700">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
                  <tr>
                    <th className="px-2 py-1 text-left">#</th>
                    <th className="px-2 py-1 text-left">Name</th>
                    <th className="px-2 py-1 text-left">Host</th>
                    <th className="px-2 py-1 text-left">Vendor</th>
                    <th className="px-2 py-1 text-left">Model</th>
                    <th className="px-2 py-1 text-left">User</th>
                    <th className="px-2 py-1 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={r.index}
                      className={r.error ? 'bg-red-50 dark:bg-red-900/20' : ''}
                    >
                      <td className="px-2 py-1">{r.index + 2}</td>
                      <td className="px-2 py-1">{r.raw.name}</td>
                      <td className="px-2 py-1">{r.raw.host}</td>
                      <td className="px-2 py-1">{r.raw.vendor}</td>
                      <td className="px-2 py-1">{r.raw.model}</td>
                      <td className="px-2 py-1">{r.raw.user}</td>
                      <td className="px-2 py-1 text-xs">
                        {r.error ? <span className="text-red-600">{r.error}</span> : <span className="text-green-600">OK</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {result && (
          <div className="space-y-2">
            <p className="text-sm">
              <span className="text-green-600 font-medium">{result.created} devices created.</span>{' '}
              {result.failed.length > 0 && (
                <span className="text-red-600 font-medium">{result.failed.length} failed.</span>
              )}
            </p>
            {result.failed.length > 0 && (
              <div className="max-h-60 overflow-auto border border-red-200 rounded-md p-2 text-sm dark:border-red-900">
                <ul className="space-y-1">
                  {result.failed.map((f) => (
                    <li key={f.row} className="text-red-700 dark:text-red-400">
                      Row {f.row + 2} ({f.name}): {f.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {mutation.isError && (
          <p className="text-sm text-red-600">Import request failed. Check the console for details.</p>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
          <Button variant="ghost" onClick={handleClose}>
            {result ? 'Close' : 'Cancel'}
          </Button>
          {!result && (
            <Button
              onClick={() => mutation.mutate()}
              disabled={validCount === 0 || mutation.isPending}
            >
              {mutation.isPending ? 'Importing…' : `Import ${validCount} devices`}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
