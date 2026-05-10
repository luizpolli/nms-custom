/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        cisco: {
          blue: '#005073',
          'blue-light': '#00aeef',
          'blue-dark': '#003a54',
        },
        severity: {
          critical: '#dc2626',
          major: '#ea580c',
          minor: '#f59e0b',
          warning: '#eab308',
          info: '#3b82f6',
          clear: '#16a34a',
        },
      },
    },
  },
  plugins: [],
};
