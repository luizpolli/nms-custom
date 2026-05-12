import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';

const httpsEnabled = process.env.HTTPS_ENABLED === 'true';
const certFile = process.env.TLS_CERT_FILE || '/certs/server.crt';
const keyFile = process.env.TLS_KEY_FILE || '/certs/server.key';
const apiTarget = process.env.VITE_API_TARGET || (httpsEnabled ? 'https://app:8000' : 'http://app:8000');
const wsTarget = process.env.VITE_WS_TARGET || (httpsEnabled ? 'wss://app:8000' : 'ws://app:8000');

const https = httpsEnabled && fs.existsSync(certFile) && fs.existsSync(keyFile)
  ? { cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile) }
  : undefined;

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    https,
    proxy: {
      '/api/alarms/ws': {
        target: wsTarget,
        ws: true,
        changeOrigin: true,
        secure: false,
      },
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
      '/health': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
