/** @type {import('tailwindcss').Config} */
export default {
    darkMode: ["class"],
    content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
  	extend: {
  		fontFamily: {
  			sans: ['var(--font-sans)'],
  			heading: ['var(--font-heading)']
  		},
  		// 對應 Figma「Text styles」面板裡的 5 個命名樣式（字級/行高，單位 px）。
  		// 用法：text-header / text-h1-title / text-footer / text-h2-title / text-body
  		// 這樣寫比 text-[32px] leading-[16px] 這種寫死的任意值更好維護，
  		// 之後設計稿改字級，只要改這裡一個地方。
  		fontSize: {
  			'header': ['24px', '24px'],     // Figma: Header_text
  			'h1-title': ['32px', '16px'],   // Figma: h1_title（注意行高比字級小，是設計稿刻意的）
  			'footer': ['16px', '16px'],     // Figma: Footer_text
  			'h2-title': ['16px', '20px'],   // Figma: h2_title
  			'body': ['12px', '19.5px'],     // Figma: Body
  		},
  		// 對應 Figma「Effect styles」面板裡的 2 個命名樣式。
  		// 用法：shadow-elevated（按鈕/卡片的外陰影）、shadow-input（輸入框的內陰影）
  		boxShadow: {
  			// Figma "Shadow"：兩層 drop shadow 疊加
  			'elevated': '0px 2px 3px 0px rgba(0,0,0,0.1), 0px 2px 2px -1px rgba(0,0,0,0.1)',
  			// Figma "input"：一層 inner shadow
  			'input': 'inset 1.5px 1.5px 4px 0px rgba(0,0,0,0.25)',
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		colors: {
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			}
  		}
  	}
  },
  plugins: [],
}