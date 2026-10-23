<script setup lang="ts">
import { announcements } from '@/data/announcements'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

function formatDate(value: string) {
  // Display announcement dates in Asia/Taipei.
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '日期未提供'
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Taipei',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}
</script>

<template>
  <section
    class="mx-auto w-full max-w-announcements px-5 pb-16 pt-12 sm:pt-announcement-top"
    aria-labelledby="announcements-title"
  >
    <h1 id="announcements-title" class="mb-announcement-gap font-heading text-h1-title">公告</h1>
    <p v-if="announcements.length === 0" role="status" class="text-body text-muted-foreground">
      目前沒有公告
    </p>
    <ul v-else class="space-y-announcement-gap">
      <li v-for="announcement in announcements" :key="announcement.id">
        <article>
          <Card
            class="min-h-announcement rounded-2xl border-border pb-4 pt-announcement-inset shadow-elevated"
          >
            <CardHeader
              class="gap-y-2 p-0 px-announcement-inset sm:flex-row sm:items-center sm:justify-between sm:gap-x-6 sm:gap-y-0"
            >
              <h2 class="min-w-0 break-words text-h2-title">{{ announcement.title }}</h2>
              <time
                :datetime="announcement.published_at"
                class="shrink-0 text-caption text-muted-foreground"
              >
                {{ formatDate(announcement.published_at) }}
              </time>
            </CardHeader>
            <CardContent class="mt-announcement-content p-0 pl-announcement-inset pr-4">
              <p class="whitespace-pre-wrap break-words text-body text-muted-foreground">
                {{ announcement.content }}
              </p>
            </CardContent>
          </Card>
        </article>
      </li>
    </ul>
  </section>
</template>
