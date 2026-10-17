import { apiClient } from './client'

export interface Announcement {
  id: string
  title: string
  content: string
  published_at: string
}

export const announcementsApi = {
  getAnnouncements() {
    return apiClient.get<Announcement[]>('/system/announcements')
  },
}
