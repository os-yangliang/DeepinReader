/** @type {import('tailwindcss').Config} */
const plugin = require('tailwindcss/plugin')

export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
          950: '#082f49',
        },
        accent: {
          50: '#fdf4ff',
          100: '#fae8ff',
          200: '#f5d0fe',
          300: '#f0abfc',
          400: '#e879f9',
          500: '#d946ef',
          600: '#c026d3',
          700: '#a21caf',
          800: '#86198f',
          900: '#701a75',
        },
        dark: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        }
      },
      fontFamily: {
        sans: ['Noto Sans SC', 'Inter', 'system-ui', 'sans-serif'],
        display: ['Playfair Display', 'serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'fade-in': 'fadeIn 0.5s ease-out',
        'scale-in': 'scaleIn 0.3s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
        'typing': 'typing 1.5s steps(3) infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        typing: {
          '0%': { content: '"."' },
          '33%': { content: '".."' },
          '66%': { content: '"..."' },
        }
      },
      backdropBlur: {
        xs: '2px',
      },
      boxShadow: {
        'glow': '0 0 20px rgba(14, 165, 233, 0.3)',
        'glow-lg': '0 0 40px rgba(14, 165, 233, 0.4)',
        'inner-glow': 'inset 0 0 20px rgba(14, 165, 233, 0.1)',
      }
    },
  },
  plugins: [
    plugin(function({ addBase }) {
      addBase({
        // 解决 text-white 在亮色主题下的问题
        '[data-theme="light"] .text-white': { color: '#0f172a' },
        '[data-theme="light"] .text-gray-400': { color: '#475569' },
        '[data-theme="light"] .text-gray-500': { color: '#64748b' },
        '[data-theme="light"] .text-gray-300': { color: '#334155' },
        '[data-theme="light"] .text-gray-600': { color: '#94a3b8' },
        // 背景覆盖
        '[data-theme="light"] .bg-gray-900\\/50': { backgroundColor: 'rgba(248, 250, 252, 0.8)' },
        '[data-theme="light"] .bg-gray-900\\/80': { backgroundColor: 'rgba(241, 245, 249, 0.9)' },
        '[data-theme="light"] .bg-gray-900\\/90': { backgroundColor: 'rgba(241, 245, 249, 0.95)' },
        // 边框
        '[data-theme="light"] .border-white\\/5': { borderColor: 'rgba(0, 0, 0, 0.06)' },
        '[data-theme="light"] .border-white\\/10': { borderColor: 'rgba(0, 0, 0, 0.08)' },
        '[data-theme="light"] .border-white\\/6': { borderColor: 'rgba(0, 0, 0, 0.06)' },
      })
    }),
  ],
}

