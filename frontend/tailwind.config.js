/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        'confidence-high': '#16A34A',
        'confidence-mid': '#EA580C',
        'confidence-low': '#DC2626',
        'pending': '#2563EB',
        'archived': '#6B7280',
        'surface': '#1F2937',
        'bg': '#111827',
      },
    },
  },
  plugins: [],
}
