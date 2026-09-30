<template>
  <div>
    <h2 class="section-title">管理后台</h2>
    <p class="section-sub">平台运营总览、用户管理、面试场次与简历分析数据。</p>

    <!-- 统计卡片 -->
    <div class="stat-grid" v-if="stats">
      <div class="mw-card stat-card">
        <div class="s-num">{{ stats.total_users }}</div>
        <div class="s-label">注册用户 <span class="s-sub">今日 +{{ stats.new_users_today }}</span></div>
      </div>
      <div class="mw-card stat-card">
        <div class="s-num">{{ stats.total_sessions }}</div>
        <div class="s-label">面试场次 <span class="s-sub">完成 {{ stats.done_sessions }}</span></div>
      </div>
      <div class="mw-card stat-card">
        <div class="s-num">{{ stats.avg_score }}</div>
        <div class="s-label">全站平均分 <span class="s-sub">近7天 {{ stats.week_practices }} 场</span></div>
      </div>
      <div class="mw-card stat-card">
        <div class="s-num">{{ stats.total_resumes }}</div>
        <div class="s-label">上传简历</div>
      </div>
    </div>
    <a-skeleton v-else active :paragraph="{ rows: 3 }" />

    <!-- 趋势 + 形式分布 -->
    <div class="chart-row" v-if="stats">
      <div class="mw-card chart-card">
        <div class="card-title">近 7 天练习趋势</div>
        <div class="trend-bars">
          <div v-for="t in stats?.trend" :key="t.date" class="t-col">
            <div class="t-bar" :style="{ height: barH(t.count) + 'px' }"></div>
            <div class="t-val">{{ t.count }}</div>
            <div class="t-date">{{ t.date }}</div>
          </div>
        </div>
      </div>
      <div class="mw-card chart-card">
        <div class="card-title">面试形式分布</div>
        <div class="dist-list">
          <div v-for="d in stats?.form_distribution" :key="d.name" class="dist-row">
            <span class="d-name">{{ d.name }}</span>
            <div class="d-bar-shell"><span :style="{ width: distPct(d.value) + '%' }"></span></div>
            <span class="d-val">{{ d.value }}</span>
          </div>
          <a-empty v-if="!stats?.form_distribution?.length" description="暂无数据" />
        </div>
      </div>
    </div>

    <!-- 数据 Tabs -->
    <div class="mw-card" style="margin-top:18px;">
      <a-tabs v-model:activeKey="tab">
        <!-- 用户 -->
        <a-tab-pane key="users" :tab="`用户（${users.total}）`">
          <div class="toolbar">
            <a-input-search v-model:value="userKw" placeholder="搜索昵称/手机号" style="max-width:280px;" @search="loadUsers" allow-clear />
            <a-button @click="loadUsers">刷新</a-button>
            <a-button type="primary" @click="exportUsers" style="margin-left:auto">导出 CSV</a-button>
          </div>
          <a-table :data-source="users.list" :columns="userCols" row-key="id" :pagination="false" size="middle" :loading="usersLoading">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'role'">
                <a-tag :color="record.role === 'admin' ? 'red' : 'default'">{{ record.role === 'admin' ? '管理员' : '用户' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'avg_score'">
                <span :style="{ color: record.avg_score >= 80 ? '#2FA36B' : record.avg_score >= 70 ? '' : '#E8912D' }">
                  {{ record.avg_score || '—' }}
                </span>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status === 'active' ? 'green' : 'orange'">{{ record.status === 'active' ? '正常' : '已禁用' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'op'">
                <a-space>
                  <a-button size="small" @click="openUser(record)">详情</a-button>
                  <a-button size="small" :type="record.status === 'active' ? 'default' : 'primary'"
                    @click="toggleUser(record)">
                    {{ record.status === 'active' ? '禁用' : '启用' }}
                  </a-button>
                </a-space>
              </template>
            </template>
          </a-table>
          <div class="pager">
            <a-button size="small" :disabled="users.page <= 1" @click="users.page--; loadUsers()">上一页</a-button>
            <span>第 {{ users.page }} 页</span>
            <a-button size="small" :disabled="users.page * users.page_size >= users.total" @click="users.page++; loadUsers()">下一页</a-button>
          </div>
        </a-tab-pane>

        <!-- 面试回放 -->
        <a-tab-pane key="records" :tab="`面试回放（${records.total}）`">
          <div class="toolbar records-toolbar">
            <a-segmented
              v-model:value="recordFormType"
              :options="formOptions"
              @change="reloadRecords"
            />
            <a-input-search
              v-model:value="recordKw"
              placeholder="按用户/手机号/套题搜索"
              style="max-width:280px;"
              @search="reloadRecords"
              allow-clear
            />
            <a-button @click="reloadRecords">刷新</a-button>
            <a-button @click="exportRecords" style="margin-left:auto">导出 CSV</a-button>
          </div>

          <div class="record-stats" v-if="records.list.length">
            <div class="rs-item"><span class="rs-num">{{ records.total }}</span><span class="rs-label">总场次</span></div>
            <div class="rs-item"><span class="rs-num">{{ answeredCount }}</span><span class="rs-label">已作答</span></div>
            <div class="rs-item"><span class="rs-num">{{ audioCount }}</span><span class="rs-label">含录音</span></div>
            <div class="rs-item"><span class="rs-num">{{ videoCount }}</span><span class="rs-label">含录像</span></div>
          </div>

          <a-table :data-source="records.list" :columns="recordCols" row-key="id" :pagination="false" size="middle" :loading="recordsLoading">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'form_type'">
                <a-tag :color="{ structured: 'blue', group: 'purple', semi: 'cyan' }[record.form_type]">
                  {{ record.form_label }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'total_score'">
                {{ record.total_score ? record.total_score.toFixed(1) : '—' }}
              </template>
              <template v-else-if="column.key === 'duration'">
                {{ fmtMs(record.duration_ms) }}
              </template>
              <template v-else-if="column.key === 'saves'">
                <a-tag color="green" v-if="record.answered_count">转写 ✓</a-tag>
                <a-tag :color="record.has_audio ? 'cyan' : 'default'">录音 {{ record.has_audio ? '✓' : '—' }}</a-tag>
                <a-tag :color="record.has_video ? 'purple' : 'default'">录像 {{ record.has_video ? '✓' : '—' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'op'">
                <a-button size="small" type="primary" :disabled="!record.answered_count" @click="openReplay(record)">
                  打开回放
                </a-button>
              </template>
            </template>
          </a-table>
          <div class="pager">
            <a-button size="small" :disabled="records.page <= 1" @click="records.page--; reloadRecords()">上一页</a-button>
            <span>第 {{ records.page }} 页</span>
            <a-button size="small" :disabled="records.page * records.page_size >= records.total" @click="records.page++; reloadRecords()">下一页</a-button>
          </div>
        </a-tab-pane>

        <!-- 面试场次 -->
        <a-tab-pane key="sessions" :tab="`面试场次（${sessions.total}）`">
          <div class="toolbar">
            <a-input-search v-model:value="sessionKw" placeholder="搜索用户/手机号/套题" style="max-width:280px;" @search="loadSessions" allow-clear />
            <a-range-picker v-model:value="sessionRange" @change="loadSessions" style="margin-left:8px;" />
            <a-button @click="loadSessions">刷新</a-button>
            <a-button type="primary" @click="exportSessions" style="margin-left:auto">导出 CSV</a-button>
          </div>
          <a-table :data-source="sessions.list" :columns="sessionCols" row-key="id" :pagination="false" size="middle" :loading="sessionsLoading">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'form_type'">
                <a-tag :color="{ structured: 'blue', group: 'purple', semi: 'cyan' }[record.form_type]">
                  {{ record.form_label }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status === 'done' ? 'green' : 'default'">{{ statusLabel(record.status) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'total_score'">
                {{ record.total_score ? record.total_score.toFixed(1) : '—' }}
              </template>
            </template>
          </a-table>
          <div class="pager">
            <a-button size="small" :disabled="sessions.page <= 1" @click="sessions.page--; loadSessions()">上一页</a-button>
            <span>第 {{ sessions.page }} 页</span>
            <a-button size="small" :disabled="sessions.page * sessions.page_size >= sessions.total" @click="sessions.page++; loadSessions()">下一页</a-button>
          </div>
        </a-tab-pane>

        <!-- 简历分析 -->
        <a-tab-pane key="resumes" :tab="`简历分析（${resumes.total}）`">
          <div class="toolbar">
            <a-input-search v-model:value="resumeKw" placeholder="搜索用户/手机号/文件名" style="max-width:280px;" @search="loadResumes" allow-clear />
            <a-range-picker v-model:value="resumeRange" @change="loadResumes" style="margin-left:8px;" />
            <a-button @click="loadResumes">刷新</a-button>
            <a-button type="primary" @click="exportResumes" style="margin-left:auto">导出 CSV</a-button>
          </div>
          <a-table :data-source="resumes.list" :columns="resumeCols" row-key="id" :pagination="false" size="middle" :loading="resumesLoading">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'engine'">
                <a-tag :color="record.engine === 'deepseek' ? 'blue' : 'default'">{{ record.engine === 'deepseek' ? 'AI' : '规则' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'skills'">
                <a-tag v-for="s in (record.skills || []).slice(0, 3)" :key="s" style="margin-bottom:2px;">{{ s }}</a-tag>
              </template>
              <template v-else-if="column.key === 'op'">
                <a-button size="small" @click="openResume(record)">详情</a-button>
              </template>
            </template>
          </a-table>
          <div class="pager">
            <a-button size="small" :disabled="resumes.page <= 1" @click="resumes.page--; loadResumes()">上一页</a-button>
            <span>第 {{ resumes.page }} 页</span>
            <a-button size="small" :disabled="resumes.page * resumes.page_size >= resumes.total" @click="resumes.page++; loadResumes()">下一页</a-button>
          </div>
        </a-tab-pane>

        <!-- 内容配置 -->
        <a-tab-pane key="content" tab="内容配置">
          <a-tabs v-model:activeKey="contentTab" type="card" class="sub-tabs">
            <!-- 套题管理 -->
            <a-tab-pane key="sets" tab="套题管理">
              <div class="toolbar">
                <a-button type="primary" @click="openSetForm()">新建套题</a-button>
                <a-button @click="loadSets">刷新</a-button>
                <span class="muted" style="margin-left:auto">共 {{ sets.list.length }} 套</span>
              </div>
              <a-table :data-source="sets.list" :columns="setCols" row-key="id" :pagination="false" size="middle" :loading="setsLoading">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'form_type'">
                    <a-tag :color="{ structured: 'blue', group: 'purple', semi: 'cyan' }[record.form_type]">{{ formLabel(record.form_type) }}</a-tag>
                  </template>
                  <template v-else-if="column.key === 'difficulty'">{{ diffLabel(record.difficulty) }}</template>
                  <template v-else-if="column.key === 'status'">
                    <a-tag :color="record.is_published ? 'green' : 'default'">{{ record.is_published ? '已上架' : '已下架' }}</a-tag>
                  </template>
                  <template v-else-if="column.key === 'op'">
                    <a-space>
                      <a-button size="small" @click="openQuestions(record)">题目</a-button>
                      <a-button size="small" @click="openSetForm(record)">编辑</a-button>
                      <a-button size="small" :type="record.is_published ? 'default' : 'primary'" @click="togglePublish(record)">
                        {{ record.is_published ? '下架' : '上架' }}
                      </a-button>
                      <a-popconfirm title="删除套题会同时删除其下所有题目，确认？" @confirm="delSet(record)">
                        <a-button size="small" danger>删除</a-button>
                      </a-popconfirm>
                    </a-space>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>

            <!-- 题目管理 -->
            <a-tab-pane key="questions" tab="题目管理">
              <div class="toolbar">
                <a-select v-model:value="qSelectedSetId" style="width:320px" placeholder="选择套题" :options="setOptions" @change="loadQuestions" />
                <a-button type="primary" :disabled="!qSelectedSetId" @click="openQForm()">新建题目</a-button>
                <a-button :disabled="!qSelectedSetId" @click="loadQuestions">刷新</a-button>
              </div>
              <a-empty v-if="!qSelectedSetId" description="请先在上方选择一套题" />
              <template v-else>
                <a-table :data-source="questions.list" :columns="qCols" row-key="id" :pagination="false" size="middle" :loading="questionsLoading">
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'seq'">#{{ record.seq }}</template>
                    <template v-else-if="column.key === 'content'"><span class="cell-clamp">{{ record.content }}</span></template>
                    <template v-else-if="column.key === 'op'">
                      <a-space>
                        <a-button size="small" @click="openQForm(record)">编辑</a-button>
                        <a-popconfirm title="确认删除题目？" @confirm="delQuestion(record)">
                          <a-button size="small" danger>删除</a-button>
                        </a-popconfirm>
                      </a-space>
                    </template>
                  </template>
                </a-table>
              </template>
            </a-tab-pane>

            <!-- 群面虚拟候选人人设 -->
            <a-tab-pane key="personas" tab="群面人设">
              <div class="toolbar">
                <a-button type="primary" @click="openPersonaForm()">新建人设</a-button>
                <a-button @click="loadPersonas">刷新</a-button>
                <span class="muted" style="margin-left:auto">共 {{ personas.list.length }} 个</span>
              </div>
              <a-table :data-source="personas.list" :columns="personaCols" row-key="id" :pagination="false" size="middle" :loading="personasLoading">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'name'">
                    <span class="persona-dot" :style="{ background: record.color }"></span>{{ record.name }}
                  </template>
                  <template v-else-if="column.key === 'scope'">
                    <a-tag :color="record.set_id ? 'blue' : 'default'">{{ record.set_id ? '套题专属' : '通用' }}</a-tag>
                  </template>
                  <template v-else-if="column.key === 'op'">
                    <a-space>
                      <a-button size="small" @click="openPersonaForm(record)">编辑</a-button>
                      <a-popconfirm title="确认删除该人设？" @confirm="delPersona(record)">
                        <a-button size="small" danger>删除</a-button>
                      </a-popconfirm>
                    </a-space>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>
          </a-tabs>
        </a-tab-pane>

        <!-- 可观测性：成功率 / 耗时 / Token 成本 / 上下文命中 / 量化评测 -->
        <a-tab-pane key="obs" tab="可观测性">
          <a-space direction="vertical" style="width:100%" size="middle">
            <a-card size="small">
              <template #title>
                <a-space>
                  <span>LLM 调用指标</span>
                  <a-select v-model:value="obsHours" size="small" style="width:110px" @change="loadObs">
                    <a-select-option :value="6">近 6 小时</a-select-option>
                    <a-select-option :value="24">近 24 小时</a-select-option>
                    <a-select-option :value="72">近 3 天</a-select-option>
                    <a-select-option :value="168">近 7 天</a-select-option>
                  </a-select>
                  <a-button size="small" :loading="obsLoading" @click="loadObs">刷新</a-button>
                </a-space>
              </template>
              <a-row :gutter="12">
                <a-col :span="6">
                  <a-statistic title="总调用" :value="obs?.overview?.total_calls ?? 0" />
                </a-col>
                <a-col :span="6">
                  <a-statistic title="成功率" :value="pct(obs?.overview?.success_rate)"
                               :value-style="{ color: (obs?.overview?.success_rate ?? 1) >= 0.95 ? '#3f8600' : '#cf1322' }" />
                </a-col>
                <a-col :span="6">
                  <a-statistic title="P95 耗时" :value="obs?.overview?.p95_latency_ms ?? 0" suffix="ms" />
                </a-col>
                <a-col :span="6">
                  <a-statistic title="累计成本" :value="obs?.overview?.cost_cny ?? 0"
                               :precision="4" prefix="¥" />
                </a-col>
              </a-row>
              <div class="muted" style="margin-top:6px">
                平均耗时 {{ obs?.overview?.avg_latency_ms ?? 0 }}ms ·
                Token 合计 {{ obs?.overview?.total_tokens ?? 0 }}
                （入 {{ obs?.overview?.prompt_tokens ?? 0 }} / 出 {{ obs?.overview?.completion_tokens ?? 0 }}）·
                单次均价 ¥{{ obs?.overview?.avg_cost_per_call ?? 0 }}
              </div>
            </a-card>

            <a-card size="small" title="分场景统计">
              <a-table :data-source="obs?.by_scene || []" :columns="obsSceneCols" row-key="scene"
                       :pagination="false" size="small" :loading="obsLoading" />
            </a-card>

            <a-card size="small" title="上下文工程效果（Phase 3 落库指标）">
              <div v-if="obsCtx && obsCtx.sample_count">
                <a-row :gutter="12">
                  <a-col :span="6"><a-statistic title="样本数" :value="obsCtx.sample_count" /></a-col>
                  <a-col :span="6"><a-statistic title="平均上下文 Token" :value="obsCtx.avg_context_tokens ?? 0" /></a-col>
                  <a-col :span="6"><a-statistic title="峰值 Token" :value="obsCtx.max_context_tokens ?? 0" /></a-col>
                  <a-col :span="6"><a-statistic title="超预算率" :value="pct(obsCtx.over_budget_rate)" /></a-col>
                </a-row>
                <div class="muted" style="margin-top:6px">
                  各层纳入率：
                  <a-tag v-for="(v, k) in (obsCtx.layer_hit_rate || {})" :key="k">{{ k }} {{ pct(v) }}</a-tag>
                </div>
              </div>
              <div v-else class="muted">{{ obsCtx?.note || '暂无数据' }}</div>
            </a-card>

            <a-card size="small">
              <template #title>
                <a-space>
                  <span>量化评测</span>
                  <a-select v-model:value="evalRepeat" size="small" style="width:110px">
                    <a-select-option :value="1">重复 1 次</a-select-option>
                    <a-select-option :value="3">重复 3 次</a-select-option>
                    <a-select-option :value="5">重复 5 次</a-select-option>
                  </a-select>
                  <a-switch v-model:checked="evalOffline" checked-children="离线" un-checked-children="真实" />
                  <a-button type="primary" size="small" :loading="evalRunning" @click="runEval">跑一轮</a-button>
                </a-space>
              </template>
              <div v-if="evalLatest">
                <a-row :gutter="12">
                  <a-col :span="6"><a-statistic title="成功率" :value="pct(evalLatest.success_rate)" /></a-col>
                  <a-col :span="6"><a-statistic title="评分标准差" :value="evalLatest.score_std ?? 0" :precision="3" /></a-col>
                  <a-col :span="6"><a-statistic title="最大极差" :value="evalLatest.score_range ?? 0" :precision="2" /></a-col>
                  <a-col :span="6"><a-statistic title="P95 耗时" :value="evalLatest.p95_latency_ms ?? 0" suffix="ms" /></a-col>
                </a-row>
                <div class="muted" style="margin-top:6px">
                  {{ evalLatest.name }} · 样本 {{ evalLatest.sample_count }} × 重复 {{ evalLatest.repeat }} ·
                  Token {{ evalLatest.total_tokens }} · 成本 ¥{{ evalLatest.cost_cny }}
                </div>
                <a-table v-if="evalLatest.report?.per_sample" :data-source="evalLatest.report.per_sample"
                         :columns="evalSampleCols" row-key="sample_idx" :pagination="false" size="small"
                         style="margin-top:8px" />
                <div v-if="evalOffline" class="muted" style="margin-top:6px">
                  离线模式使用启发式假 LLM：绝对分值不代表真实模型水平，本轮只验证流水线正确性与评分稳定性。
                </div>
              </div>
              <div v-else class="muted">还没有评测记录，点「跑一轮」生成。</div>
            </a-card>
          </a-space>
        </a-tab-pane>

        <!-- 人工审批卡点：高危内容变更 草稿 → 待审 → 复核 -->
        <a-tab-pane key="approval" :tab="`审批卡点（${pendingCount}）`">
          <a-space direction="vertical" style="width:100%" size="middle">
            <a-card size="small">
              <template #title>
                <a-space>
                  <span>待人工复核</span>
                  <a-select v-model:value="apprStatus" size="small" style="width:120px" @change="loadApprovals">
                    <a-select-option value="pending">待审</a-select-option>
                    <a-select-option value="approved">已批准</a-select-option>
                    <a-select-option value="rejected">已驳回</a-select-option>
                    <a-select-option value="">全部</a-select-option>
                  </a-select>
                  <a-button size="small" :loading="apprLoading" @click="loadApprovals">刷新</a-button>
                </a-space>
              </template>
              <div v-if="!approvals.length" class="muted">没有待复核的变更。</div>
              <a-table v-else :data-source="approvals" :columns="approvalCols" row-key="id"
                       :pagination="false" size="small" :loading="apprLoading">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'risk'">
                    <a-tag :color="record.risk === 'high' ? 'red' : record.risk === 'medium' ? 'orange' : 'blue'">
                      {{ record.risk }}
                    </a-tag>
                  </template>
                  <template v-else-if="column.key === 'status'">
                    <a-tag :color="{ pending: 'gold', approved: 'green', rejected: 'red', cancelled: 'default' }[record.status]">
                      {{ { pending: '待审', approved: '已批准', rejected: '已驳回', cancelled: '已撤回' }[record.status] }}
                    </a-tag>
                  </template>
                  <template v-else-if="column.key === 'action'">
                    {{ { create: '新增', update: '修改', delete: '删除', publish: '上架', unpublish: '下架' }[record.action] || record.action }}
                  </template>
                  <template v-else-if="column.key === 'ops'">
                    <a-space v-if="record.status === 'pending'">
                      <a-button type="link" size="small" @click="openApproval(record)">详情</a-button>
                      <a-button type="link" size="small" @click="askReview(record, true)">批准</a-button>
                      <a-button type="link" size="small" danger @click="askReview(record, false)">驳回</a-button>
                    </a-space>
                    <a-button v-else type="link" size="small" @click="openApproval(record)">查看</a-button>
                  </template>
                </template>
              </a-table>
              <div class="muted" style="margin-top:8px">
                高危变更（删除 / 上下架）在后台操作后不会立即生效，而是冻结为审批单；
                批准后才会落库，驳回则完全不产生变更。全过程留审计并绑定 trace_id。
              </div>
            </a-card>
          </a-space>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 面试回放弹窗 -->
    <ReplayModal v-model:open="replayOpen" :sessionId="replaySessionId" />

    <!-- 用户详情抽屉 -->
    <a-drawer v-model:open="userDrawer" title="用户详情" width="580" @close="userDetail = null">
      <a-spin v-if="!userDetail" />
      <template v-else>
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="ID">{{ userDetail.user.id }}</a-descriptions-item>
          <a-descriptions-item label="手机号">{{ userDetail.user.phone }}</a-descriptions-item>
          <a-descriptions-item label="昵称">{{ userDetail.user.nickname }}</a-descriptions-item>
          <a-descriptions-item label="目标岗位">{{ userDetail.user.target_position || '—' }}</a-descriptions-item>
          <a-descriptions-item label="角色">{{ userDetail.user.role }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ userDetail.user.status }}</a-descriptions-item>
          <a-descriptions-item label="练习次数">{{ userDetail.user.practice_count }}</a-descriptions-item>
          <a-descriptions-item label="平均分">{{ userDetail.user.avg_score }}</a-descriptions-item>
          <a-descriptions-item label="简历数">{{ userDetail.user.resume_count }}</a-descriptions-item>
          <a-descriptions-item label="注册时间">{{ userDetail.user.created_at }}</a-descriptions-item>
          <a-descriptions-item label="最近登录">{{ userDetail.user.last_login_at }}</a-descriptions-item>
        </a-descriptions>

        <h4 class="drawer-h">练习历史（{{ userDetail.practices.length }}）</h4>
        <a-table :data-source="userDetail.practices" :columns="practiceCols" row-key="practiced_at" size="small" :pagination="false" />

        <h4 class="drawer-h">简历（{{ userDetail.resumes.length }}）</h4>
        <a-table :data-source="userDetail.resumes" :columns="resumeMiniCols" row-key="id" size="small" :pagination="false" />

        <h4 class="drawer-h">面试场次（{{ userDetail.sessions.length }}）</h4>
        <a-table :data-source="userDetail.sessions" :columns="sessionMiniCols" row-key="id" size="small" :pagination="false" />
      </template>
    </a-drawer>

    <!-- 简历详情抽屉 -->
    <a-drawer v-model:open="resumeDrawer" title="简历详情" width="620" @close="resumeDetail = null">
      <a-spin v-if="!resumeDetail" />
      <template v-else>
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="ID">{{ resumeDetail.id }}</a-descriptions-item>
          <a-descriptions-item label="用户">{{ resumeDetail.user_name }}</a-descriptions-item>
          <a-descriptions-item label="文件">{{ resumeDetail.filename }}</a-descriptions-item>
          <a-descriptions-item label="引擎">{{ resumeDetail.engine }}</a-descriptions-item>
          <a-descriptions-item label="候选人">{{ resumeDetail.candidate_name || '—' }}</a-descriptions-item>
          <a-descriptions-item label="目标岗位">{{ resumeDetail.target_position || '—' }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ resumeDetail.status }}</a-descriptions-item>
          <a-descriptions-item label="上传时间">{{ resumeDetail.created_at }}</a-descriptions-item>
        </a-descriptions>
        <h4 class="drawer-h">技能</h4>
        <a-space wrap>
          <a-tag v-for="s in (resumeDetail.skills || [])" :key="s">{{ s }}</a-tag>
          <span v-if="!resumeDetail.skills || !resumeDetail.skills.length" class="muted">无</span>
        </a-space>
        <h4 class="drawer-h">解析全文（JSON）</h4>
        <pre class="json-box">{{ JSON.stringify(resumeDetail.parsed, null, 2) }}</pre>
      </template>
    </a-drawer>

    <!-- 套题编辑抽屉 -->
    <a-drawer v-model:open="setDrawer" :title="setForm.id ? '编辑套题' : '新建套题'" width="560" @close="setForm.id = null">
      <a-form layout="vertical">
        <a-form-item label="套题名称">
          <a-input v-model:value="setForm.name" placeholder="如：互联网产品经理 · 8 题" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item label="行业"><a-input v-model:value="setForm.industry" placeholder="如：互联网" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="岗位类型"><a-input v-model:value="setForm.position_type" placeholder="如：产品" /></a-form-item></a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item label="面试形式"><a-select v-model:value="setForm.form_type" :options="formTypeOptions" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="难度"><a-select v-model:value="setForm.difficulty" :options="diffOptions" /></a-form-item></a-col>
        </a-row>
        <a-form-item label="简介"><a-textarea v-model:value="setForm.description" :rows="3" /></a-form-item>
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item label="预计时长（分钟）"><a-input-number v-model:value="setForm.est_minutes" :min="0" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="匹配度"><a-input-number v-model:value="setForm.match_score" :min="0" :max="100" :step="0.1" style="width:100%" /></a-form-item></a-col>
        </a-row>
        <a-form-item label="是否上架">
          <a-switch :checked="setForm.is_published === 1" @change="(v) => setForm.is_published = v ? 1 : 0"
            checked-children="上架" un-checked-children="下架" />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="setDrawer = false">取消</a-button>
          <a-button type="primary" :loading="saving" @click="saveSet">保存</a-button>
        </a-space>
      </template>
    </a-drawer>

    <!-- 题目编辑弹窗 -->
    <a-modal v-model:open="qModal" :title="qForm.id ? '编辑题目' : '新建题目'" width="660"
      :confirm-loading="saving" @ok="saveQuestion">
      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="8"><a-form-item label="序号（0=自动追加）"><a-input-number v-model:value="qForm.seq" :min="0" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="形式"><a-select v-model:value="qForm.form_type" :options="formTypeOptions" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="难度"><a-select v-model:value="qForm.difficulty" :options="diffOptions" /></a-form-item></a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item label="类别"><a-input v-model:value="qForm.category" placeholder="如：专业题" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="考察维度"><a-input v-model:value="qForm.dimension" placeholder="如：专业深度" /></a-form-item></a-col>
        </a-row>
        <a-form-item label="题目内容"><a-textarea v-model:value="qForm.content" :rows="4" /></a-form-item>
        <a-form-item>
          <template #label>
            <span>参考答案</span>
            <a-button size="small" type="link" :loading="aiGenLoading" :disabled="!qForm.id"
              style="float:right; padding-right:0" @click="aiGenRefAnswer">AI 生成（需复核）</a-button>
          </template>
          <a-textarea v-model:value="qForm.ref_answer" :rows="3" placeholder="可点右侧「AI 生成」由大模型起草，提交后进入人工复核，批准才生效" />
        </a-form-item>
        <a-form-item label="答题时限（秒）"><a-input-number v-model:value="qForm.time_limit_s" :min="10" style="width:160px" /></a-form-item>
      </a-form>
    </a-modal>

    <!-- 群面人设编辑抽屉 -->
    <a-drawer v-model:open="personaDrawer" :title="personaForm.id ? '编辑人设' : '新建人设'" width="620" @close="personaForm.id = null">
      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item label="姓名"><a-input v-model:value="personaForm.name" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="风格标签"><a-input v-model:value="personaForm.style" placeholder="如：激进派" /></a-form-item></a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item label="主题色">
            <a-input v-model:value="personaForm.color" style="width:140px">
              <template #addonBefore><span class="persona-dot" :style="{ background: personaForm.color }"></span></template>
            </a-input>
          </a-form-item></a-col>
          <a-col :span="12"><a-form-item label="抢话倾向（1-5）"><a-slider v-model:value="personaForm.aggressiveness" :min="1" :max="5" /></a-form-item></a-col>
        </a-row>
        <a-form-item label="适用范围"><a-select v-model:value="personaForm.set_id" :options="personaScopeOptions" /></a-form-item>
        <a-form-item label="人设简介"><a-textarea v-model:value="personaForm.bio" :rows="2" /></a-form-item>
        <a-form-item label="个人陈述模板（每行一条）"><a-textarea v-model:value="personaForm.openings" :rows="3" /></a-form-item>
        <a-form-item label="自由讨论反驳模板（每行一条）"><a-textarea v-model:value="personaForm.rebuttals" :rows="4" /></a-form-item>
        <a-form-item label="总结陈词模板（每行一条）"><a-textarea v-model:value="personaForm.summaries" :rows="3" /></a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="personaDrawer = false">取消</a-button>
          <a-button type="primary" :loading="saving" @click="savePersona">保存</a-button>
        </a-space>
      </template>
    </a-drawer>

    <!-- 审批单详情：看清「要改的是什么」再拍板 -->
    <a-drawer v-model:open="apprDrawer" title="审批单详情" width="620">
      <template v-if="apprDetail">
        <a-descriptions :column="2" bordered size="small" style="margin-bottom:12px">
          <a-descriptions-item label="审批单号">{{ apprDetail.id }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="{ pending: 'gold', approved: 'green', rejected: 'red', cancelled: 'default' }[apprDetail.status]">
              {{ { pending: '待审', approved: '已批准', rejected: '已驳回', cancelled: '已撤回' }[apprDetail.status] }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="变更对象">{{ apprDetail.target_type }} #{{ apprDetail.target_id || '-' }}</a-descriptions-item>
          <a-descriptions-item label="动作">
            {{ { create: '新增', update: '修改', delete: '删除', publish: '上架', unpublish: '下架' }[apprDetail.action] || apprDetail.action }}
          </a-descriptions-item>
          <a-descriptions-item label="风险等级">
            <a-tag :color="apprDetail.risk === 'high' ? 'red' : 'orange'">{{ apprDetail.risk }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="提交人">#{{ apprDetail.submitter_id }}</a-descriptions-item>
          <a-descriptions-item label="提交时间">{{ apprDetail.created_at }}</a-descriptions-item>
          <a-descriptions-item label="链路 trace">{{ apprDetail.trace_id || '-' }}</a-descriptions-item>
        </a-descriptions>

        <h4 class="drawer-h">变更说明</h4>
        <div class="appr-summary">{{ apprDetail.summary || '（无）' }}</div>

        <h4 class="drawer-h">变更前快照（复核依据）</h4>
        <pre class="json-box">{{ prettyJSON(apprDetail.snapshot) }}</pre>

        <h4 class="drawer-h">将写入的内容</h4>
        <pre class="json-box">{{ prettyJSON(apprDetail.payload) }}</pre>

        <template v-if="apprDetail.last_error">
          <h4 class="drawer-h">上次应用失败原因</h4>
          <div class="appr-error">{{ apprDetail.last_error }}</div>
        </template>
      </template>
      <div v-else class="muted">加载中…</div>
      <template #footer>
        <a-space v-if="apprDetail?.status === 'pending'">
          <a-button @click="apprDrawer = false">关闭</a-button>
          <a-button danger @click="askReview(apprDetail, false)">驳回</a-button>
          <a-button type="primary" :loading="apprActing" @click="askReview(apprDetail, true)">批准并应用</a-button>
        </a-space>
        <a-button v-else @click="apprDrawer = false">关闭</a-button>
      </template>
    </a-drawer>

    <!-- 复核意见（批准/驳回都要留话，避免闭眼点通过） -->
    <a-modal v-model:open="reviewModal" :title="reviewOk ? '批准该变更' : '驳回该变更'"
      :confirm-loading="apprActing" @ok="submitReview">
      <a-alert v-if="reviewOk" type="warning" show-icon style="margin-bottom:10px"
        message="批准后变更将立即生效，删除类操作不可撤销。" />
      <a-form layout="vertical">
        <a-form-item label="复核意见">
          <a-textarea v-model:value="reviewComment" :rows="3"
            :placeholder="reviewOk ? '如：确认该套题已无引用，同意删除' : '如：题目仍在被使用，暂不删除（驳回必填）'" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { adminApi, contentApi, observabilityApi, approvalApi } from '@/api'
import ReplayModal from '@/components/ReplayModal.vue'

const router = useRouter()
const stats = ref(null)
const tab = ref('users')

const users = ref({ list: [], total: 0, page: 1, page_size: 10 })
const sessions = ref({ list: [], total: 0, page: 1, page_size: 10 })
const resumes = ref({ list: [], total: 0, page: 1, page_size: 10 })
const records = ref({ list: [], total: 0, page: 1, page_size: 10 })
const userKw = ref('')
const sessionKw = ref('')
const resumeKw = ref('')
const sessionRange = ref([])
const resumeRange = ref([])
const recordKw = ref('')
const recordFormType = ref('')
const formOptions = [
  { label: '全部', value: '' },
  { label: '结构化', value: 'structured' },
  { label: '群面', value: 'group' },
  { label: '半结构化', value: 'semi' },
]

// 加载态
const usersLoading = ref(false)
const sessionsLoading = ref(false)
const resumesLoading = ref(false)
const recordsLoading = ref(false)

// 抽屉
const userDrawer = ref(false)
const userDetail = ref(null)
const resumeDrawer = ref(false)
const resumeDetail = ref(null)

// 面试回放弹窗
const replayOpen = ref(false)
const replaySessionId = ref(null)
const answeredCount = computed(() => records.value.list.filter(r => r.answered_count).length)
const audioCount = computed(() => records.value.list.filter(r => r.has_audio).length)
const videoCount = computed(() => records.value.list.filter(r => r.has_video).length)

const userCols = [
  { title: '昵称', dataIndex: 'nickname', key: 'nickname' },
  { title: '手机号', dataIndex: 'phone', key: 'phone' },
  { title: '目标岗位', dataIndex: 'target_position', key: 'target_position', customRender: ({ text }) => text || '—' },
  { title: '角色', key: 'role' },
  { title: '练习次数', dataIndex: 'practice_count', key: 'practice_count' },
  { title: '平均分', key: 'avg_score' },
  { title: '简历', dataIndex: 'resume_count', key: 'resume_count' },
  { title: '状态', key: 'status' },
  { title: '操作', key: 'op' },
]
const sessionCols = [
  { title: '场次ID', dataIndex: 'id', key: 'id' },
  { title: '用户', dataIndex: 'user_name', key: 'user_name' },
  { title: '形式', key: 'form_type' },
  { title: '套题', dataIndex: 'set_name', key: 'set_name' },
  { title: '总分', key: 'total_score' },
  { title: '状态', key: 'status' },
  { title: '开始时间', dataIndex: 'started_at', key: 'started_at' },
]
const recordCols = [
  { title: '场次', dataIndex: 'id', key: 'id', width: 80 },
  { title: '用户', dataIndex: 'user_name', key: 'user_name' },
  { title: '形式', key: 'form_type' },
  { title: '套题', dataIndex: 'set_name', key: 'set_name' },
  { title: '题数', key: 'qcount', customRender: ({ record }) => `${record.answered_count}/${record.question_count}` },
  { title: '时长', key: 'duration' },
  { title: '总分', key: 'total_score' },
  { title: '保存情况', key: 'saves' },
  { title: '开始时间', dataIndex: 'started_at', key: 'started_at' },
  { title: '操作', key: 'op', width: 110 },
]
const resumeCols = [
  { title: 'ID', dataIndex: 'id', key: 'id' },
  { title: '用户', dataIndex: 'user_name', key: 'user_name' },
  { title: '文件', dataIndex: 'filename', key: 'filename' },
  { title: '候选人', dataIndex: 'candidate_name', key: 'candidate_name', customRender: ({ text }) => text || '—' },
  { title: '目标岗位', dataIndex: 'target_position', key: 'target_position', customRender: ({ text }) => text || '—' },
  { title: '技能', key: 'skills' },
  { title: '引擎', key: 'engine' },
  { title: '上传时间', dataIndex: 'created_at', key: 'created_at' },
  { title: '操作', key: 'op', width: 90 },
]
const practiceCols = [
  { title: '套题', dataIndex: 'set_name', key: 'set_name' },
  { title: '得分', dataIndex: 'total_score', key: 'total_score' },
  { title: '时间', dataIndex: 'practiced_at', key: 'practiced_at' },
]
const resumeMiniCols = [
  { title: 'ID', dataIndex: 'id', key: 'id' },
  { title: '文件', dataIndex: 'filename', key: 'filename' },
  { title: '引擎', dataIndex: 'engine', key: 'engine' },
  { title: '候选人', dataIndex: 'candidate_name', key: 'candidate_name' },
]
const sessionMiniCols = [
  { title: '场次', dataIndex: 'id', key: 'id' },
  { title: '形式', dataIndex: 'form_label', key: 'form_label' },
  { title: '套题', dataIndex: 'set_name', key: 'set_name' },
  { title: '总分', dataIndex: 'total_score', key: 'total_score' },
  { title: '时间', dataIndex: 'started_at', key: 'started_at' },
]

function barH(c) {
  const max = Math.max(...(stats.value?.trend || []).map(t => t.count), 1)
  return 8 + (c / max) * 90
}
function distPct(v) {
  const max = Math.max(...(stats.value?.form_distribution || []).map(d => d.value), 1)
  return Math.round(v / max * 100)
}
function statusLabel(s) {
  return { done: '已完成', running: '进行中', idle: '待开始', aborted: '已中断', paused: '已暂停' }[s] || s
}
function fmtMs(ms) {
  ms = ms || 0
  const s = Math.round(ms / 1000)
  const m = Math.floor(s / 60)
  const ss = String(s % 60).padStart(2, '0')
  return `${m}:${ss}`
}

async function loadStats() {
  try { stats.value = await adminApi.stats() } catch (e) {
    message.error('无管理员权限或加载失败')
    router.push('/dashboard')
  }
}
async function loadUsers() {
  usersLoading.value = true
  try {
    const r = await adminApi.users({ keyword: userKw.value, page: users.value.page, page_size: 10 })
    users.value.list = r.list; users.value.total = r.total
  } finally { usersLoading.value = false }
}
async function loadSessions() {
  sessionsLoading.value = true
  try {
    const params = { page: sessions.value.page, page_size: 10 }
    if (sessionKw.value) params.keyword = sessionKw.value
    const rg = sessionRange.value
    if (rg && rg[0]) params.start = rg[0].format('YYYY-MM-DD')
    if (rg && rg[1]) params.end = rg[1].format('YYYY-MM-DD')
    const r = await adminApi.sessions(params)
    sessions.value.list = r.list; sessions.value.total = r.total
  } finally { sessionsLoading.value = false }
}
async function loadResumes() {
  resumesLoading.value = true
  try {
    const params = { page: resumes.value.page, page_size: 10 }
    if (resumeKw.value) params.keyword = resumeKw.value
    const rg = resumeRange.value
    if (rg && rg[0]) params.start = rg[0].format('YYYY-MM-DD')
    if (rg && rg[1]) params.end = rg[1].format('YYYY-MM-DD')
    const r = await adminApi.resumes(params)
    resumes.value.list = r.list; resumes.value.total = r.total
  } finally { resumesLoading.value = false }
}
async function reloadRecords() {
  recordsLoading.value = true
  try {
    const r = await adminApi.records({
      keyword: recordKw.value,
      form_type: recordFormType.value,
      page: records.value.page,
      page_size: 10,
    }).catch(() => ({ list: [], total: 0 }))
    records.value.list = r.list || []
    records.value.total = r.total || 0
  } finally { recordsLoading.value = false }
}
async function toggleUser(record) {
  const next = record.status === 'active' ? 'paused' : 'active'
  await adminApi.setUserStatus(record.id, next)
  message.success(next === 'active' ? '已启用' : '已禁用')
  loadUsers()
}
function openReplay(record) {
  replaySessionId.value = record.id
  replayOpen.value = true
}
async function openUser(record) {
  userDrawer.value = true
  userDetail.value = null
  try { userDetail.value = await adminApi.userDetail(record.id) }
  catch (e) { message.error('加载用户详情失败') }
}
async function openResume(record) {
  resumeDrawer.value = true
  resumeDetail.value = null
  try { resumeDetail.value = await adminApi.resumeDetail(record.id) }
  catch (e) { message.error('加载简历详情失败') }
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
async function exportUsers() {
  try {
    const blob = await adminApi.exportUsers()
    triggerDownload(blob, 'mockwise_users.csv')
    message.success('已导出用户 CSV')
  } catch (e) { message.error('导出失败') }
}
async function exportSessions() {
  try {
    const params = {}
    if (sessionKw.value) params.keyword = sessionKw.value
    const rg = sessionRange.value
    if (rg && rg[0]) params.start = rg[0].format('YYYY-MM-DD')
    if (rg && rg[1]) params.end = rg[1].format('YYYY-MM-DD')
    const blob = await adminApi.exportSessions(params)
    triggerDownload(blob, 'mockwise_sessions.csv')
    message.success('已导出面试场次 CSV')
  } catch (e) { message.error('导出失败') }
}
async function exportResumes() {
  try {
    const params = {}
    if (resumeKw.value) params.keyword = resumeKw.value
    const rg = resumeRange.value
    if (rg && rg[0]) params.start = rg[0].format('YYYY-MM-DD')
    if (rg && rg[1]) params.end = rg[1].format('YYYY-MM-DD')
    const blob = await adminApi.exportResumes ? await adminApi.exportResumes(params) : null
    if (!blob) { message.error('后端未提供简历导出'); return }
    triggerDownload(blob, 'mockwise_resumes.csv')
    message.success('已导出简历 CSV')
  } catch (e) { message.error('导出失败') }
}
async function exportRecords() {
  try {
    const params = {}
    if (recordKw.value) params.keyword = recordKw.value
    if (recordFormType.value) params.form_type = recordFormType.value
    const blob = await adminApi.exportRecords(params)
    triggerDownload(blob, 'mockwise_records.csv')
    message.success('已导出面试回放 CSV')
  } catch (e) { message.error('导出失败') }
}

// ============ 内容配置后台 ============
const contentTab = ref('sets')
const sets = ref({ list: [] })
const setsLoading = ref(false)
const questions = ref({ list: [] })
const questionsLoading = ref(false)
const qSelectedSetId = ref(null)
const personas = ref({ list: [] })
const personasLoading = ref(false)
const saving = ref(false)

const formTypeOptions = [
  { label: '结构化', value: 'structured' },
  { label: '群面', value: 'group' },
  { label: '半结构化', value: 'semi' },
]
const diffOptions = [
  { label: '简单', value: 'easy' },
  { label: '中等', value: 'medium' },
  { label: '困难', value: 'hard' },
]
function formLabel(v) { return { structured: '结构化', group: '群面', semi: '半结构化' }[v] || v }
function diffLabel(v) { return { easy: '简单', medium: '中等', hard: '困难' }[v] || v }

const setOptions = computed(() =>
  sets.value.list.map(s => ({ label: `${s.name}（${formLabel(s.form_type)}）`, value: s.id })))
const personaScopeOptions = computed(() =>
  [{ label: '通用（所有群面）', value: 0 }].concat(setOptions.value))

const setCols = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '形式', key: 'form_type', width: 90 },
  { title: '难度', key: 'difficulty', width: 80 },
  { title: '题目数', dataIndex: 'question_count', key: 'question_count', width: 80 },
  { title: '状态', key: 'status', width: 90 },
  { title: '操作', key: 'op' },
]
const qCols = [
  { title: '#', key: 'seq', width: 56 },
  { title: '类别', dataIndex: 'category', key: 'category', width: 96 },
  { title: '维度', dataIndex: 'dimension', key: 'dimension', width: 96 },
  { title: '题目内容', key: 'content' },
  { title: '时限', dataIndex: 'time_limit_s', key: 'time_limit_s', width: 72 },
  { title: '操作', key: 'op', width: 120 },
]
const personaCols = [
  { title: '姓名', key: 'name' },
  { title: '风格', dataIndex: 'style', key: 'style', width: 96 },
  { title: '抢话', dataIndex: 'aggressiveness', key: 'aggressiveness', width: 64 },
  { title: '范围', key: 'scope', width: 96 },
  { title: '简介', dataIndex: 'bio', key: 'bio', ellipsis: true },
  { title: '操作', key: 'op', width: 120 },
]

async function loadSets() {
  setsLoading.value = true
  try { sets.value.list = await contentApi.sets() } finally { setsLoading.value = false }
}
async function loadQuestions() {
  if (!qSelectedSetId.value) return
  questionsLoading.value = true
  try { questions.value.list = await contentApi.questions(qSelectedSetId.value) } finally { questionsLoading.value = false }
}
async function loadPersonas() {
  personasLoading.value = true
  try { personas.value.list = await contentApi.personas() } finally { personasLoading.value = false }
}

// —— 套题 ——
const setDrawer = ref(false)
const setForm = reactive({
  id: null, name: '', industry: '', position_type: '', form_type: 'structured',
  difficulty: 'medium', description: '', est_minutes: 0, match_score: 0, is_published: 1,
})
function openSetForm(row) {
  const d = { id: null, name: '', industry: '', position_type: '', form_type: 'structured',
    difficulty: 'medium', description: '', est_minutes: 0, match_score: 0, is_published: 1 }
  if (row) Object.assign(d, row)
  Object.assign(setForm, d)
  setDrawer.value = true
}
async function saveSet() {
  if (!setForm.name || !setForm.name.trim()) { message.warning('请填写套题名称'); return }
  saving.value = true
  try {
    const payload = {
      name: setForm.name, industry: setForm.industry, position_type: setForm.position_type,
      form_type: setForm.form_type, difficulty: setForm.difficulty, description: setForm.description,
      est_minutes: setForm.est_minutes, match_score: setForm.match_score, is_published: setForm.is_published,
    }
    if (setForm.id) await contentApi.updateSet(setForm.id, payload)
    else await contentApi.createSet(payload)
    message.success('已保存')
    setDrawer.value = false
    await loadSets()
  } catch (e) { message.error('保存失败') } finally { saving.value = false }
}
async function togglePublish(row) {
  const next = row.is_published ? 0 : 1
  const r = await contentApi.togglePublish(row.id, next)
  const d = r?.data ?? r
  if (d?.need_approval) {
    message.info(`已提交人工复核（审批单 #${d.approval_id}），批准后生效`)
    loadApprovals()
    return
  }
  message.success(next ? '已上架' : '已下架')
  loadSets()
}
async function delSet(row) {
  const r = await contentApi.deleteSet(row.id)
  const d = r?.data ?? r
  if (d?.need_approval) {
    message.info(`已提交人工复核（审批单 #${d.approval_id}），批准后才会删除`)
    loadApprovals()
    return
  }
  message.success('已删除')
  loadSets()
  if (qSelectedSetId.value === row.id) { qSelectedSetId.value = null; questions.value.list = [] }
}

// —— 题目 ——
const qModal = ref(false)
const aiGenLoading = ref(false)
const qForm = reactive({
  id: null, set_id: null, seq: 0, form_type: 'structured', difficulty: 'medium',
  category: '', dimension: '', content: '', ref_answer: '', time_limit_s: 120,
})
function openQuestions(row) {
  qSelectedSetId.value = row.id
  contentTab.value = 'questions'
  loadQuestions()
}
function openQForm(row) {
  const d = { id: null, set_id: qSelectedSetId.value, seq: 0, form_type: 'structured',
    difficulty: 'medium', category: '', dimension: '', content: '', ref_answer: '', time_limit_s: 120 }
  if (row) Object.assign(d, row, { set_id: qSelectedSetId.value })
  Object.assign(qForm, d)
  qModal.value = true
}
async function saveQuestion() {
  if (!qForm.content || !qForm.content.trim()) { message.warning('请填写题目内容'); return }
  saving.value = true
  try {
    const payload = {
      seq: qForm.seq, form_type: qForm.form_type, difficulty: qForm.difficulty,
      category: qForm.category, dimension: qForm.dimension, content: qForm.content,
      ref_answer: qForm.ref_answer || null, time_limit_s: qForm.time_limit_s,
    }
    if (qForm.id) await contentApi.updateQuestion(qForm.id, payload)
    else await contentApi.createQuestion(qSelectedSetId.value, payload)
    message.success('已保存')
    qModal.value = false
    await loadQuestions()
  } catch (e) { message.error('保存失败') } finally { saving.value = false }
}

// AI 生成参考答案：大模型起草后进入人工复核，批准才写入题库
async function aiGenRefAnswer() {
  if (!qForm.id) { message.warning('请先保存题目再生成参考答案'); return }
  aiGenLoading.value = true
  try {
    const r = await contentApi.aiRefAnswer(qForm.id)
    const d = r.data
    if (d.need_approval) {
      message.success(`已提交人工复核（审批单 #${d.approval_id}，${d.engine} 生成），批准后生效`)
    } else {
      qForm.ref_answer = d.ref_answer || qForm.ref_answer
      message.success('AI 已生成参考答案并写入')
    }
  } catch (e) {
    message.error((e?.response?.data?.msg) || 'AI 生成失败')
  } finally { aiGenLoading.value = false }
}
async function delQuestion(row) {
  const r = await contentApi.deleteQuestion(row.id)
  const d = r?.data ?? r
  if (d?.need_approval) {
    message.info(`已提交人工复核（审批单 #${d.approval_id}），批准后才会删除`)
    loadApprovals()
    return
  }
  message.success('已删除')
  loadQuestions()
}

// —— 群面人设 ——
const personaDrawer = ref(false)
const personaForm = reactive({
  id: null, name: '', style: '', color: '#3E63DD', bio: '', aggressiveness: 3,
  set_id: 0, openings: '', rebuttals: '', summaries: '',
})
function openPersonaForm(row) {
  const d = { id: null, name: '', style: '', color: '#3E63DD', bio: '', aggressiveness: 3,
    set_id: 0, openings: '', rebuttals: '', summaries: '' }
  if (row) Object.assign(d, row, {
    set_id: row.set_id || 0,
    openings: (row.openings || []).join('\n'),
    rebuttals: (row.rebuttals || []).join('\n'),
    summaries: (row.summaries || []).join('\n'),
  })
  Object.assign(personaForm, d)
  personaDrawer.value = true
}
function _lines(s) { return (s || '').split('\n').map(x => x.trim()).filter(Boolean) }
async function savePersona() {
  if (!personaForm.name || !personaForm.name.trim()) { message.warning('请填写姓名'); return }
  saving.value = true
  try {
    const payload = {
      name: personaForm.name, style: personaForm.style, color: personaForm.color,
      bio: personaForm.bio, aggressiveness: personaForm.aggressiveness,
      set_id: personaForm.set_id ? personaForm.set_id : null,
      openings: _lines(personaForm.openings),
      rebuttals: _lines(personaForm.rebuttals),
      summaries: _lines(personaForm.summaries),
    }
    if (personaForm.id) await contentApi.updatePersona(personaForm.id, payload)
    else await contentApi.createPersona(payload)
    message.success('已保存')
    personaDrawer.value = false
    await loadPersonas()
  } catch (e) { message.error('保存失败') } finally { saving.value = false }
}
async function delPersona(row) {
  const r = await contentApi.deletePersona(row.id)
  const d = r?.data ?? r
  if (d?.need_approval) {
    message.info(`已提交人工复核（审批单 #${d.approval_id}），批准后才会删除`)
    loadApprovals()
    return
  }
  message.success('已删除')
  loadPersonas()
}

// ——— 人工审批卡点（高危变更 草稿 → 待审 → 复核）———
const apprStatus = ref('pending')
const approvals = ref([])
const pendingCount = ref(0)
const apprLoading = ref(false)
const apprActing = ref(false)
const apprDrawer = ref(false)
const apprDetail = ref(null)
const reviewModal = ref(false)
const reviewOk = ref(true)
const reviewComment = ref('')
const reviewTarget = ref(null)

const approvalCols = [
  { title: '#', dataIndex: 'id', key: 'id', width: 56 },
  { title: '对象', key: 'target', width: 150,
    customRender: ({ record }) => `${record.target_type} #${record.target_id || '-'}` },
  { title: '动作', key: 'action', width: 80 },
  { title: '风险', key: 'risk', width: 76 },
  { title: '变更说明', dataIndex: 'summary', key: 'summary', ellipsis: true },
  { title: '提交人', dataIndex: 'submitter_id', key: 'submitter_id', width: 78 },
  { title: '状态', key: 'status', width: 90 },
  { title: '提交时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'ops', width: 180 },
]

function prettyJSON(s) {
  if (!s) return '（空）'
  try { return JSON.stringify(JSON.parse(s), null, 2) } catch { return String(s) }
}

async function loadApprovals() {
  apprLoading.value = true
  try {
    const r = await approvalApi.list(apprStatus.value || undefined, 50)
    const d = r?.data ?? r
    approvals.value = Array.isArray(d) ? d : (d?.list || [])
    const pc = await approvalApi.pendingCount()
    pendingCount.value = (pc?.data ?? pc)?.pending ?? 0
  } catch (e) {
    message.error('审批单加载失败')
  } finally {
    apprLoading.value = false
  }
}

async function openApproval(row) {
  apprDrawer.value = true
  apprDetail.value = null
  try {
    const r = await approvalApi.detail(row.id)
    apprDetail.value = r?.data ?? r
  } catch { apprDetail.value = row }
}

function askReview(row, ok) {
  reviewTarget.value = row
  reviewOk.value = ok
  reviewComment.value = ''
  reviewModal.value = true
}

async function submitReview() {
  if (!reviewTarget.value) return
  if (!reviewOk.value && !reviewComment.value.trim()) {
    message.warning('驳回请填写原因，便于提交人修正')
    return
  }
  apprActing.value = true
  try {
    if (reviewOk.value) {
      await approvalApi.approve(reviewTarget.value.id, reviewComment.value || '同意')
      message.success('已批准，变更已生效')
    } else {
      await approvalApi.reject(reviewTarget.value.id, reviewComment.value)
      message.success('已驳回，未产生任何变更')
    }
    reviewModal.value = false
    apprDrawer.value = false
    await loadApprovals()
    loadSets(); loadPersonas()
    if (qSelectedSetId.value) loadQuestions()
  } catch (e) {
    message.error(e?.response?.data?.msg || '操作失败')
  } finally {
    apprActing.value = false
  }
}

// ——— 可观测性（成功率 / 耗时 / 成本 / 上下文命中 / 量化评测）———
const obsHours = ref(24)
const obsLoading = ref(false)
const obs = ref(null)
const obsCtx = ref(null)
const evalRepeat = ref(3)
const evalOffline = ref(true)
const evalRunning = ref(false)
const evalLatest = ref(null)

const pct = (v) => (v == null ? '—' : (v * 100).toFixed(1) + '%')

const obsSceneCols = [
  { title: '场景', dataIndex: 'scene' },
  { title: '调用数', dataIndex: 'total_calls' },
  { title: '成功率', dataIndex: 'success_rate', customRender: ({ text }) => pct(text) },
  { title: '平均耗时(ms)', dataIndex: 'avg_latency_ms' },
  { title: 'P95(ms)', dataIndex: 'p95_latency_ms' },
  { title: 'Token', dataIndex: 'total_tokens' },
  { title: '成本(¥)', dataIndex: 'cost_cny', customRender: ({ text }) => (text ?? 0).toFixed(4) },
]
const evalSampleCols = [
  { title: '样本', dataIndex: 'name' },
  { title: '均分', dataIndex: 'mean_score', customRender: ({ text }) => (text == null ? '—' : text) },
  { title: '标准差', dataIndex: 'std' },
  { title: '极差', dataIndex: 'range', customRender: ({ text }) => (text == null ? '—' : text) },
  {
    title: '期望区间',
    dataIndex: 'expected',
    customRender: ({ text }) => (text && text[0] != null ? `${text[0]} ~ ${text[1]}` : '—'),
  },
  { title: '引擎', dataIndex: 'engine' },
]

async function loadObs() {
  obsLoading.value = true
  try {
    const [m, c] = await Promise.all([
      observabilityApi.llmMetrics(obsHours.value),
      observabilityApi.contextMetrics(obsHours.value),
    ])
    obs.value = m?.data ?? m
    obsCtx.value = c?.data ?? c
  } catch (e) {
    message.error('指标加载失败')
  } finally {
    obsLoading.value = false
  }
}

async function runEval() {
  evalRunning.value = true
  try {
    const r = await observabilityApi.runEval(evalRepeat.value, evalOffline.value)
    evalLatest.value = r?.data ?? r
    message.success('评测完成')
    loadObs()
  } catch (e) {
    message.error('评测失败')
  } finally {
    evalRunning.value = false
  }
}

async function loadEvalLatest() {
  try {
    const r = await observabilityApi.latestEval()
    evalLatest.value = r?.data ?? r
  } catch {
    evalLatest.value = null
  }
}

onMounted(() => {
  loadStats()
  loadUsers()
  loadSessions()
  loadResumes()
  reloadRecords()
  loadSets()
  loadPersonas()
  loadObs()
  loadEvalLatest()
  loadApprovals()
})
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
.stat-card { padding: 20px; }
.s-num { font-size: 32px; font-weight: 800; color: var(--primary); }
.s-label { font-size: 13px; color: var(--text-2); margin-top: 4px; }
.s-sub { font-size: 12px; color: var(--text-3); margin-left: 6px; }
.chart-row { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; }
.chart-card { padding: 20px; }
.card-title { font-size: 14px; font-weight: 700; margin-bottom: 16px; }
.trend-bars { display: flex; align-items: flex-end; gap: 14px; height: 140px; }
.t-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; }
.t-bar { width: 60%; background: linear-gradient(180deg, #3E63DD, #7C6BD6); border-radius: 6px 6px 0 0; min-height: 8px; }
.t-val { font-size: 12px; font-weight: 700; margin-top: 4px; }
.t-date { font-size: 11px; color: var(--text-3); }
.dist-list { display: flex; flex-direction: column; gap: 14px; }
.dist-row { display: flex; align-items: center; gap: 10px; }
.d-name { font-size: 13px; width: 70px; }
.d-bar-shell { flex: 1; height: 10px; background: var(--border-soft); border-radius: 5px; overflow: hidden; }
.d-bar-shell > span { display: block; height: 100%; background: var(--success); border-radius: 5px; }
.d-val { font-size: 13px; font-weight: 700; width: 36px; text-align: right; }
.toolbar { margin-bottom: 12px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.records-toolbar { flex-wrap: wrap; }

.record-stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
  margin-bottom: 14px;
}
.rs-item {
  padding: 14px; background: var(--bg); border-radius: 10px;
  display: flex; flex-direction: column; gap: 4px;
}
.rs-num { font-size: 22px; font-weight: 800; color: var(--primary); }
.rs-label { font-size: 12px; color: var(--text-3); }

.pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 14px; font-size: 13px; color: var(--text-3); }

.drawer-h { font-size: 14px; font-weight: 700; margin: 18px 0 10px; }
.muted { color: var(--text-3); font-size: 13px; }
.sub-tabs { margin-top: 4px; }
.cell-clamp {
  display: inline-block; max-width: 460px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; vertical-align: bottom;
}
.persona-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.json-box {
  background: var(--bg); border: 1px solid var(--border-soft); border-radius: 8px;
  padding: 12px; font-size: 12px; line-height: 1.5; max-height: 320px; overflow: auto;
  white-space: pre-wrap; word-break: break-all; margin: 0;
}
.appr-summary {
  background: var(--bg); border: 1px solid var(--border-soft); border-radius: 8px;
  padding: 10px 12px; font-size: 13px; line-height: 1.6;
}
.appr-error {
  background: #fff2f0; border: 1px solid #ffccc7; border-radius: 8px;
  padding: 10px 12px; font-size: 12px; color: #cf1322; line-height: 1.6;
}

@media (max-width: 900px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .chart-row { grid-template-columns: 1fr; }
  .record-stats { grid-template-columns: repeat(2, 1fr); }
}
</style>
