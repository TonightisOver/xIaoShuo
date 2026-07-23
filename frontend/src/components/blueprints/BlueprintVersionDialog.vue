<template>
  <div v-if="visible" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50" data-version-dialog>
    <div class="bg-paper-50 rounded-lg p-6 w-[640px] max-h-[80vh] overflow-auto">
      <h3 class="heading-serif text-lg mb-4">版本历史</h3>
      <ul class="space-y-1 mb-4">
        <li v-for="v in versions" :key="v.version_number"
            class="flex items-center gap-2 text-sm">
          <button @click="$emit('compare', v.version_number)"
                  class="text-vermilion-600 text-xs">对比</button>
          <button v-if="!v.is_active"
                  @click="$emit('select-rollback', v.version_number)"
                  :data-select-rollback="v.version_number"
                  class="text-vermilion-600 text-xs">回退到此版本</button>
          <span>v{{ v.version_number }}</span>
          <span class="text-ink-400 text-xs">{{ v.source }}</span>
        </li>
      </ul>
      <p v-if="!versions.length" class="text-sm text-ink-400 mb-4">
        尚无可回退的版本记录。重新生成或保存一次后将建立版本历史。
      </p>
      <p v-if="impactLoading" class="text-sm text-ink-400 mb-4">
        正在加载回退影响范围...
      </p>

      <!-- 字段对比表 -->
      <table v-if="compareResult" class="w-full text-xs mb-4" data-compare-table>
        <thead><tr class="text-ink-500">
          <th class="text-left">字段</th><th class="text-left">旧值</th><th class="text-left">新值</th><th>变化</th>
        </tr></thead>
        <tbody>
          <tr v-for="d in compareResult.fields" :key="d.field">
            <td>{{ d.field }}</td><td>{{ format(d.old) }}</td><td>{{ format(d.new) }}</td>
            <td>{{ d.changed ? '是' : '否' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 回退确认 -->
      <div v-if="targetVersion" class="p-3 rounded bg-vermilion-50 text-sm" data-rollback-confirm>
        <p>确认回退到 v{{ targetVersion }}？</p>
        <p v-if="impact" class="text-xs text-ink-500 mt-1">
          直接影响 {{ impact.direct_downstream?.length || 0 }} 项，
          全部影响 {{ impact.full_downstream?.length || 0 }} 项
        </p>
        <button @click="onRollback" data-confirm-rollback class="btn-primary text-xs mt-2">确认回退</button>
        <button @click="$emit('close')" class="btn-secondary text-xs mt-2 ml-2">取消</button>
      </div>

      <button @click="$emit('close')" class="btn-secondary text-xs w-full mt-4">关闭</button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  versions: { type: Array, default: () => [] },
  compareResult: { type: Object, default: null },
  targetVersion: { type: [Number, null], default: null },
  impact: { type: Object, default: null },
  impactLoading: { type: Boolean, default: false },
})
const emit = defineEmits(['compare', 'select-rollback', 'rollback', 'close'])
function onRollback() { emit('rollback', props.targetVersion) }
function format(v) {
  if (Array.isArray(v) || (typeof v === 'object' && v !== null)) return JSON.stringify(v)
  return v
}
</script>
