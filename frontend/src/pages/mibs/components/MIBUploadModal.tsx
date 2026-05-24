import React, { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../../lib/api';

interface Props {
  onClose: () => void;
  onUploaded: () => void;
}

const ACCEPTED = '.mib,.my,.txt';

export function MIBUploadModal({ onClose, onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData();
      form.append('file', f);
      return api.post('/mibs/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) setProgress(Math.round((e.loaded / e.total) * 100));
        },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mibs'] });
      onUploaded();
    },
  });

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  };

  const handleSubmit = () => {
    if (file) mutate(file);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Upload MIB</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none">&times;</button>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
            dragOver
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
              : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            className="hidden"
            onChange={(e) => { if (e.target.files?.[0]) setFile(e.target.files[0]); }}
          />
          {file ? (
            <p className="text-sm text-gray-700 dark:text-gray-200 font-medium">{file.name}</p>
          ) : (
            <>
              <p className="text-sm text-gray-500 dark:text-gray-400">Drag a file here or click</p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Formats: .mib, .my, .txt</p>
            </>
          )}
        </div>

        {isPending && (
          <div className="mt-3">
            <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className="h-2 rounded-full bg-blue-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 text-right">{progress}%</p>
          </div>
        )}

        {isError && (
          <p className="mt-2 text-xs text-red-500">
            {error instanceof Error ? error.message : 'Failed to upload file'}
          </p>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!file || isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {isPending ? 'Uploading...' : 'Upload MIB'}
          </button>
        </div>
      </div>
    </div>
  );
}
