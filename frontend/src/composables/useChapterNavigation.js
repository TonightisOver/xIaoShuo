import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

export function useChapterNavigation(novelId, chapterNumber) {
  const router = useRouter()
  const allChapters = ref([])
  const allVolumes = ref([])

  function _id() { return typeof novelId === 'object' ? novelId.value : novelId }

  async function loadAllChapters() {
    const res = await fetch(`/api/v1/projects/${_id()}/chapters`)
    if (res.ok) allChapters.value = await res.json()
  }

  async function loadVolumes() {
    const res = await fetch(`/api/v1/projects/${_id()}/volumes`)
    if (res.ok) allVolumes.value = await res.json()
    else allVolumes.value = []
  }

  const sortedChapters = computed(() =>
    [...allChapters.value].sort((a, b) => a.chapter_number - b.chapter_number)
  )

  const groupedChapters = computed(() => {
    const groups = []
    const sorted = sortedChapters.value
    if (allVolumes.value.length === 0) {
      groups.push({ title: '正文目录', chapters: sorted })
      return groups
    }
    const volMap = new Map()
    for (const vol of allVolumes.value) volMap.set(vol.volume_number, vol)
    const volumeGroups = {}
    const unassigned = []
    for (const ch of sorted) {
      const volNum = ch.volume_number
      if (volNum && volMap.has(volNum)) {
        if (!volumeGroups[volNum]) volumeGroups[volNum] = []
        volumeGroups[volNum].push(ch)
      } else {
        unassigned.push(ch)
      }
    }
    const sortedVolNums = Object.keys(volumeGroups).map(Number).sort((a, b) => a - b)
    for (const volNum of sortedVolNums) {
      const vol = volMap.get(volNum)
      groups.push({ volume_number: volNum, title: `第${volNum}卷 · ${vol.title || '未命名'}`, chapters: volumeGroups[volNum] })
    }
    if (unassigned.length > 0) groups.push({ title: '未分卷章节', chapters: unassigned })
    return groups
  })

  function currentChapterIdx(chapter) {
    if (!chapter) return -1
    return sortedChapters.value.findIndex(c => c.chapter_number === chapter.chapter_number)
  }

  const prevChapter = computed(() => {
    const num = typeof chapterNumber === 'object' ? parseInt(chapterNumber.value) : parseInt(chapterNumber)
    const idx = sortedChapters.value.findIndex(c => c.chapter_number === num)
    return idx > 0 ? sortedChapters.value[idx - 1] : null
  })

  const nextChapter = computed(() => {
    const num = typeof chapterNumber === 'object' ? parseInt(chapterNumber.value) : parseInt(chapterNumber)
    const idx = sortedChapters.value.findIndex(c => c.chapter_number === num)
    return idx !== -1 && idx < sortedChapters.value.length - 1 ? sortedChapters.value[idx + 1] : null
  })

  function goToChapter(num) {
    router.push(`/novels/${_id()}/chapters/${num}`)
  }

  return {
    allChapters,
    allVolumes,
    sortedChapters,
    groupedChapters,
    prevChapter,
    nextChapter,
    loadAllChapters,
    loadVolumes,
    currentChapterIdx,
    goToChapter,
  }
}
