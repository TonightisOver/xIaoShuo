import { ref } from 'vue'

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

  async function fetchAll() {
    loading.value = true
    try {
      const id = typeof novelId === 'object' ? novelId.value : novelId
      const [nRes, wRes, cRes, chRes, convRes, volRes, psRes, slRes, olRes] = await Promise.all([
        fetch(`/api/v1/projects/${id}`),
        fetch(`/api/v1/projects/${id}/world`),
        fetch(`/api/v1/projects/${id}/characters`),
        fetch(`/api/v1/projects/${id}/chapters`),
        fetch(`/api/v1/projects/${id}/conversations`),
        fetch(`/api/v1/projects/${id}/volumes`),
        fetch(`/api/v1/projects/${id}/power-systems`),
        fetch(`/api/v1/projects/${id}/relations`),
        fetch(`/api/v1/projects/${id}/outlines`),
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
    } finally {
      loading.value = false
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
