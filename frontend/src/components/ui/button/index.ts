import type { VariantProps } from 'class-variance-authority'
import { cva } from 'class-variance-authority'

export { default as Button } from './Button.vue'

/*
 * variant / size 對照 Figma「Botton」元件的變體軸：
 *   Figma State=Default,  Color=Primary,   Style=Default -> variant="default"   (實心主色按鈕，例如「登入」)
 *   Figma State=Default,  Color=Secondary, Style=Default -> variant="secondary" (實心輔色按鈕，例如頁首「登入」導覽按鈕)
 *   Figma State=Default,  Style=Text (不分 Color)         -> variant="ghost"     (純文字按鈕，例如「註冊」「隱私權」)
 *   Figma State=Hover 則交給瀏覽器原生的 :hover 處理，不用另外做一個 variant。
 *   Figma Size=Large -> size="lg"；Size=Small -> size="default" / "sm"。
 *   注意：Figma 按鈕的文字比一般網頁習慣大很多——Large 是 32px（設計稿裡叫 h1_title），
 *   Small 是 24px，不是網頁常見的 14-16px，size="lg" 已經改成 text-[32px]，
 *   不要因為「看起來很大」就自己改小，這是設計稿刻意的風格。
 * 按鈕文字用 --primary-foreground / --secondary-foreground（已在 main.css 設成深色 #4F595D），
 * 這是 Figma 特意設計成「淺色底 + 深色字」，不是白字，記得不要改回白色。
 *
 * hover 顏色說明（這是修正過的地方）：
 * Figma 的 hover 是「底色 + 疊一層黑色 15% 透明度」，效果是讓顏色變暗、變濃。
 * 一開始寫成 hover:bg-primary/85（把按鈕底色本身變透明 85%），
 * 但按鈕外面是白色卡片，透明度一降低，白色會透出來，顏色反而變「淺」，跟 Figma 想要的「變暗」剛好相反。
 * 所以改成 hover:brightness-90，維持底色不透明，用亮度往下壓 10%，比較接近 Figma 疊黑色的暗化效果。
 *
 * 邊框說明（這也是修正過的地方）：
 * Figma 查證後只有 Large 尺寸的實心按鈕才有 #EBE9E1 邊框，Small 尺寸完全沒有邊框。
 * 原本 border-border 是直接寫在 variant 裡、跟尺寸無關，導致 Small 按鈕也跟著長出邊框。
 * 改成 data-[size=lg]:border-border，只有在 size="lg" 時才會有邊框，Small 維持無邊框。
 */
export const buttonVariants = cva(
  'focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 rounded-lg border border-transparent bg-clip-padding font-heading text-sm font-medium focus-visible:ring-3 aria-invalid:ring-3 active:not-aria-[haspopup]:translate-y-px [&_svg:not([class*=size-])]:size-4 group/button inline-flex shrink-0 items-center justify-center whitespace-nowrap transition-all outline-none select-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground data-[size=lg]:border-border data-[size=lg]:shadow-[0px_2px_3px_0px_rgba(0,0,0,0.1),0px_2px_2px_-1px_rgba(0,0,0,0.1)] hover:brightness-90',
        outline: 'border-border bg-background hover:bg-muted hover:text-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 aria-expanded:bg-muted aria-expanded:text-foreground shadow-xs',
        secondary: 'bg-secondary text-secondary-foreground data-[size=lg]:border-border data-[size=lg]:shadow-[0px_2px_3px_0px_rgba(0,0,0,0.1),0px_2px_2px_-1px_rgba(0,0,0,0.1)] hover:brightness-90',
        ghost: 'text-foreground hover:text-muted-foreground aria-expanded:text-foreground',
        destructive: 'bg-destructive/10 hover:bg-destructive/20 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/20 text-destructive focus-visible:border-destructive/40 dark:hover:bg-destructive/30',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        'default': 'h-9 gap-1.5 px-2.5 in-data-[slot=button-group]:rounded-md has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2',
        'xs': 'h-6 gap-1 rounded-[min(var(--radius-md),8px)] px-2 text-xs in-data-[slot=button-group]:rounded-md has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*=size-])]:size-3',
        'sm': 'h-auto min-h-8 gap-1 rounded-[min(var(--radius-md),10px)] px-4 py-1.5 text-[24px] leading-none in-data-[slot=button-group]:rounded-md has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5',
        'lg': 'h-auto min-h-11 gap-2 px-8 py-4 text-[32px] leading-none has-data-[icon=inline-end]:pr-4 has-data-[icon=inline-start]:pl-4',
        'icon': 'size-9',
        'icon-xs': 'size-6 rounded-[min(var(--radius-md),8px)] in-data-[slot=button-group]:rounded-md [&_svg:not([class*=size-])]:size-3',
        'icon-sm': 'size-8 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-md',
        'icon-lg': 'size-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)
export type ButtonVariants = VariantProps<typeof buttonVariants>
