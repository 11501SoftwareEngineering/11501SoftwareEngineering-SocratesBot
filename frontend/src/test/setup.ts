// 測試共用設定：每個元件測試都自動裝上 i18n（預設正體中文），測試照常用中文文字比對
import { config } from '@vue/test-utils'
import { i18n } from '@/i18n'

config.global.plugins = [...(config.global.plugins ?? []), i18n]
