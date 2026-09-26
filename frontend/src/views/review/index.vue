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
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
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
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="loadError" class="notice-panel error-panel">
      <span>{{ loadError }}</span>
      <button class="btn" type="button" @click="reload">重试</button>
    </div>

    <div v-if="conflictMessage" class="notice-panel conflict-panel">
      <span>{{ conflictMessage }}</span>
      <button class="btn" type="button" @click="resolveConflict">刷新列表后重试</button>
      <button class="btn ghost" type="button" @click="conflictMessage = ''">知道了</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length + 1" class="empty-state">复核记录加载中…</td>
        </tr>
        <template v-else>
          <tr v-for="row in rows" :key="String(row.id)">
            <td
              v-for="column in columns"
              :key="column"
              :class="{ 'cell-ellipsis': LONG_TEXT_FIELDS.includes(column) }"
              :title="LONG_TEXT_FIELDS.includes(column) ? String(row[column] ?? '') : undefined"
            >
              <button
                v-if="column === '复核编号'"
                class="link"
                type="button"
                @click="openDetail(row)"
              >
                {{ row[column] ?? '—' }}
              </button>
              <template v-else>{{ row[column] ?? '—' }}</template>
            </td>
            <td class="row-actions">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                :disabled="acting"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length && !loadError">
            <td :colspan="columns.length + 1" class="empty-state">
              <p>暂无{{ statusFilter ? `「${statusFilter}」的` : '' }}复核记录。</p>
              <p>
                可前往<router-link to="/result">检测结果</router-link>提交待复核结果，
                或点击右上角「登记复核记录」手动登记；确认筛选条件无误后也可以
                <button class="link" type="button" @click="reload">重新加载</button>。
              </p>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条结果复核记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 复核动作表单：确认通过必须填复核意见，发起重测必须填差异说明 -->
    <div v-if="actionDialog" class="modal-mask" @click.self="closeActionDialog">
      <div class="modal-card">
        <h3>{{ actionDialog.action }} · {{ actionDialog.row['复核编号'] }}</h3>
        <p class="modal-tip">
          {{ actionDialog.action === '确认通过' ? '确认通过前必须填写复核意见。' : '发起重测前必须填写差异说明，写清与初测结果的差异。' }}
        </p>
        <label v-if="actionDialog.action === '确认通过'" class="modal-field">
          <span>复核意见（必填，{{ opinionText.trim().length }}/{{ FIELD_LIMITS['复核意见'] }} 字）</span>
          <textarea
            v-model="opinionText"
            rows="3"
            :maxlength="FIELD_LIMITS['复核意见']"
            placeholder="填写复核意见"
          ></textarea>
        </label>
        <label v-if="actionDialog.action === '发起重测'" class="modal-field">
          <span>差异说明（必填，{{ diffText.trim().length }}/{{ FIELD_LIMITS['差异说明'] }} 字）</span>
          <textarea
            v-model="diffText"
            rows="3"
            :maxlength="FIELD_LIMITS['差异说明']"
            placeholder="说明与初测结果的差异"
          ></textarea>
        </label>
        <label class="modal-field">
          <span>复核人</span>
          <input v-model="reviewerText" placeholder="填写复核人姓名" />
        </label>
        <p v-if="actionError" class="error-text">{{ actionError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" :disabled="submitting" @click="submitAction">
            {{ submitting ? '提交中…' : '提交' }}
          </button>
          <button class="btn ghost" type="button" :disabled="submitting" @click="closeActionDialog">取消</button>
        </div>
      </div>
    </div>

    <!-- 复核记录详情：状态与列表、统计同源 -->
    <div v-if="detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card">
        <h3>复核记录详情</h3>
        <p v-if="detailLoading" class="modal-tip">详情加载中…</p>
        <div v-else-if="detailError" class="detail-error">
          <span class="error-text">{{ detailError }}</span>
          <button class="btn" type="button" @click="retryDetail">重试</button>
        </div>
        <dl v-else-if="detail" class="detail-grid">
          <template v-for="field in columns" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detail[field] ?? '—' }}</dd>
          </template>
        </dl>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type StatItem = { label: string; value: number }

const ENDPOINT = '/api/review'
const columns = ["复核编号", "关联结果", "复核项目", "复核人", "复核意见", "复核时间", "差异说明", "复核状态"]
const actions = ["开始复核", "确认通过", "发起重测"]
const statuses = ["待复核", "复核中", "已通过", "需重测"]
// 长文本字段：列表里截断显示，提交时限制长度，避免把表格撑坏
const LONG_TEXT_FIELDS = ["复核意见", "差异说明"]
const FIELD_LIMITS: Record<string, number> = { 复核意见: 200, 差异说明: 200 }

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const acting = ref(false)
const loadError = ref('')
const errorMessage = ref('')
const conflictMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const stats = ref<StatItem[]>([
  { label: '待复核记录', value: 0 },
  { label: '本月通过数', value: 0 },
  { label: '需重测项数', value: 0 },
])

const actionDialog = ref<{ action: string; row: Row } | null>(null)
const opinionText = ref('')
const diffText = ref('')
const reviewerText = ref('')
const actionError = ref('')
const submitting = ref(false)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detail = ref<Row | null>(null)
const detailId = ref<number | null>(null)

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

function runAction(action: string, row: Row) {
  conflictMessage.value = ''
  errorMessage.value = ''
  if (action === '开始复核') {
    void submitActionRequest(action, row, {})
    return
  }
  opinionText.value = ''
  diffText.value = ''
  reviewerText.value = ''
  actionError.value = ''
  actionDialog.value = { action, row }
}

function closeActionDialog() {
  if (submitting.value) return
  actionDialog.value = null
}

async function submitAction() {
  const dialog = actionDialog.value
  if (!dialog) return
  const extra: Record<string, string> = {}
  if (dialog.action === '确认通过') {
    const opinion = opinionText.value.trim()
    if (!opinion) {
      actionError.value = '确认通过前必须填写复核意见'
      return
    }
    if (opinion.length > FIELD_LIMITS['复核意见']) {
      actionError.value = `复核意见最多 ${FIELD_LIMITS['复核意见']} 字，请精简后再提交`
      return
    }
    extra['复核意见'] = opinion
  }
  if (dialog.action === '发起重测') {
    const diff = diffText.value.trim()
    if (!diff) {
      actionError.value = '发起重测前必须填写差异说明'
      return
    }
    if (diff.length > FIELD_LIMITS['差异说明']) {
      actionError.value = `差异说明最多 ${FIELD_LIMITS['差异说明']} 字，请精简后再提交`
      return
    }
    extra['差异说明'] = diff
  }
  const reviewer = reviewerText.value.trim()
  if (reviewer) {
    extra['复核人'] = reviewer
  }
  submitting.value = true
  actionError.value = ''
  const ok = await submitActionRequest(dialog.action, dialog.row, extra)
  submitting.value = false
  if (ok) {
    actionDialog.value = null
  }
}

async function submitActionRequest(
  action: string,
  row: Row,
  extra: Record<string, string>,
): Promise<boolean> {
  acting.value = true
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, version: row.version ?? 0, ...extra } }),
    })
    if (response.status === 409) {
      const payload = await response.json().catch(() => null)
      conflictMessage.value = payload?.detail ?? '这条复核记录刚被其他人更新，请刷新列表后重试'
      actionDialog.value = null
      return false
    }
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      const message = payload?.message ?? payload?.detail ?? `结果复核动作未生效（接口返回 ${response.status}）`
      if (actionDialog.value) {
        actionError.value = message
      } else {
        errorMessage.value = message
      }
      return false
    }
    await reload()
    return true
  } catch (error) {
    const message = error instanceof Error ? error.message : '结果复核操作失败，请稍后重试'
    if (actionDialog.value) {
      actionError.value = message
    } else {
      errorMessage.value = message
    }
    return false
  } finally {
    acting.value = false
  }
}

async function resolveConflict() {
  conflictMessage.value = ''
  await reload()
}

function openDetail(row: Row) {
  detailVisible.value = true
  void loadDetail(Number(row.id))
}

async function loadDetail(id: number) {
  detailId.value = id
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.detail ?? `复核记录详情读取失败（接口返回 ${response.status}）`)
    }
    detail.value = payload
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '复核记录详情读取失败，请稍后重试'
  } finally {
    detailLoading.value = false
  }
}

function retryDetail() {
  if (detailId.value != null) {
    void loadDetail(detailId.value)
  }
}

function closeDetail() {
  detailVisible.value = false
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
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error(`复核记录列表读取失败（接口返回 ${response.status}）`)
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '复核记录列表读取失败，请检查网络后重试'
  } finally {
    loading.value = false
  }
  void reloadStats()
}

async function reloadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}`)
    }
    const payload = await response.json()
    if (Array.isArray(payload.items)) {
      stats.value = payload.items
    }
  } catch {
    // 统计卡片读取失败不阻塞列表，保留上一次数据
  }
}

onMounted(reload)
</script>

<style scoped>
.notice-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.error-panel { border: 1px solid #f3c2c2; background: #fef3f2; color: #b42318; }
.conflict-panel { border: 1px solid #f5d08a; background: #fffaeb; color: #93370d; }
.cell-ellipsis {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty-state p { margin: 4px 0; }
select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 13px;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.modal-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  width: 420px;
  max-width: 90vw;
}
.modal-card h3 { margin: 0 0 8px; font-size: 15px; }
.modal-tip { color: var(--muted); font-size: 12px; margin: 0 0 10px; }
.modal-field { display: block; margin-bottom: 10px; }
.modal-field span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.modal-field textarea,
.modal-field input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  font-family: inherit;
}
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; word-break: break-all; }
.detail-error { display: flex; align-items: center; gap: 12px; }
</style>
