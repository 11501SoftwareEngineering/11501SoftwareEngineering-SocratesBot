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
import alarmClockUrl from '@/assets/icons/alarm-clock.svg'
import chatUrl from '@/assets/icons/chat.svg'
import checkUrl from '@/assets/icons/check.svg'
import checkRingUrl from '@/assets/icons/check-ring.svg'
import copyHoverUrl from '@/assets/icons/copy-hover.svg'
import lockUrl from '@/assets/icons/lock.svg'
import pinUrl from '@/assets/icons/pin.svg'
import chevronDownUrl from '@/assets/icons/chevron-down.svg'
import copyUrl from '@/assets/icons/copy.svg'
import doughnutUrl from '@/assets/icons/doughnut.svg'
import externalUrl from '@/assets/icons/external.svg'
import fileUrl from '@/assets/icons/file.svg'
import globeUrl from '@/assets/icons/globe.svg'
import groupUrl from '@/assets/icons/group.svg'
import leaveUrl from '@/assets/icons/leave.svg'
import settingUrl from '@/assets/icons/setting.svg'
import spinnerUrl from '@/assets/icons/spinner.svg'
import timeUrl from '@/assets/icons/time.svg'
import uploadCircleUrl from '@/assets/icons/upload-circle.svg'
import userDeleteUrl from '@/assets/icons/user-delete.svg'
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
import soundMaxUrl from '@/assets/icons/sound-max.svg'
import trashUrl from '@/assets/icons/trash.svg'

/**
 * 單色圖示（用在只有圖示的按鈕上）：用 CSS mask 畫，顏色跟著文字顏色（currentColor）。
 * Figma 的圖示按鈕滑過時是圖示線條換色（一般 → 文字輔色、紅色 → 點綴色），
 * 用 <img> 換不了色，所以這幾個圖示改用這個方式。預設顏色由按鈕的文字顏色決定（文字主色）。
 */
function figmaMonoIcon(name: string, src: string, size: number) {
  return defineComponent({
    name,
    setup(_, { attrs }) {
      return () =>
        h('span', {
          'aria-hidden': 'true',
          class: 'inline-block shrink-0 bg-current',
          style: {
            width: `${size}px`,
            height: `${size}px`,
            maskImage: `url("${src}")`,
            WebkitMaskImage: `url("${src}")`,
            maskSize: '100% 100%',
            WebkitMaskSize: '100% 100%',
            maskRepeat: 'no-repeat',
            WebkitMaskRepeat: 'no-repeat',
          },
          ...attrs,
        })
    },
  })
}

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
export const EditIcon = figmaMonoIcon('EditIcon', editUrl, 24)
export const TrashIcon = figmaMonoIcon('TrashIcon', trashUrl, 24)
export const RefreshIcon = figmaIcon('RefreshIcon', refreshUrl, 24)
export const SignOutIcon = figmaIcon('SignOutIcon', signOutUrl, 24)
export const MenuIcon = figmaIcon('MenuIcon', menuUrl, 24)
export const SoundIcon = figmaIcon('SoundIcon', soundMaxUrl, 24)
export const AlarmClockIcon = figmaIcon('AlarmClockIcon', alarmClockUrl, 24)
export const ChatIcon = figmaIcon('ChatIcon', chatUrl, 24)
export const ChevronDownIcon = figmaIcon('ChevronDownIcon', chevronDownUrl, 24)
/** Figma「Select」選單裡選中項目前面的勾（node 971:2919） */
export const CheckIcon = figmaIcon('CheckIcon', checkUrl, 16)
/** Figma「Check_ring」：Banner 成功、Copy 複製完成 */
export const CheckRingIcon = figmaIcon('CheckRingIcon', checkRingUrl, 24)
/** Figma「Copy」滑過（文字輔色） */
export const CopyHoverIcon = figmaIcon('CopyHoverIcon', copyHoverUrl, 24)
/** Figma Banner「Lock」 */
export const LockIcon = figmaIcon('LockIcon', lockUrl, 24)
/** Figma「Pin」：Banner「Info」 */
export const PinIcon = figmaIcon('PinIcon', pinUrl, 24)
export const CopyIcon = figmaIcon('CopyIcon', copyUrl, 24)
export const DoughnutIcon = figmaIcon('DoughnutIcon', doughnutUrl, 24)
export const ExternalIcon = figmaIcon('ExternalIcon', externalUrl, 24)
export const FileIcon = figmaIcon('FileIcon', fileUrl, 24)
export const GlobeIcon = figmaIcon('GlobeIcon', globeUrl, 20)
export const GroupIcon = figmaIcon('GroupIcon', groupUrl, 24)
export const LeaveIcon = figmaMonoIcon('LeaveIcon', leaveUrl, 24)
export const SettingIcon = figmaIcon('SettingIcon', settingUrl, 24)
export const SpinnerIcon = figmaIcon('SpinnerIcon', spinnerUrl, 22)
export const TimeIcon = figmaIcon('TimeIcon', timeUrl, 24)
export const UploadCircleIcon = figmaIcon('UploadCircleIcon', uploadCircleUrl, 24)
export const UserDeleteIcon = figmaMonoIcon('UserDeleteIcon', userDeleteUrl, 24)
