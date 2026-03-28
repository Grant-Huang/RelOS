/**
 * ExpertInit — 专家初始化向导（4 步）
 * 步骤：① 设备信息 → ② 录入关系 → ③ 导入历史 → ④ 完成
 */
import { useState, useRef } from 'react'
import { UserCog, ChevronRight, ChevronLeft, Plus, Trash2, CheckCircle, Upload } from 'lucide-react'
import ConfidenceBar from '../components/ConfidenceBar'
import { expertInitRelation, uploadDocument, getDocument, clarifyDocument, postTelemetryEvent } from '../api/client'

const RELATION_TEMPLATES = [
  { value: 'ALARM__INDICATES__COMPONENT_FAILURE', label: '告警 → 根因部件' },
  { value: 'DEVICE__TRIGGERS__ALARM', label: '设备 → 触发告警' },
  { value: 'OPERATOR__RESOLVES__ALARM', label: '操作员 → 处理告警' },
  { value: 'PROCESS__AFFECTS__QUALITY', label: '工艺 → 影响质量' },
]

const DEVICE_TYPES = ['注塑机', '焊接机', '冲压机', '装配线', '输送线', '其他']

const STEPS = ['设备信息', '录入关系', '导入历史', '完成']

function StepIndicator({ current }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEPS.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <div key={i} className="flex items-center gap-2">
            <div className={`flex items-center gap-2 ${active ? '' : done ? 'opacity-60' : 'opacity-30'}`}>
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 border ${
                done ? 'bg-confidence-high border-confidence-high text-white' :
                active ? 'border-[color:var(--blue)] text-[color:var(--blue)]' :
                'border-[color:var(--b2)] text-[color:var(--t3)]'
              }`}>
                {done ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </div>
              <span className={`text-sm ${active ? 'text-[color:var(--t1)] font-medium' : 'text-[color:var(--t2)]'}`}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <ChevronRight className="w-4 h-4 mx-1" style={{ color: 'var(--t3)' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function ExpertInit({ embedded = false }) {
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  // 步骤 1：设备信息
  const [device, setDevice] = useState({
    type: '',
    name: '',
    device_id: '',
    location: '',
  })

  // 步骤 2：关系列表
  const [relations, setRelations] = useState([
    { relation_type: 'ALARM__INDICATES__COMPONENT_FAILURE', alarm_code: '', cause: '', confidence: 0.75, notes: '' },
  ])

  // 步骤 3：上传
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef()
  const [docDetail, setDocDetail] = useState(null)
  const [docLoading, setDocLoading] = useState(false)
  const [clarifyAns, setClarifyAns] = useState({})
  const [clarifySubmitting, setClarifySubmitting] = useState(false)

  // 步骤 4：汇总
  const [submitted, setSubmitted] = useState(0)

  const addRelation = () => {
    setRelations([...relations, {
      relation_type: 'ALARM__INDICATES__COMPONENT_FAILURE',
      alarm_code: '', cause: '', confidence: 0.75, notes: '',
    }])
  }

  const removeRelation = (i) => {
    setRelations(relations.filter((_, idx) => idx !== i))
  }

  const updateRelation = (i, field, value) => {
    setRelations(relations.map((r, idx) => idx === i ? { ...r, [field]: value } : r))
  }

  const handleUpload = async (file) => {
    if (!file) return
    setUploading(true)
    setDocDetail(null)
    setClarifyAns({})
    try {
      const result = await uploadDocument(file)
      setUploadResult(result)
    } catch {
      setUploadResult({ error: '上传失败，请确认后端服务已启动' })
    } finally {
      setUploading(false)
    }
  }

  const loadDoc = async () => {
    if (!uploadResult?.id) return
    setDocLoading(true)
    try {
      const d = await getDocument(uploadResult.id)
      setDocDetail(d)
      const existing = d?.clarify_answers || {}
      setClarifyAns(existing)
    } catch {
      setDocDetail({ error: '获取文档状态失败，请稍后重试' })
    } finally {
      setDocLoading(false)
    }
  }

  const submitClarify = async () => {
    if (!uploadResult?.id) return
    setClarifySubmitting(true)
    try {
      const d = await clarifyDocument(uploadResult.id, { answers: clarifyAns, answered_by: 'engineer' })
      setDocDetail(d)
      postTelemetryEvent({
        event_name: 'document_clarify_submitted',
        props: { doc_id: uploadResult.id, answers: clarifyAns },
      }).catch(() => {})
    } catch (e) {
      setDocDetail({ error: e.message || '提交澄清失败' })
    } finally {
      setClarifySubmitting(false)
    }
  }

  const handleSubmitRelations = async () => {
    setSubmitting(true)
    let count = 0
    for (const rel of relations) {
      if (!rel.alarm_code || !rel.cause) continue
      try {
        await expertInitRelation({
          source_node_id: `alarm-${rel.alarm_code}`,
          source_node_type: 'Alarm',
          target_node_id: rel.cause,
          target_node_type: 'Component',
          relation_type: rel.relation_type,
          confidence: rel.confidence,
          provenance: 'manual_engineer',
          half_life_days: 365,
          notes: rel.notes || undefined,
          device_id: device.device_id || undefined,
        })
        count++
      } catch { /* 跳过失败条目 */ }
    }
    setSubmitted(count)
    setSubmitting(false)
    setStep(3)
  }

  return (
    <div className={embedded ? 'p-0 max-w-2xl mx-auto' : 'p-8 max-w-2xl mx-auto'}>
      {!embedded && (
        <div className="flex items-center gap-3 mb-8">
          <UserCog className="w-6 h-6 text-purple-400" />
          <div>
            <h1 className="text-2xl font-bold text-[color:var(--t1)]">专家初始化向导</h1>
            <p className="text-[color:var(--t2)] text-sm">将现场经验沉淀为知识图谱</p>
          </div>
        </div>
      )}

      <StepIndicator current={step} />

      {/* 步骤 1：设备信息 */}
      {step === 0 && (
        <div className="relos-panel mb-6">
          <h2 className="text-lg font-semibold text-[color:var(--t1)] mb-5">设备基本信息</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-[color:var(--t2)] mb-1.5">设备类型 *</label>
              <select
                value={device.type}
                onChange={(e) => setDevice({ ...device, type: e.target.value })}
                className="relos-field"
              >
                <option value="">请选择...</option>
                {DEVICE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[color:var(--t2)] mb-1.5">设备名称 *</label>
              <input
                type="text"
                value={device.name}
                onChange={(e) => setDevice({ ...device, name: e.target.value })}
                placeholder="如：1号注塑机"
                className="relos-field"
              />
            </div>
            <div>
              <label className="block text-xs text-[color:var(--t2)] mb-1.5">设备 ID</label>
              <input
                type="text"
                value={device.device_id}
                onChange={(e) => setDevice({ ...device, device_id: e.target.value })}
                placeholder="如：device-M1"
                className="relos-field"
              />
            </div>
            <div>
              <label className="block text-xs text-[color:var(--t2)] mb-1.5">车间/位置</label>
              <input
                type="text"
                value={device.location}
                onChange={(e) => setDevice({ ...device, location: e.target.value })}
                placeholder="如：A栋一车间"
                className="relos-field"
              />
            </div>
          </div>
          <button
            onClick={() => setStep(1)}
            disabled={!device.type || !device.name}
            className="btn btn-p mt-6 w-full justify-center disabled:opacity-40 disabled:cursor-not-allowed"
          >
            下一步 <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 步骤 2：录入关系 */}
      {step === 1 && (
        <div className="space-y-4">
          <div className="relos-panel mb-4">
            <p className="text-xs text-[color:var(--t2)] mb-1">正在为设备录入经验关系</p>
            <p className="text-[color:var(--t1)] font-semibold">{device.type} · {device.name}</p>
          </div>

          {relations.map((rel, i) => (
            <div key={i} className="relos-panel mb-4">
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-medium text-[color:var(--t2)]">关系 #{i + 1}</span>
                {relations.length > 1 && (
                  <button onClick={() => removeRelation(i)} className="text-[color:var(--t3)] hover:text-red-400 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-[color:var(--t2)] mb-1.5">关系类型</label>
                  <select
                    value={rel.relation_type}
                    onChange={(e) => updateRelation(i, 'relation_type', e.target.value)}
                    className="relos-field"
                  >
                    {RELATION_TEMPLATES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[color:var(--t2)] mb-1.5">告警码 *</label>
                    <input
                      type="text"
                      value={rel.alarm_code}
                      onChange={(e) => updateRelation(i, 'alarm_code', e.target.value)}
                      placeholder="如 VIB-001"
                      className="relos-field"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[color:var(--t2)] mb-1.5">根因部件 *</label>
                    <input
                      type="text"
                      value={rel.cause}
                      onChange={(e) => updateRelation(i, 'cause', e.target.value)}
                      placeholder="如 轴承磨损"
                      className="relos-field"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-[color:var(--t2)] mb-2">
                    置信度：{Math.round(rel.confidence * 100)}%
                  </label>
                  <input
                    type="range"
                    min="50" max="95" step="5"
                    value={Math.round(rel.confidence * 100)}
                    onChange={(e) => updateRelation(i, 'confidence', e.target.value / 100)}
                    className="w-full accent-blue-500"
                  />
                  <div className="mt-2">
                    <ConfidenceBar value={rel.confidence} size="sm" showLabel={true} />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-[color:var(--t2)] mb-1.5">备注（可选）</label>
                  <textarea
                    value={rel.notes}
                    onChange={(e) => updateRelation(i, 'notes', e.target.value)}
                    placeholder="如：高温天气下此故障概率更高"
                    rows={2}
                    className="relos-field resize-y min-h-[80px]"
                  />
                </div>
              </div>
            </div>
          ))}

          <button
            onClick={addRelation}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-lg border border-dashed border-[color:var(--b2)] text-[color:var(--t2)] hover:text-[color:var(--t2)] hover:border-[color:var(--blue)] transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
            再添加一条关系
          </button>

          <div className="flex gap-3">
            <button
              onClick={() => setStep(0)}
              className="flex items-center gap-2 px-4 py-3 rounded-lg border border-[color:var(--b2)] text-[color:var(--t3)] hover:text-[color:var(--t1)] transition-colors text-sm"
            >
              <ChevronLeft className="w-4 h-4" /> 上一步
            </button>
            <button
              onClick={() => setStep(2)}
              className="btn btn-p flex-1 justify-center"
            >
              下一步 <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* 步骤 3：批量导入（可选） */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="relos-panel mb-6">
            <h2 className="text-lg font-semibold text-[color:var(--t1)] mb-2">导入历史数据（可选）</h2>
            <p className="text-sm text-[color:var(--t2)] mb-5">上传 MES 导出的 Excel 文件，批量导入历史维修关系</p>

            {/* 拖拽上传区 */}
            <div
              className="border-2 border-dashed border-[color:var(--b2)] rounded-xl p-8 text-center cursor-pointer hover:border-[color:var(--b2)] transition-colors"
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                const file = e.dataTransfer.files[0]
                if (file) { setUploadFile(file); handleUpload(file) }
              }}
            >
              <Upload className="w-8 h-8 text-[color:var(--t3)] mx-auto mb-3" />
              {uploadFile ? (
                <>
                  <p className="text-[color:var(--t1)] font-medium">{uploadFile.name}</p>
                  <p className="text-xs text-[color:var(--t2)] mt-1">{(uploadFile.size / 1024).toFixed(1)} KB</p>
                </>
              ) : (
                <>
                  <p className="text-[color:var(--t2)]">拖拽 Excel 文件到此，或点击选择</p>
                  <p className="text-xs text-[color:var(--t3)] mt-1">支持 .xlsx、.xls 格式</p>
                </>
              )}
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files[0]
                  if (file) { setUploadFile(file); handleUpload(file) }
                }}
              />
            </div>

            {uploading && (
              <div className="mt-4 flex items-center gap-2 text-sm text-[color:var(--t3)]">
                <div className="w-4 h-4 border-2 border-[color:var(--b2)] border-t-blue-400 rounded-full animate-spin" />
                正在解析并导入...
              </div>
            )}

            {uploadResult && !uploadResult.error && (
              <div className="mt-4 bg-green-900/20 border border-green-800 rounded-lg p-3">
                <p className="text-green-400 text-sm font-medium">导入成功</p>
                <p className="text-xs text-[color:var(--t3)] mt-1">
                  {JSON.stringify(uploadResult).slice(0, 120)}...
                </p>
              </div>
            )}
            {uploadResult?.error && (
              <p className="mt-3 text-sm text-red-400">{uploadResult.error}</p>
            )}

            {/* 上传后澄清（阶段1/3）：MVP 先做静态问题 + 记录答案 */}
            {uploadResult && !uploadResult.error && (
              <div className="mt-4 relos-subpanel">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[color:var(--t1)]">上传后澄清（可选）</p>
                    <p className="text-xs text-[color:var(--t2)] mt-1">
                      先回答 2-3 个问题，系统后续可据此提升抽取质量（MVP：当前仅记录答案）
                    </p>
                  </div>
                  <button
                    onClick={loadDoc}
                    disabled={docLoading}
                    className="btn btn-sm"
                  >
                    {docLoading ? '加载中…' : '加载问题'}
                  </button>
                </div>

                {docDetail?.error && (
                  <p className="text-sm text-red-400 mt-3">{docDetail.error}</p>
                )}

                {docDetail && !docDetail.error && (
                  <div className="mt-4 space-y-3">
                    <p className="text-xs text-[color:var(--t3)]">
                      doc：<span className="font-mono">{uploadResult.id}</span> · status：{docDetail.status}
                    </p>

                    {(docDetail.clarify_questions || []).map((q) => (
                      <div key={q.question_id} className="relos-subpanel">
                        <p className="text-sm text-[color:var(--t1)]">{q.prompt}</p>
                        {q.type === 'single_choice' ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {(q.options || []).map((opt) => (
                              <button
                                key={opt.id}
                                type="button"
                                onClick={() => setClarifyAns((a) => ({ ...a, [q.question_id]: opt.id }))}
                                className={`px-3 py-2 rounded-lg border text-sm transition-colors ${
                                  clarifyAns?.[q.question_id] === opt.id
                                    ? 'border-[color:var(--blue)] bg-[color:var(--blue-l)] text-[color:var(--blue-ink)]'
                                    : 'border-[color:var(--b2)] bg-[color:var(--bg2)] text-[color:var(--t2)] hover:border-[color:var(--blue)]'
                                }`}
                              >
                                {opt.label}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <input
                            value={clarifyAns?.[q.question_id] || ''}
                            onChange={(e) => setClarifyAns((a) => ({ ...a, [q.question_id]: e.target.value }))}
                            placeholder="可选填写"
                            className="relos-field mt-2"
                          />
                        )}
                      </div>
                    ))}

                    <button
                      onClick={submitClarify}
                      disabled={clarifySubmitting}
                      className="btn btn-p w-full justify-center disabled:opacity-40"
                    >
                      {clarifySubmitting ? '正在提交…' : '提交澄清答案'}
                    </button>
                    <p className="text-xs text-[color:var(--t3)]">
                      说明：若文档尚未进入 <span className="font-mono">pending_review</span>，后端会返回 400（请稍后再试）。
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => setStep(1)}
              className="flex items-center gap-2 px-4 py-3 rounded-lg border border-[color:var(--b2)] text-[color:var(--t3)] hover:text-[color:var(--t1)] transition-colors text-sm"
            >
              <ChevronLeft className="w-4 h-4" /> 上一步
            </button>
            <button
              onClick={handleSubmitRelations}
              disabled={submitting}
              className="btn btn-ok flex-1 justify-center disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  正在提交...
                </>
              ) : (
                <>确认完成 <ChevronRight className="w-4 h-4" /></>
              )}
            </button>
          </div>
          <button
            onClick={handleSubmitRelations}
            disabled={submitting}
            className="w-full text-center text-sm text-[color:var(--t2)] hover:text-[color:var(--t2)] transition-colors py-2"
          >
            跳过导入，直接完成
          </button>
        </div>
      )}

      {/* 步骤 4：完成 */}
      {step === 3 && (
        <div className="relos-panel text-center">
          <CheckCircle className="w-16 h-16 text-confidence-high mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-[color:var(--t1)] mb-2">初始化完成！</h2>
          <p className="text-[color:var(--t3)] mb-6">
            已成功录入 <strong className="text-[color:var(--t1)]">{relations.filter(r => r.alarm_code && r.cause).length}</strong> 条专家经验关系
            {uploadResult && !uploadResult.error && '，并完成历史数据导入'}
          </p>

          <div className="relos-subpanel mb-6 text-left">
            <p className="text-xs text-[color:var(--t2)] mb-2">系统状态</p>
            <div className="space-y-1.5 text-sm">
              <div className="flex items-center gap-2 text-green-400">
                <CheckCircle className="w-4 h-4" />
                知识图谱已建立，Shadow Mode 开启
              </div>
              <div className="flex items-center gap-2 text-blue-400">
                <CheckCircle className="w-4 h-4" />
                下次告警将优先匹配您录入的经验
              </div>
            </div>
          </div>

          <button
            onClick={() => window.location.href = '/alarm'}
            className="btn btn-p w-full justify-center"
          >
            开始验证 → 去分析告警
          </button>
        </div>
      )}
    </div>
  )
}
