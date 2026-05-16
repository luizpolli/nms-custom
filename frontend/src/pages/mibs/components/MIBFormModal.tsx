import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { clsx } from 'clsx';

export interface MIB {
  id?: string;
  name: string;
  oid_root: string;
  description: string;
  status: 'active' | 'inactive';
}

interface Props {
  mib?: MIB;
  onClose: () => void;
  onSaved: () => void;
}

const EMPTY: MIB = { name: '', oid_root: '', description: '', status: 'active' };

export function MIBFormModal({ mib, onClose, onSaved }: Props) {
  const [form, setForm] = useState<MIB>(mib ?? EMPTY);
  const qc = useQueryClient();
  const isEdit = !!mib?.id;

  useEffect(() => { setForm(mib ?? EMPTY); }, [mib]);

  const set = (key: keyof MIB) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: () =>
      isEdit
        ? axios.patch(`/api/mibs/${mib!.id}`, form)
        : axios.post('/api/mibs', form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mibs'] });
      onSaved();
    },
  });

  const fieldClass = 'w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            {isEdit ? 'Edit MIB' : 'New MIB'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none">&times;</button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Name *</label>
            <input value={form.name} onChange={set('name')} className={fieldClass} placeholder="IF-MIB" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Root OID *</label>
            <input value={form.oid_root} onChange={set('oid_root')} className={fieldClass} placeholder="1.3.6.1.2.1.2" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={set('description')}
              rows={3}
              className={clsx(fieldClass, 'resize-none')}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Status</label>
            <select value={form.status} onChange={set('status')} className={fieldClass}>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        {isError && (
          <p className="mt-2 text-xs text-red-500">
            {error instanceof Error ? error.message : 'Failed to save'}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            onClick={() => mutate()}
            disabled={!form.name || !form.oid_root || isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
