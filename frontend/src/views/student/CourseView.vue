<script setup lang="ts">
import { computed, ref, useTemplateRef, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useFocus } from '@vueuse/core'
import { CircleX, Search } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useStudentCourse } from '@/composables/useStudentCourse'
import { getApiErrorMessage } from '@/lib/utils'

const route = useRoute()
const courseId = computed(() => String(route.params.courseId ?? ''))
const { data: course, isPending, isError, error, isFetching, refetch } = useStudentCourse(courseId)
const search = ref('')
const searchInput = useTemplateRef<InstanceType<typeof Input>>('searchInput')
const searchElement = computed(() => searchInput.value?.$el as HTMLInputElement | undefined)
const { focused } = useFocus(searchElement)

const filteredTopics = computed(() => {
  const term = search.value.trim().toLocaleLowerCase()
  const topics = course.value?.topics ?? []
  if (!term) return topics
  return topics.filter((topic) =>
    [topic.title, topic.description ?? ''].some((text) => text.toLocaleLowerCase().includes(term)),
  )
})

watch(courseId, () => {
  search.value = ''
})

function handleClearSearch() {
  search.value = ''
  focused.value = true
}
</script>

<template>
  <section
    class="mx-auto mt-course-top w-full max-w-page px-5 py-4 lg:min-h-course-panel"
    aria-labelledby="course-title"
    :aria-busy="isFetching"
  >
    <h1 id="course-title" class="mb-1 font-heading text-h1-title">問題列表</h1>
    <div role="search" class="relative mb-1 w-full max-w-course-search">
      <label for="course-search" class="sr-only">搜尋課程問題</label>
      <Search
        aria-hidden="true"
        class="pointer-events-none absolute left-3 top-1/2 z-10 size-5 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        id="course-search"
        ref="searchInput"
        v-model="search"
        type="search"
        placeholder="搜尋"
        autocomplete="off"
        aria-controls="course-topics"
        class="h-9 rounded-full bg-card py-1 pl-9 pr-10 text-body shadow-elevated placeholder:text-muted-foreground [&::-webkit-search-cancel-button]:appearance-none"
        @keydown.esc.prevent="handleClearSearch"
      />
      <button
        type="button"
        aria-label="清除搜尋"
        :disabled="!search"
        class="absolute right-1 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-full text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default"
        @click="handleClearSearch"
      >
        <CircleX aria-hidden="true" class="size-5" />
      </button>
    </div>

    <p v-if="isPending" role="status" class="py-4 text-body-lg text-muted-foreground">
      問題載入中…
    </p>
    <Card v-else-if="isError" class="rounded-2xl border-border p-4 shadow-elevated">
      <p role="alert" class="mb-4 text-body-lg text-destructive">
        {{ getApiErrorMessage(error, '課程載入失敗，請稍後再試') }}
      </p>
      <Button variant="secondary" :disabled="isFetching" @click="refetch()">重新載入</Button>
    </Card>
    <p
      v-else-if="course?.topics.length === 0"
      role="status"
      class="py-4 text-body-lg text-muted-foreground"
    >
      這門課程目前沒有問題
    </p>
    <p
      v-else-if="filteredTopics.length === 0"
      role="status"
      class="py-4 text-body-lg text-muted-foreground"
    >
      找不到符合搜尋的問題
    </p>
    <ul v-else id="course-topics" class="space-y-2">
      <li v-for="topic in filteredTopics" :key="topic.topic_id">
        <RouterLink
          :to="{ name: 'StudentChat', params: { questionId: topic.topic_id }, query: { courseId } }"
          class="group block rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <Card
            class="min-h-course-topic rounded-2xl border-thin border-border p-4 shadow-elevated transition-colors group-hover:border-foreground"
          >
            <h2 class="break-words text-h2-title">{{ topic.title }}</h2>
            <p class="flex flex-wrap gap-x-4 text-body-lg text-muted-foreground">
              <span class="min-w-0 break-words">年齡層：{{ topic.age_range || '未提供' }}</span>
              <span class="min-w-0 break-words">回合數：{{ topic.round_count ?? '未提供' }}</span>
            </p>
          </Card>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>
