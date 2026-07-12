/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        // 保留 accent（兼容旧代码，逐步迁移到 ink/vermilion）
        accent: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // 墨色系：正文与标题主色（替代 neutral 的冷灰，改暖墨）
        ink: {
          50: '#f7f5f1',
          100: '#ede8e0',
          200: '#d9d0c2',
          300: '#b8a994',
          400: '#8a7a64',
          500: '#5c4f3d',
          600: '#3d3327',
          700: '#2c2416',
          800: '#1f1a11',
          900: '#141009',
        },
        // 纸张系：背景米白暖色（书卷气）
        paper: {
          50: '#fdfbf7',
          100: '#faf7f2',
          200: '#f3ede3',
          300: '#ebe3d4',
          400: '#dccfb8',
        },
        // 朱砂系：印章红，强调与点缀（克制使用）
        vermilion: {
          50: '#fdf2f4',
          100: '#fbe0e5',
          200: '#f5b8c4',
          300: '#ec8099',
          400: '#d94e6f',
          500: '#a8324a',
          600: '#8a273a',
          700: '#6e1f2e',
        },
      },
      fontFamily: {
        sans: ['"Noto Sans SC"', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
        serif: ['"Noto Serif SC"', '"Source Han Serif SC"', 'serif'],
      },
    },
  },
  plugins: [],
}
