import { Link } from 'react-router-dom';
import { Home } from 'lucide-react';

function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div className="text-6xl font-bold text-cisco-blue">404</div>
      <p className="text-lg text-gray-700 dark:text-gray-300">Page not found</p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 rounded-md bg-cisco-blue px-4 py-2 text-sm font-medium text-white hover:bg-cisco-blue-dark"
      >
        <Home className="h-4 w-4" />
        Back to Dashboard
      </Link>
    </div>
  );
}

export default NotFound;
