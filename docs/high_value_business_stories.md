# RelOS 高价值业务故事

本文档面向工厂一线、设备运维、质量负责人，挑选 5 个最贴合当前 RelOS 页面与接口能力的高价值业务故事。目标不是“展示一个系统能做很多事”，而是让观众理解：RelOS 如何把分散的告警、文档、经验和协同信息，变成现场可执行的判断与行动。

## 故事 1：关键告警 5 分钟内定位首要根因

### 业务场景

夜班操作员发现 1 号机持续出现振动超限，现场只能看到报警和停机，却无法迅速判断是轴承磨损、冷却异常，还是偶发误报。传统做法依赖老师傅经验和纸面记录，排查慢，且不同班次判断不一致。

### RelOS 如何解决

在 `告警根因分析` 页面输入或选择告警后，RelOS 从已有图谱关系中读取：

- 设备与告警的历史触发关系
- 告警与部件故障的经验关系
- 置信度与证据来源

系统给出推荐根因、证据关系和流式解释，必要时还能继续追问澄清问题。

### 对应页面与接口

- 页面：`frontend/src/pages/AlarmAnalysis.jsx`
- 主要接口：
  - `GET /v1/config/quick-alarms`
  - `POST /v1/decisions/analyze-alarm/stream`
  - `POST /v1/decisions/stream-answer`

### 业务价值

- 降低一线排障首轮判断时间
- 减少“靠个人经验记忆”的波动
- 把经验关系沉淀为可复用资产

### 演示所需数据

- `scripts/seed_neo4j.py`
- `relos/demo_data/quick_alarms.json`

---

## 故事 2：维修记录和交接班文档自动变成待审核知识

### 业务场景

设备维修记录、供应商交期表、交接班文档里其实包含了大量高价值知识，但这些知识通常散落在 Excel、Word、群消息里，只有出问题时才被翻出来，无法成为组织可持续使用的资产。

### RelOS 如何解决

在 `企业文档标注` 页面上传维修工单、供应商交期、交接班文档后，RelOS 会：

- 自动识别文档模板类型
- 从结构化字段或章节内容中抽取候选关系
- 将结果放入待审核队列
- 允许工程师确认后提交到图谱

这使“文档”第一次真正变成“可查询、可复用的关系知识”。

### 对应页面与接口

- 页面：`frontend/src/pages/knowledge/KnowledgeDocuments.jsx`
- 主要接口：
  - `POST /v1/documents/upload`
  - `GET /v1/documents/`
  - `GET /v1/documents/{doc_id}`
  - `POST /v1/documents/{doc_id}/annotate/{rel_id}`
  - `POST /v1/documents/{doc_id}/commit`

### 业务价值

- 降低知识录入成本
- 避免交接班和维修经验流失
- 让质量、运维、采购文档可以沉淀为统一知识底座

### 演示所需数据

- `data/demo/documents/cmms_workorder_m3.xlsx`
- `data/demo/documents/supplier_delay_q235.xlsx`
- `data/demo/documents/shift_handover_m3.docx`
- `relos/demo_data/llm_extract_mock_relations.json`

---

## 故事 3：把“不太确定”的 AI 关系变成人机协同可落地的知识飞轮

### 业务场景

很多一线知识并不是“完全确定”的。例如：某次温度告警是否真的影响工单、某次停机是否真的意味着某个部件故障。这类信息如果完全丢掉，系统学习速度很慢；如果直接自动写入，又会污染知识库。

### RelOS 如何解决

在 `提示标注工作区` 页面，RelOS 只把置信度处于 0.50–0.79 的关系推给工程师确认。工程师可以：

- 单条确认
- 单条否定
- 按类别筛选处理
- 批量确认当前队列

RelOS 通过这种方式实现“AI 先提议，人工再纠偏”的知识飞轮。

### 对应页面与接口

- 页面：`frontend/src/pages/runtime/PromptLabeling.jsx`
- 主要接口：
  - `GET /v1/relations/pending-review`
  - `POST /v1/relations/{id}/feedback`

### 业务价值

- 提高知识库准确率
- 让现场专家的确认动作直接转化为系统学习
- 建立可审计的人机协同流程

### 演示所需数据

- `scripts/seed_neo4j.py`
- `scripts/seed_demo_scenarios.py`

---

## 故事 4：早会中快速识别“哪条产线拖慢了整体”和“问题卡在哪个部门”

### 业务场景

车间早会上，生产经理常常只能看到“L2 效率低”“两个工单延期”“采购说在催货”，但很难把设备停机、物料短缺、工单阻塞串成一条统一的因果链。结果是多个部门各说各话，问题推进慢。

### RelOS 如何解决

在 `产线效率与运营分析` 页面，RelOS 将三类信息放在同一视角里：

- S-07：产线效率瓶颈
- S-08：跨部门协同因果链
- S-09：异常处理效率

这意味着班组长和生产经理不需要切换多个系统，就能快速定位瓶颈产线、关键设备、受影响工单和部门责任分布。

### 对应页面与接口

- 页面：`frontend/src/pages/LineEfficiency.jsx`
- 主要接口：
  - `GET /v1/scenarios/line-efficiency`
  - `GET /v1/scenarios/cross-dept-analysis`
  - `GET /v1/scenarios/issue-resolution`

### 业务价值

- 缩短早会定位问题时间
- 把“现象”转为“因果路径”
- 让生产、采购、计划拥有同一份问题视图

### 演示所需数据

- `scripts/seed_neo4j.py`
- `scripts/seed_demo_scenarios.py`

---

## 故事 5：发现夜班处理慢后，直接给出最值得投入的资源动作

### 业务场景

一线和设备主管经常已经知道“夜班处理慢”“设备稳定性差”“扩产会更危险”，但下一步究竟该优先加维保、做培训，还是先压扩产节奏，往往只能靠拍脑袋。

### RelOS 如何解决

在 `战略模拟与资源配置` 页面，RelOS 基于已有关系和历史弹性推演，给出：

- 资源优化建议与 ROI 排序
- 不同扩产比例下的交付风险、故障率、质量风险变化
- 扩产前建议动作

对一线负责人而言，这不是“宏大战略”，而是把现场问题转成更明确的资源优先级。

### 对应页面与接口

- 页面：`frontend/src/pages/StrategicSim.jsx`
- 主要接口：
  - `GET /v1/scenarios/resource-optimization`
  - `POST /v1/scenarios/strategic-simulation`

### 业务价值

- 把经验判断变成可解释的资源建议
- 让维保、培训、供应商管理的投入更有先后顺序
- 在扩产前提前暴露设备和交付风险

### 演示所需数据

- `scripts/seed_neo4j.py`
- `scripts/seed_demo_scenarios.py`

---

## 统一演示前置条件

1. 启动依赖服务与 API。
2. 执行 `python scripts/seed_neo4j.py`。
3. 执行 `python scripts/seed_demo_scenarios.py`。
4. 如需展示文档知识沉淀，准备 `data/demo/documents/` 下的样例文件。

## 选型说明

本批 5 个故事优先贴合当前已有页面与接口能力，不默认修改前端。这样交付后可以直接用于：

- 客户 POC
- 内部产品演示
- 一线培训与试运行讲解

如后续需要把这些故事进一步包装成更强的行业化版本，优先建议通过补 seed 数据、补上传样例和补讲解文案来扩展，而不是先改页面结构。
