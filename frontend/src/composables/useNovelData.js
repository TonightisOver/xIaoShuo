import { ref, toValue, onUnmounted } from 'vue'

export function useNovelData(novelId) {
  const novel = ref(null)
  const world = ref(null)
  const characters = ref([])
  const chapters = ref([])
  const volumes = ref([])
  const conversations = ref([])
  const powerSystems = ref([])
  const storylinesData = ref(null)
  const outlineTree = ref(null)
  const loading = ref(true)
  let controller = null

  onUnmounted(() => controller?.abort())

  async function fetchAll() {
    controller?.abort()
    controller = new AbortController()
    const { signal } = controller
    loading.value = true
    try {
      const id = toValue(novelId)
      const [nRes, wRes, cRes, chRes, convRes, volRes, psRes, slRes, olRes] = await Promise.all([
        fetch(`/api/v1/projects/${id}`, { signal }),
        fetch(`/api/v1/projects/${id}/world`, { signal }),
        fetch(`/api/v1/projects/${id}/characters`, { signal }),
        fetch(`/api/v1/projects/${id}/chapters`, { signal }),
        fetch(`/api/v1/projects/${id}/conversations`, { signal }),
        fetch(`/api/v1/projects/${id}/volumes`, { signal }),
        fetch(`/api/v1/projects/${id}/power-systems`, { signal }),
        fetch(`/api/v1/projects/${id}/relations`, { signal }),
        fetch(`/api/v1/projects/${id}/outlines`, { signal }),
      ])
      if (nRes.ok) novel.value = await nRes.json()
      if (wRes.ok) world.value = await wRes.json()
      if (cRes.ok) characters.value = await cRes.json()
      if (chRes.ok) chapters.value = await chRes.json()
      if (convRes.ok) conversations.value = await convRes.json()
      if (volRes.ok) volumes.value = await volRes.json()
      if (psRes.ok) powerSystems.value = await psRes.json()
      if (slRes.ok) storylinesData.value = await slRes.json()
      if (olRes.ok) outlineTree.value = await olRes.json()
    } catch (e) {
      if (e.name === 'AbortError') return
    } finally {
      if (!signal.aborted) loading.value = false
    }
  }

  return {
    novel,
    world,
    characters,
    chapters,
    volumes,
    conversations,
    powerSystems,
    storylinesData,
    outlineTree,
    loading,
    fetchAll,
  }
}
