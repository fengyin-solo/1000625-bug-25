<template>
  <section class="page" data-module="review">
    <header class="page-head">
      <div>
        <h2>结果复核管理</h2>
        <p class="page-desc">维护复核记录，围绕复核编号、关联结果、复核项目、复核人做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记复核记录</button>
        <button class="btn" type="button" @click="exportRows">导出结果复核清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
        <p v-if="item.error" class="stat-error">
          {{ item.error }}
          <button class="link" type="button" @click="loadStats">重试</button>
        </p>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>复核编号</span>
        <input v-model="keyword" placeholder="按复核编号检索" />
      </label>
      <label class="filter-item">
        <span>复核状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="option in statuses" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length + 1" class="state-cell">复核记录加载中，请稍候…</td>
        </tr>
        <tr v-else-if="loadError">
          <td :colspan="columns.length + 1" class="state-cell is-error">
            <span>复核记录加载失败：{{ loadError }}</span>
            <button class="btn" type="button" @click="reload">重试</button>
          </td>
        </tr>
        <tr v-else-if="!rows.length && hasActiveFilters">
          <td :colspan="columns.length + 1" class="empty-state">
            <p>没有符合当前筛选条件的复核记录，请调整关键字或状态后重新查询。</p>
            <p class="empty-actions">
              <button class="btn ghost" type="button" @click="resetFilters">清空筛选条件</button>
            </p>
          </td>
        </tr>
        <tr v-else-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            <p>暂无复核记录。检测结果在「检测结果」模块完成“提交复核”后会出现在这里。</p>
            <p class="empty-actions">
              <RouterLink class="btn" to="/result">前往检测结果</RouterLink>
              <button class="btn ghost" type="button" @click="reload">刷新列表</button>
            </p>
          </td>
        </tr>
        <tr v-for="row in rows" v-else :key="String(row.id)">
          <td
            v-for="column in columns"
            :key="column"
            :class="{ 'cell-clamp': longColumns.has(column) }"
          >
            <span v-if="column === '复核状态'" class="status-tag" :class="statusClass(row[column])">{{ row[column] }}</span>
            <span v-else :title="longColumns.has(column) ? formatText(row[column]) : undefined">{{ formatText(row[column]) }}</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <button
              v-if="row['复核状态'] === '待复核'"
              class="link"
              type="button"
              :disabled="actingId === Number(row.id)"
              @click="quickStart(row)"
            >
              {{ actingId === Number(row.id) ? '提交中…' : '开始复核' }}
            </button>
            <button v-if="row['复核状态'] === '复核中'" class="link" type="button" @click="openAction('确认通过', row)">确认通过</button>
            <button v-if="row['复核状态'] === '复核中'" class="link" type="button" @click="openAction('发起重测', row)">发起重测</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条结果复核记录</span>
      <span v-if="successMessage" class="success-text">{{ successMessage }}</span>
      <span v-if="errorMessage" class="error-text">
        {{ errorMessage }}
        <button v-if="!loading" class="link" type="button" @click="reload">重试</button>
      </span>
    </footer>

    <div v-if="modal.open" class="modal-mask" @click.self="closeModal">
      <div class="modal-card" role="dialog" aria-modal="true" aria-label="复核记录详情">
        <header class="modal-head">
          <h3>{{ modal.mode === 'detail' ? '复核记录详情' : modal.action }}</h3>
          <button class="link" type="button" @click="closeModal">关闭</button>
        </header>

        <div v-if="modal.loading" class="modal-body state-cell">复核记录加载中，请稍候…</div>
        <div v-else-if="modal.loadError" class="modal-body state-cell is-error">
          <span>复核详情读取失败：{{ modal.loadError }}</span>
          <button class="btn" type="button" @click="loadDetail(Number(modal.entryId))">重试</button>
        </div>
        <template v-else-if="modal.entry">
          <dl class="detail-list">
            <div v-for="field in detailFields" :key="field" class="detail-item">
              <dt>{{ field }}</dt>
              <dd>
                <span v-if="field === '复核状态'" class="status-tag" :class="statusClass(modal.entry[field])">{{ modal.entry[field] }}</span>
                <span v-else>{{ formatText(modal.entry[field]) }}</span>
              </dd>
            </div>
          </dl>

          <div v-if="modal.mode === 'action'" class="action-form">
            <label class="action-field">
              <span>{{ inputMeta?.label }}<em class="required-mark">*</em></span>
              <textarea
                v-model="modal.input"
                rows="4"
                :placeholder="inputMeta?.placeholder"
              ></textarea>
              <small class="input-hint" :class="{ 'is-error': modal.input.trim().length > INPUT_MAX_LENGTH }">
                必填，{{ modal.input.trim().length }}/{{ INPUT_MAX_LENGTH }}，超出后无法提交
              </small>
            </label>
          </div>

          <p v-if="modal.error" class="error-text modal-error">
            {{ modal.error }}
            <button v-if="modal.conflict" class="link" type="button" @click="refreshDetail">刷新记录后重试</button>
          </p>

          <footer class="modal-actions">
            <template v-if="modal.mode === 'detail'">
              <button
                v-if="modal.entry['复核状态'] === '待复核'"
                class="btn primary"
                type="button"
                :disabled="modal.submitting"
                @click="startFromModal"
              >
                {{ modal.submitting ? '提交中…' : '开始复核' }}
              </button>
              <template v-if="modal.entry['复核状态'] === '复核中'">
                <button class="btn primary" type="button" @click="switchToAction('确认通过')">确认通过</button>
                <button class="btn danger" type="button" @click="switchToAction('发起重测')">发起重测</button>
              </template>
            </template>
            <template v-else>
              <button class="btn primary" type="button" :disabled="modal.submitting" @click="submitAction">
                {{ modal.submitting ? '提交中…' : `提交${modal.action}` }}
              </button>
              <button class="btn" type="button" :disabled="modal.submitting" @click="switchToDetail">返回详情</button>
            </template>
          </footer>
        </template>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Stats = { pending: number; passed_month: number; retest: number }
type ActionName = '开始复核' | '确认通过' | '发起重测'
type FormAction = Exclude<ActionName, '开始复核'>

const ENDPOINT = '/api/review'
const columns = ['复核编号', '关联结果', '复核项目', '复核人', '复核意见', '复核时间', '差异说明', '复核状态']
const detailFields = columns
const longColumns = new Set(['复核意见', '差异说明'])
const statuses = ['待复核', '复核中', '已通过', '需重测']
const INPUT_MAX_LENGTH = 500

const ACTION_INPUT: Record<FormAction, { field: '复核意见' | '差异说明'; label: string; placeholder: string }> = {
  确认通过: { field: '复核意见', label: '复核意见', placeholder: '请填写复核意见；确认通过必须填写意见后才能提交' },
  发起重测: { field: '差异说明', label: '差异说明', placeholder: '请说明检测结果与复核结论的差异及重测原因' },
}

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const loadError = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const actingId = ref<number | null>(null)

const stats = reactive<{ data: Stats | null; error: string }>({ data: null, error: '' })

const statCards = computed(() => [
  { label: '待复核记录', value: stats.data ? stats.data.pending : '—', error: stats.error },
  { label: '本月通过数', value: stats.data ? stats.data.passed_month : '—', error: '' },
  { label: '需重测项数', value: stats.data ? stats.data.retest : '—', error: '' },
])

const hasActiveFilters = computed(() => Boolean(keyword.value.trim() || statusFilter.value))

const modal = reactive({
  open: false,
  mode: 'detail' as 'detail' | 'action',
  action: '' as '' | ActionName,
  entryId: null as number | null,
  entry: null as Row | null,
  input: '',
  loading: false,
  loadError: '',
  submitting: false,
  error: '',
  conflict: false,
})

const inputMeta = computed(() =>
  modal.mode === 'action' && modal.action && modal.action !== '开始复核'
    ? ACTION_INPUT[modal.action]
    : undefined,
)

function formatText(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function statusClass(value: string | number | null | undefined): string {
  const map: Record<string, string> = {
    待复核: 'is-pending',
    复核中: 'is-doing',
    已通过: 'is-passed',
    需重测: 'is-retest',
  }
  return map[String(value ?? '')] ?? 'is-pending'
}

function flashSuccess(message: string) {
  successMessage.value = message
  window.setTimeout(() => {
    if (successMessage.value === message) {
      successMessage.value = ''
    }
  }, 4000)
}

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown; message?: unknown }
    const detail = body.detail ?? body.message
    if (typeof detail === 'string' && detail) {
      return detail
    }
  } catch {
    // 错误体不是 JSON 时使用兜底文案
  }
  return `${fallback}（HTTP ${response.status}）`
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '复核记录登记入口尚未接入审批流'
}

async function reload() {
  loading.value = true
  loadError.value = ''
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (keyword.value.trim()) {
    params.set('keyword', keyword.value.trim())
  }
  if (statusFilter.value) {
    params.set('status', statusFilter.value)
  }
  const query = params.toString()
  try {
    const response = await request(`${ENDPOINT}${query ? `?${query}` : ''}`)
    if (!response.ok) {
      throw new Error(await readErrorDetail(response, '复核记录列表读取失败'))
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    rows.value = []
    total.value = 0
    loadError.value = error instanceof Error ? error.message : '复核记录列表读取失败'
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  stats.error = ''
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) {
      throw new Error(await readErrorDetail(response, '复核统计读取失败'))
    }
    stats.data = (await response.json()) as Stats
  } catch (error) {
    stats.error = error instanceof Error ? error.message : '复核统计读取失败'
  }
}

async function postAction(
  row: Row,
  action: ActionName,
  extra: Record<string, string> = {},
): Promise<{ ok: boolean; status: number; message: string; entry: Row | null }> {
  const response = await request(`${ENDPOINT}/${row.id}/actions`, {
    method: 'POST',
    body: JSON.stringify({
      values: {
        action,
        expected_version: row.version,
        ...extra,
      },
    }),
  })
  let message = ''
  let entry: Row | null = null
  let bodyOk = true
  try {
    const body = (await response.json()) as { ok?: boolean; message?: string; entry?: Row }
    bodyOk = body.ok ?? true
    message = body.message ?? ''
    entry = body.entry ?? null
  } catch {
    // 非 JSON 响应（如 409/500 的纯文本）交给下面的状态分支处理
  }
  if (!response.ok) {
    return { ok: false, status: response.status, message: message || `操作未生效（HTTP ${response.status}）`, entry }
  }
  if (!bodyOk) {
    return { ok: false, status: 200, message: message || '复核动作未生效，请按提示调整后重试', entry }
  }
  return { ok: true, status: 200, message: message || `复核记录已${action}`, entry }
}

async function quickStart(row: Row) {
  errorMessage.value = ''
  actingId.value = Number(row.id)
  try {
    const result = await postAction(row, '开始复核')
    if (!result.ok) {
      errorMessage.value = result.status === 409
        ? `${result.message}，请刷新列表后重试`
        : result.message
      if (result.status === 409) {
        await reload()
      }
      return
    }
    flashSuccess(result.message)
    await reload()
    await loadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '开始复核失败，请稍后重试'
  } finally {
    actingId.value = null
  }
}

function openDetail(row: Row) {
  modal.open = true
  modal.mode = 'detail'
  modal.action = ''
  modal.entryId = Number(row.id)
  modal.entry = row
  modal.input = ''
  modal.error = ''
  modal.conflict = false
  modal.loadError = ''
  modal.submitting = false
  void loadDetail(Number(row.id))
}

async function loadDetail(entryId: number) {
  modal.loading = true
  modal.loadError = ''
  modal.error = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}`)
    if (!response.ok) {
      throw new Error(await readErrorDetail(response, '复核详情读取失败'))
    }
    modal.entry = (await response.json()) as Row
    modal.entryId = entryId
  } catch (error) {
    modal.loadError = error instanceof Error ? error.message : '复核详情读取失败'
  } finally {
    modal.loading = false
  }
}

async function refreshDetail() {
  if (modal.entryId === null) {
    return
  }
  await loadDetail(modal.entryId)
  modal.conflict = false
  modal.error = ''
}

function openAction(action: FormAction, row: Row) {
  openDetail(row)
  modal.mode = 'action'
  modal.action = action
  modal.input = ''
}

function switchToAction(action: FormAction) {
  modal.mode = 'action'
  modal.action = action
  modal.input = ''
  modal.error = ''
  modal.conflict = false
}

function switchToDetail() {
  modal.mode = 'detail'
  modal.action = ''
  modal.input = ''
  modal.error = ''
  modal.conflict = false
}

function closeModal() {
  if (modal.submitting) {
    return
  }
  modal.open = false
  modal.entry = null
  modal.entryId = null
}

async function startFromModal() {
  if (!modal.entry) {
    return
  }
  modal.submitting = true
  modal.error = ''
  try {
    const result = await postAction(modal.entry, '开始复核')
    if (!result.ok) {
      modal.error = result.message
      modal.conflict = result.status === 409
      return
    }
    flashSuccess(result.message)
    modal.open = false
    await reload()
    await loadStats()
  } catch (error) {
    modal.error = error instanceof Error ? error.message : '开始复核失败，请稍后重试'
  } finally {
    modal.submitting = false
  }
}

async function submitAction() {
  if (!modal.entry || !modal.action || modal.action === '开始复核') {
    return
  }
  const meta = ACTION_INPUT[modal.action]
  const text = modal.input.trim()
  if (!text) {
    modal.error = modal.action === '确认通过'
      ? '确认通过必须填写复核意见'
      : '发起重测必须填写差异说明'
    modal.conflict = false
    return
  }
  if (text.length > INPUT_MAX_LENGTH) {
    modal.error = `${meta.label}过长（最多 ${INPUT_MAX_LENGTH} 字，当前 ${text.length} 字），请精简后再提交`
    modal.conflict = false
    return
  }
  modal.submitting = true
  modal.error = ''
  try {
    const result = await postAction(modal.entry, modal.action, { [meta.field]: text })
    if (!result.ok) {
      modal.error = result.message
      modal.conflict = result.status === 409
      return
    }
    flashSuccess(result.message)
    modal.open = false
    await reload()
    await loadStats()
  } catch (error) {
    modal.error = error instanceof Error ? error.message : '复核操作提交失败，请稍后重试'
  } finally {
    modal.submitting = false
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>

<style scoped>
.state-cell {
  text-align: center;
  color: var(--muted);
  padding: 24px 12px;
}
.state-cell.is-error {
  color: #b42318;
}
.state-cell.is-error .btn {
  margin-left: 8px;
}
.empty-state {
  text-align: center;
  color: var(--muted);
  padding: 24px 12px;
}
.empty-state p {
  margin: 4px 0;
}
.empty-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}
.cell-clamp {
  max-width: 180px;
}
.cell-clamp > span {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  vertical-align: bottom;
}
.status-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  border: 1px solid var(--border);
}
.status-tag.is-pending {
  color: #b54708;
  background: #fffaeb;
  border-color: #fedf89;
}
.status-tag.is-doing {
  color: #175cd3;
  background: #eff8ff;
  border-color: #b2ddff;
}
.status-tag.is-passed {
  color: #027a48;
  background: #ecfdf3;
  border-color: #abefc6;
}
.status-tag.is-retest {
  color: #b42318;
  background: #fef3f2;
  border-color: #fda29b;
}
.success-text {
  color: #027a48;
}
.stat-error {
  margin: 4px 0 0;
  font-size: 12px;
  color: #b42318;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-card {
  width: 640px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-head h3 {
  margin: 0;
  font-size: 16px;
}
.modal-body {
  padding: 24px 0;
}
.detail-list {
  margin: 12px 0 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 20px;
}
.detail-item {
  display: flex;
  gap: 8px;
  margin: 0;
  font-size: 13px;
  border-bottom: 1px dashed var(--border);
  padding-bottom: 6px;
}
.detail-item dt {
  color: var(--muted);
  flex: 0 0 72px;
}
.detail-item dd {
  margin: 0;
  word-break: break-all;
}
.action-form {
  margin-top: 12px;
}
.action-field {
  display: block;
}
.action-field > span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.action-field textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  font: inherit;
}
.required-mark {
  color: #b42318;
  margin-left: 2px;
}
.input-hint {
  display: block;
  margin-top: 4px;
  color: var(--muted);
}
.input-hint.is-error {
  color: #b42318;
}
.modal-error {
  margin-bottom: 0;
}
.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 16px;
}
.btn.danger {
  color: #b42318;
  border-color: #fda29b;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
