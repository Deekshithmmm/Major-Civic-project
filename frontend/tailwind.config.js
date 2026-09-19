/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0f2e2b',
        civic: {
          50: '#eef6f5',
          600: '#166058',
          700: '#114a44',
        },
      },
    },
  },
  plugins: [],
}
