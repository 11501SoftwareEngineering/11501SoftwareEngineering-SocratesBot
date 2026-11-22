/** @type {import('tailwindcss').Config} */
// Typography values follow the Figma inspector screenshots.
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)'],
        heading: ['var(--font-heading)'],
      },
      fontSize: {
        'body-lg': ['18px', { lineHeight: '1.6', fontWeight: '400', letterSpacing: '0em' }],
        header: [
          '22px',
          {
            lineHeight: '22px',
            fontWeight: '500',
            letterSpacing: '0em',
          },
        ],
        // Figma 文字樣式「H1」：頁面大標題，例如「探索結果報告」
        'page-title': [
          '40px',
          {
            lineHeight: '1.3',
            fontWeight: '700',
            letterSpacing: '0.02em',
          },
        ],
        'h1-title': [
          '32px',
          {
            lineHeight: '1.4',
            fontWeight: '700',
            letterSpacing: '0.01em',
          },
        ],
        footer: [
          '22px',
          {
            lineHeight: '22px',
            fontWeight: '500',
            letterSpacing: '0em',
          },
        ],
        'h2-title': [
          '20px',
          {
            lineHeight: '20px',
            fontWeight: '500',
            letterSpacing: '0em',
          },
        ],
        body: [
          '16px',
          {
            lineHeight: '1.6',
            fontWeight: '400',
            letterSpacing: '0em',
          },
        ],
        // Figma 文字樣式「Caption」：14px / 行高 1.5（2026-10 依元件頁 Card_News 核對，原本誤寫成 12px）
        caption: [
          '14px',
          {
            lineHeight: '1.5',
            fontWeight: '400',
            letterSpacing: '0em',
          },
        ],
      },
      boxShadow: {
        elevated: '0px 2px 3px 0px rgba(0,0,0,0.1), 0px 2px 2px -1px rgba(0,0,0,0.1)',
        input: 'inset 1.5px 1.5px 4px 0px rgba(0,0,0,0.25)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        // Figma「主色_淺」（主色＋20% 白）：語言按鈕、已發布標籤、學生泡泡
        'primary-light': '#A5C6C1',
        // Figma「主色_深」（主色＋20% 黑）：卡片上的文字連結（檢視觀點↗、進入課程↗）
        'primary-dark': '#72938E',
        // Figma「輔色_淺」（輔色＋20% 白）：草稿標籤
        'secondary-light': '#DDD4C8',
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
          // Figma「點綴色_深」（點綴色＋20% 黑）：欄位下方的錯誤文字
          dark: '#A87E79',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chart: {
          1: 'hsl(var(--chart-1))',
          2: 'hsl(var(--chart-2))',
          3: 'hsl(var(--chart-3))',
          4: 'hsl(var(--chart-4))',
          5: 'hsl(var(--chart-5))',
        },
      },
      borderWidth: { thin: '0.8px' },
      spacing: {
        'course-top': '47px',
        'site-header': '66px',
        'site-logo': '42px',
        navigation: '34px',
        'announcement-top': '54px',
        'announcement-gap': '22px',
        'announcement-inset': '21px',
        'announcement-content': '13px',
      },
      maxWidth: {
        page: '1000px',
        'course-search': '804px',
        account: '83px',
        announcements: '1000px',
      },
      minHeight: {
        'site-header': '66px',
        'course-panel': '797px',
        'course-topic': '96.3px',
        announcement: '98px',
      },
    },
  },
  plugins: [],
}
