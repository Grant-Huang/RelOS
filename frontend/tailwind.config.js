/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#f5f5f3',
        bg2: '#eeede9',
        card: '#ffffff',
        t1: '#1a1a1a',
        t2: '#5f5e5a',
        t3: '#888780',
        blue: { DEFAULT: '#185FA5', light: '#E6F1FB', dark: '#0C447C' },
        green: { DEFAULT: '#3B6D11', light: '#EAF3DE' },
        amber: { DEFAULT: '#854F0B', light: '#FAEEDA' },
        red: { DEFAULT: '#A32D2D', light: '#FCEBEB' },
        purple: { DEFAULT: '#3C3489', light: '#EEEDFE' },
        teal: { DEFAULT: '#085041', light: '#E1F5EE' },
        surface: '#ffffff',
        'confidence-high': '#3B6D11',
        'confidence-mid': '#854F0B',
        'confidence-low': '#A32D2D',
      },
      fontSize: {
        xs: ['11px', { lineHeight: '1.5' }],
        sm: ['12px', { lineHeight: '1.5' }],
        base: ['13px', { lineHeight: '1.5' }],
        lg: ['15px', { lineHeight: '1.4' }],
        xl: ['17px', { lineHeight: '1.3' }],
        '2xl': ['20px', { lineHeight: '1.2' }],
        '3xl': ['24px', { lineHeight: '1.2' }],
      },
    },
  },
  plugins: [],
}
