/**
 * Figma 元件頁匯出的圖示（原始 SVG 放在 src/assets/icons/，不要手動修改）。
 * 顏色已經是設計稿指定的顏色，所以直接當圖片用。
 *
 * 用法：<AddRingIcon />、<SearchIcon class="size-5" />
 * 都是裝飾用圖示（alt=""），按鈕要有文字或 aria-label 說明用途。
 *
 * Figma 沒有提供的圖示，請用 @lucide/vue，粗細和圓角風格相近。
 */
import { defineComponent, h } from 'vue'
import addRingUrl from '@/assets/icons/add-ring.svg'
import checkboxCheckedUrl from '@/assets/icons/checkbox-checked.svg'
import checkboxUncheckedUrl from '@/assets/icons/checkbox-unchecked.svg'
import closeRingUrl from '@/assets/icons/close-ring.svg'
import editUrl from '@/assets/icons/edit.svg'
import menuUrl from '@/assets/icons/menu.svg'
import micUrl from '@/assets/icons/mic.svg'
import refreshUrl from '@/assets/icons/refresh.svg'
import searchUrl from '@/assets/icons/search.svg'
import sendUrl from '@/assets/icons/send.svg'
import signOutUrl from '@/assets/icons/sign-out.svg'
import trashUrl from '@/assets/icons/trash.svg'

function figmaIcon(name: string, src: string, size: number) {
  return defineComponent({
    name,
    setup(_, { attrs }) {
      return () =>
        h('img', {
          src,
          alt: '',
          width: size,
          height: size,
          'aria-hidden': 'true',
          draggable: false,
          ...attrs,
        })
    },
  })
}

export const AddRingIcon = figmaIcon('AddRingIcon', addRingUrl, 24)
export const SearchIcon = figmaIcon('SearchIcon', searchUrl, 24)
export const CloseRingIcon = figmaIcon('CloseRingIcon', closeRingUrl, 24)
export const CheckboxCheckedIcon = figmaIcon('CheckboxCheckedIcon', checkboxCheckedUrl, 24)
export const CheckboxUncheckedIcon = figmaIcon('CheckboxUncheckedIcon', checkboxUncheckedUrl, 24)
export const MicIcon = figmaIcon('MicIcon', micUrl, 16)
export const SendIcon = figmaIcon('SendIcon', sendUrl, 14)
export const EditIcon = figmaIcon('EditIcon', editUrl, 24)
export const TrashIcon = figmaIcon('TrashIcon', trashUrl, 24)
export const RefreshIcon = figmaIcon('RefreshIcon', refreshUrl, 24)
export const SignOutIcon = figmaIcon('SignOutIcon', signOutUrl, 24)
export const MenuIcon = figmaIcon('MenuIcon', menuUrl, 24)
