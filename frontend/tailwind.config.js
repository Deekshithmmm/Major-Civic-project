/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0f2e2b',
        civic: {
          50: '#eef6f5',
          100: '#d6eae7',
          200: '#aed6d0',
          300: '#7bbab1',
          400: '#4a9a8f',
          500: '#2b7d72',
          600: '#166058',
          700: '#114a44',
          800: '#0d3a35',
          900: '#0a2c29',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Noto Sans',
          'Noto Sans Devanagari',
          'Noto Sans Kannada',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 46, 43, 0.06), 0 1px 3px rgba(15, 46, 43, 0.04)',
        lift: '0 4px 12px rgba(15, 46, 43, 0.10)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'fade-in': 'fade-in 200ms ease-out both',
      },
    },
  },
  plugins: [],
}
