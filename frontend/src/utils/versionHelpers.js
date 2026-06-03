export function sourceLabel(source) {
  const labels = {
    manual: '手动',
    ai_rewrite: 'AI 改写',
    rollback: '回滚',
    generation: '生成',
  }
  return labels[source] || source || '未知'
}

export function sourceClass(source) {
  const classes = {
    manual: 'bg-neutral-100 text-neutral-700',
    ai_rewrite: 'bg-blue-50 text-blue-700',
    rollback: 'bg-amber-50 text-amber-700',
    generation: 'bg-emerald-50 text-emerald-700',
  }
  return classes[source] || 'bg-neutral-100 text-neutral-700'
}

export function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatNumber(value) {
  if (value == null) return '-'
  return Number(value).toLocaleString('zh-CN')
}
