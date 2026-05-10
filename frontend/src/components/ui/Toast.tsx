import { useEffect, useState } from 'react';
import { X, AlertCircle, CheckCircle } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

interface ToastMessage {
  id: string;
  type: 'error' | 'success' | 'info';
  message: string;
}

let toastCounter = 0;
const listeners: Array<(msg: ToastMessage) => void> = [];

export function pushToast(message: string, type: ToastMessage['type'] = 'info') {
  const msg: ToastMessage = { id: String(++toastCounter), type, message };
  listeners.forEach((l) => l(msg));
}

const typeClasses: Record<ToastMessage['type'], string> = {
  error: 'bg-severity-critical text-white',
  success: 'bg-severity-clear text-white',
  info: 'bg-cisco-blue text-white',
};

const TypeIcon = ({ type }: { type: ToastMessage['type'] }) => {
  if (type === 'error') return <AlertCircle className="h-5 w-5 shrink-0" />;
  if (type === 'success') return <CheckCircle className="h-5 w-5 shrink-0" />;
  return <AlertCircle className="h-5 w-5 shrink-0" />;
};

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    const add = (msg: ToastMessage) => {
      setToasts((prev) => [...prev, msg]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== msg.id));
      }, 5_000);
    };
    listeners.push(add);

    // Listen to api-error events from api.ts interceptor
    const handler = (e: Event) => {
      pushToast((e as CustomEvent<string>).detail, 'error');
    };
    window.addEventListener('api-error', handler);

    return () => {
      listeners.splice(listeners.indexOf(add), 1);
      window.removeEventListener('api-error', handler);
    };
  }, []);

  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={twMerge(
            'flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg text-sm max-w-sm',
            typeClasses[t.type],
          )}
        >
          <TypeIcon type={t.type} />
          <span className="flex-1">{t.message}</span>
          <button
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            aria-label="Cerrar"
            className="ml-2 opacity-80 hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
