export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function extractFilename(
  disposition: string | null,
  fallbackName: string,
  ext: string
): string {
  if (disposition) {
    const match = /filename[^;=\n]*=(['"]?)([^'";\n]+)\1/i.exec(disposition);
    if (match?.[2]) return match[2].trim();
  }
  return `${fallbackName}-${Date.now()}.${ext}`;
}

export function formatExtFromFormat(format: string): string {
  return format.toLowerCase() === 'pdf' ? 'pdf' : 'xlsx';
}
