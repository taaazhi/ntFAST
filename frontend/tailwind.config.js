/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Apple-inspired Premium Color Palette
        primary: {
          deep: '#1d1d1f',      // Apple's signature dark
          accent: '#0071e3',    // Apple blue
          light: '#2997ff',     // Bright blue
          dark: '#000000',      // Pure black
        },
        success: {
          emerald: '#0D5C4F',   // Изумрудный - успех
          DEFAULT: '#10B981',   // Стандартный зеленый
          light: '#34D399',     // Светлый зеленый
        },
        warning: {
          amber: '#D97706',     // Янтарный - внимание
          DEFAULT: '#F59E0B',   // Стандартный оранжевый
          light: '#FBBF24',     // Светлый оранжевый
        },
        error: {
          ruby: '#DC2626',      // Рубиновый - опасность
          DEFAULT: '#EF4444',   // Стандартный красный
          light: '#F87171',     // Светлый красный
        },
        neutral: {
          50: '#F8FAFC',        // Фон премиум
          100: '#F1F5F9',       // Очень светлый
          200: '#E2E8F0',       // Границы subtle
          300: '#CBD5E1',       // Границы
          400: '#94A3B8',       // Текст placeholder
          500: '#64748B',       // Текст вторичный
          600: '#475569',       // Текст
          700: '#334155',       // Темный текст
          800: '#1E293B',       // Основной текст
          900: '#0F172A',       // Самый темный
        },
        // Для обратной совместимости
        info: '#3B82F6',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'system-ui', 'sans-serif'],
        display: ['SF Pro Display', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'monospace'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem', letterSpacing: '-0.01em' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem', letterSpacing: '-0.01em' }],
        'base': ['1rem', { lineHeight: '1.6', letterSpacing: '-0.01em' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem', letterSpacing: '-0.01em' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem', letterSpacing: '-0.01em' }],
        '2xl': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.02em' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem', letterSpacing: '-0.02em' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.02em' }],
      },
      borderRadius: {
        'premium': '12px',
        'premium-lg': '16px',
        'premium-xl': '20px',
      },
      boxShadow: {
        'premium': '0 2px 8px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06)',
        'premium-hover': '0 4px 16px rgba(0, 0, 0, 0.08), 0 2px 4px rgba(0, 0, 0, 0.06)',
        'premium-lg': '0 8px 30px rgba(0, 0, 0, 0.12), 0 3px 8px rgba(0, 0, 0, 0.08)',
        'premium-inner': 'inset 0 2px 4px rgba(0, 0, 0, 0.04)',
        'apple': '0 0.4px 0.4px rgba(0, 0, 0, 0.022), 0 1px 1px rgba(0, 0, 0, 0.031), 0 1.9px 1.9px rgba(0, 0, 0, 0.039), 0 3.4px 3.4px rgba(0, 0, 0, 0.048), 0 6.3px 6.3px rgba(0, 0, 0, 0.061), 0 15px 15px rgba(0, 0, 0, 0.09)',
      },
      backdropBlur: {
        'premium': '10px',
        'premium-lg': '20px',
      },
      animation: {
        'elegant-appear': 'elegantAppear 0.5s ease-out',
        'shimmer': 'shimmer 2s infinite',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        elegantAppear: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-100% 0' },
          '100%': { backgroundPosition: '100% 0' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
      },
    },
  },
  plugins: [],
}
