import { AppRouter } from './router';
import { ToastContainer } from './components/ui';
import { DemoBanner } from './demo/DemoBanner';

export function App() {
  return (
    <>
      <DemoBanner />
      <AppRouter />
      <ToastContainer />
    </>
  );
}
