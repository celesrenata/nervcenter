/**
 * MockApiClient — returns representative fixtures for standalone rendering.
 * Used when VITE_API_BASE is unset (mock mode).
 */

export interface ApiResponse<T> {
  data: T
  status: number
}

// ─── Overview ──────────────────────────────────────────────────────────────────

export const mockOverview = {
  health: {
    status: 'healthy' as const,
    uptime: '14d 3h 22m',
    version: '0.4.1',
    lastCheck: '2026-09-28T23:55:00Z',
  },
  incidents: [
    {
      id: 'inc-001',
      title: 'GPU memory leak on esnixi worker',
      severity: 'high',
      status: 'active',
      createdAt: '2026-09-28T22:15:00Z',
      impact: 'Inference latency p95 up 40%',
    },
  ],
  goals: [
    {
      id: 'goal-001',
      title: 'Make HelloDJ video pipeline production ready',
      status: 'ACTIVE',
      progress: 72,
      dueDate: '2026-10-15',
    },
    {
      id: 'goal-002',
      title: 'Migrate inference fabric to local GPU cluster',
      status: 'ACTIVE',
      progress: 34,
      dueDate: '2026-11-01',
    },
    {
      id: 'goal-003',
      title: 'Reduce context compilation latency below 1s p95',
      status: 'ACTIVE',
      progress: 55,
      dueDate: '2026-10-30',
    },
  ],
  runningAgents: [
    { id: 'agent-001', name: 'investigator-1', status: 'running', task: 'Trace GPU memory leak' },
    { id: 'agent-002', name: 'correlator', status: 'running', task: 'Correlate deployment timeline' },
    { id: 'agent-003', name: 'verifier', status: 'verifying', task: 'Validate fix candidate' },
  ],
  taskConcurrency: {
    total: 8,
    running: 2,
    ready: 2,
    pending: 1,
    blocked: 1,
    verifying: 1,
    succeeded: 1,
    failed: 0,
  },
  computeUtilization: {
    totalNodes: 3,
    activeNodes: 2,
    avgGpuUtilization: 64,
    totalVRAMUsed: 28.4,
    totalVRAM: 39.5,
  },
  omniRouteActivity: {
    activeRoutes: 3,
    requestsPerMin: 42,
    avgLatency: 320,
    fallbackCount24h: 2,
  },
  recentDeployments: [
    { id: 'dep-042', system: 'nervecenter-api', version: '0.4.1', status: 'succeeded', at: '2026-09-28T20:00:00Z' },
    { id: 'dep-041', system: 'web-ui', version: '2.1.0', status: 'succeeded', at: '2026-09-28T18:30:00Z' },
    { id: 'dep-040', system: 'lavalink', version: '4.2.1', status: 'failed', at: '2026-09-28T14:00:00Z' },
  ],
  recentFailures: [
    { id: 'fail-001', system: 'lavalink', error: 'OOM killed', at: '2026-09-28T14:02:00Z' },
  ],
  pendingApprovals: [
    { id: 'appr-001', change: 'Rollback lavalink to 4.1.9', requestedBy: 'agent-001', at: '2026-09-28T22:20:00Z' },
    { id: 'appr-002', change: 'Scale esnixi GPU allocation +20%', requestedBy: 'scheduler', at: '2026-09-28T21:00:00Z' },
  ],
}

// ─── Task DAG (≥8 tasks, mixed states) ────────────────────────────────────────

export const mockTasks = [
  { task_id: 't-001', title: 'Collect evidence: GPU memory snapshots', state: 'SUCCEEDED', dependencies: [], capabilities: ['data-collection'], priority: 50 },
  { task_id: 't-002', title: 'Trace allocation stack (esnixi)', state: 'RUNNING', dependencies: ['t-001'], capabilities: ['repository-analysis'], priority: 90 },
  { task_id: 't-003', title: 'Trace allocation stack (gremlin-1)', state: 'RUNNING', dependencies: ['t-001'], capabilities: ['repository-analysis'], priority: 90 },
  { task_id: 't-004', title: 'Correlate with deployment timeline', state: 'READY', dependencies: ['t-001'], capabilities: ['temporal-analysis'], priority: 70 },
  { task_id: 't-005', title: 'Rank hypotheses for root cause', state: 'BLOCKED', dependencies: ['t-002', 't-003'], capabilities: ['hypothesis-ranking'], priority: 95 },
  { task_id: 't-006', title: 'Generate fix candidate', state: 'PENDING', dependencies: ['t-005'], capabilities: ['code-generation'], priority: 80 },
  { task_id: 't-007', title: 'Verify fix in staging', state: 'PENDING', dependencies: ['t-006'], capabilities: ['verification'], priority: 85 },
  { task_id: 't-008', title: 'Validate against regression suite', state: 'VERIFYING', dependencies: ['t-007'], capabilities: ['test-execution'], priority: 60 },
  { task_id: 't-009', title: 'Document root cause & permanent record', state: 'FAILED', dependencies: ['t-008'], capabilities: ['documentation'], priority: 40 },
]

// ─── Agents ────────────────────────────────────────────────────────────────────

export const mockAgents = [
  { id: 'agent-001', name: 'investigator-1', type: 'zoo', status: 'active', currentTask: 'Trace allocation stack (esnixi)', cpuUsage: 42, memoryUsage: 68, tasksCompleted: 14, tasksFailed: 1, lastHeartbeat: '2026-09-28T23:58:00Z' },
  { id: 'agent-002', name: 'correlator', type: 'native', status: 'active', currentTask: 'Correlate deployment timeline', cpuUsage: 23, memoryUsage: 45, tasksCompleted: 8, tasksFailed: 0, lastHeartbeat: '2026-09-28T23:57:30Z' },
  { id: 'agent-003', name: 'verifier', type: 'zoo', status: 'active', currentTask: 'Validate fix candidate', cpuUsage: 55, memoryUsage: 72, tasksCompleted: 22, tasksFailed: 2, lastHeartbeat: '2026-09-28T23:59:00Z' },
  { id: 'agent-004', name: 'documentation-bot', type: 'native', status: 'paused', currentTask: null, cpuUsage: 0, memoryUsage: 12, tasksCompleted: 5, tasksFailed: 0, lastHeartbeat: '2026-09-28T20:00:00Z' },
]

// ─── Compute nodes (§51 example) ──────────────────────────────────────────────

export const mockComputeNodes = [
  {
    id: 'node-esnixi',
    hostname: 'esnixi',
    hardware: 'RTX 5090',
    vram: '32 GB',
    gpuUtilization: 71,
    loadedModel: 'Qwen Code',
    tokensPerSec: 64,
    contextUsage: '32K / 128K',
    activeCalls: 3,
    latency: { p50: 280, p95: 620, p99: 900 },
    failures24h: 1,
    fallbacks24h: 0,
  },
  {
    id: 'node-gremlin-1',
    hostname: 'gremlin-1',
    hardware: 'RTX 4070 Ti SUPER',
    vram: '16 GB',
    gpuUtilization: 0,
    loadedModel: null,
    tokensPerSec: 0,
    contextUsage: null,
    activeCalls: 0,
    latency: null,
    failures24h: 0,
    fallbacks24h: 0,
  },
  {
    id: 'node-stabulous',
    hostname: 'stabulous',
    hardware: 'M5 Max',
    vram: '91 GB unified memory',
    gpuUtilization: 54,
    loadedModel: 'DeepSeek',
    tokensPerSec: 35,
    contextUsage: '48K / 256K',
    activeCalls: 2,
    latency: { p50: 410, p95: 1100, p99: 2000 },
    failures24h: 0,
    fallbacks24h: 1,
  },
]

// ─── OmniRoute routes ─────────────────────────────────────────────────────────

export const mockRoutes = [
  {
    routeId: 'route-coding',
    taskType: 'coding',
    chain: ['Qwen Code (esnixi)', 'Claude Sonnet (cloud)'],
    strategy: 'latency-first',
    activeCalls: 2,
    successRate: 0.97,
    avgLatency: 320,
  },
  {
    routeId: 'route-planning',
    taskType: 'planning',
    chain: ['DeepSeek (stabulous)', 'Claude Opus (cloud)'],
    strategy: 'quality-first',
    activeCalls: 1,
    successRate: 0.99,
    avgLatency: 1200,
  },
  {
    routeId: 'route-analysis',
    taskType: 'analysis',
    chain: ['Qwen Code (esnixi)'],
    strategy: 'cost-first',
    activeCalls: 0,
    successRate: 0.94,
    avgLatency: 280,
  },
]

// ─── Historical model performance ─────────────────────────────────────────────

export const mockModelHistory = [
  { model: 'Qwen Code', node: 'esnixi', window: '7d', avgTokPerSec: 62, p95Latency: 650, successRate: 0.97, fallbackRate: 0.02 },
  { model: 'DeepSeek', node: 'stabulous', window: '7d', avgTokPerSec: 34, p95Latency: 1150, successRate: 0.99, fallbackRate: 0.01 },
  { model: 'Claude Sonnet', node: 'cloud', window: '7d', avgTokPerSec: 48, p95Latency: 800, successRate: 0.98, fallbackRate: 0.00 },
]

// ─── Incidents ────────────────────────────────────────────────────────────────

export const mockIncidents = [
  {
    id: 'inc-001',
    title: 'GPU memory leak on esnixi worker',
    severity: 'high',
    status: 'active',
    createdAt: '2026-09-28T22:15:00Z',
    updatedAt: '2026-09-28T23:30:00Z',
    description: 'esnixi GPU memory usage grew monotonically from 6 GB to 29 GB over 4 hours. Inference p95 latency increased by 40%.',
    impact: 'Inference latency degraded; 1 fallback to cloud triggered',
    tags: ['gpu', 'memory-leak', 'esnixi', 'inference'],
  },
  {
    id: 'inc-002',
    title: 'Lavalink OOM restart',
    severity: 'medium',
    status: 'resolved',
    createdAt: '2026-09-28T14:02:00Z',
    updatedAt: '2026-09-28T15:30:00Z',
    description: 'Lavalink pod OOMKilled during peak usage. Auto-restarted by K3s. Root cause: undrained HLS buffer.',
    impact: '30s audio gap for 2 active sessions',
    tags: ['lavalink', 'oom', 'k8s'],
  },
]

// ─── Decisions ────────────────────────────────────────────────────────────────

export const mockDecisions = [
  {
    id: 'dec-001',
    title: 'Adopt local GPU cluster for primary inference',
    status: 'approved',
    createdAt: '2026-09-25T10:00:00Z',
    updatedAt: '2026-09-27T12:00:00Z',
    description: 'Route coding and analysis tasks to local GPU first; cloud fallback only for overflow.',
    rationale: 'Reduces latency by 40% and eliminates per-token billing for bulk workloads.',
    impact: 'Requires 2 GPU nodes with ≥16 GB VRAM each. Cloud cost projected to drop 60%.',
    approvers: ['celes'],
    tags: ['inference', 'cost', 'local-first'],
  },
  {
    id: 'dec-002',
    title: 'Use OmniRoute combo scoring for task routing',
    status: 'implemented',
    createdAt: '2026-09-20T08:00:00Z',
    updatedAt: '2026-09-22T16:00:00Z',
    description: 'Replace static routing with dynamic combo scoring based on latency, cost, and reliability.',
    rationale: 'Static routing wastes fast nodes on slow tasks and vice versa.',
    impact: 'Improved p50 latency by 28% in A/B test.',
    approvers: ['celes', 'system'],
    tags: ['routing', 'omniroute', 'performance'],
  },
]

// ─── Timeline / Events ────────────────────────────────────────────────────────

export const mockEvents = [
  { id: 'ev-001', timestamp: '2026-09-28T23:55:00Z', type: 'agent_progress', entity: 'investigator-1', message: 'Found suspicious allocation in tensor cache module', severity: 'info' },
  { id: 'ev-002', timestamp: '2026-09-28T23:40:00Z', type: 'task_state_change', entity: 't-008', message: 'Task "Validate against regression suite" entered VERIFYING', severity: 'info' },
  { id: 'ev-003', timestamp: '2026-09-28T23:30:00Z', type: 'incident_update', entity: 'inc-001', message: 'Incident severity confirmed HIGH — memory leak reproduced', severity: 'warning' },
  { id: 'ev-004', timestamp: '2026-09-28T22:15:00Z', type: 'incident_created', entity: 'inc-001', message: 'New incident: GPU memory leak on esnixi', severity: 'error' },
  { id: 'ev-005', timestamp: '2026-09-28T20:00:00Z', type: 'deployment', entity: 'nervecenter-api', message: 'Deployed v0.4.1 to K3s cluster', severity: 'success' },
  { id: 'ev-006', timestamp: '2026-09-28T18:30:00Z', type: 'deployment', entity: 'web-ui', message: 'Deployed v2.1.0 (web UI rebuild)', severity: 'success' },
  { id: 'ev-007', timestamp: '2026-09-28T14:02:00Z', type: 'failure', entity: 'lavalink', message: 'Lavalink pod OOMKilled', severity: 'error' },
]

// ─── Systems health ───────────────────────────────────────────────────────────

export const mockSystems = [
  { name: 'nervecenter-api', status: 'healthy', version: '0.4.1', message: 'All subsystems operational', checkedAt: '2026-09-28T23:55:00Z' },
  { name: 'postgres', status: 'healthy', version: '16.2', message: 'pgvector extension loaded', checkedAt: '2026-09-28T23:55:00Z' },
  { name: 'nats', status: 'healthy', version: '2.10', message: 'JetStream 3 streams active', checkedAt: '2026-09-28T23:55:00Z' },
  { name: 'lavalink', status: 'degraded', version: '4.2.1', message: 'Recovered from OOM; monitoring memory', checkedAt: '2026-09-28T23:50:00Z' },
  { name: 'web-ui', status: 'healthy', version: '2.1.0', message: 'Serving via nginx', checkedAt: '2026-09-28T23:55:00Z' },
  { name: 'k3s', status: 'healthy', version: '1.30', message: '4/4 nodes Ready', checkedAt: '2026-09-28T23:55:00Z' },
]

// ─── Ask (provenance) ────────────────────────────────────────────────────────

export const mockAskResponse = {
  answer: 'The GPU memory leak on esnixi is most likely caused by the tensor cache in the Qwen Code model loader. Evidence shows the allocation pattern correlates with deployment 29211 which introduced a new caching layer without eviction policy.',
  confidence: 0.87,
  facts: [
    {
      statement: 'esnixi GPU memory grew from 6 GB to 29 GB over 4 hours',
      type: 'FACT' as const,
      confidence: 1.0,
      evidence: ['snapshot:22:00', 'snapshot:26:00', 'monitoring:gpu-mem'],
    },
    {
      statement: 'Deployment 29211 introduced tensor_cache module',
      type: 'FACT' as const,
      confidence: 1.0,
      evidence: ['commit:81fa93', 'deployment:29211', 'diff:cache-init'],
    },
  ],
  hypotheses: [
    {
      statement: 'The new tensor_cache lacks an LRU eviction policy, causing unbounded growth',
      type: 'HYPOTHESIS' as const,
      confidence: 0.87,
      evidence: ['code:cache.py:42', 'benchmark:no-eviction', 'snapshot:after'],
    },
    {
      statement: 'Memory leak is a driver issue unrelated to software change',
      type: 'HYPOTHESIS' as const,
      confidence: 0.12,
      evidence: ['driver:555.12', 'no-prior-incidents'],
    },
  ],
}

// ─── Goals ────────────────────────────────────────────────────────────────────

export const mockGoals = mockOverview.goals.map((g) => ({
  id: g.id,
  name: g.title,
  description: `Working toward: ${g.title}`,
  status: 'active' as const,
  progress: g.progress,
  dueDate: g.dueDate,
}))

// ─── Models ───────────────────────────────────────────────────────────────────

export const mockModels = [
  { id: 'model-qwen-code', name: 'Qwen Code', provider: 'local', node: 'esnixi', contextWindow: 128000, status: 'loaded' },
  { id: 'model-deepseek', name: 'DeepSeek', provider: 'local', node: 'stabulous', contextWindow: 256000, status: 'loaded' },
  { id: 'model-claude-sonnet', name: 'Claude 3.5 Sonnet', provider: 'cloud', node: 'api.anthropic.com', contextWindow: 200000, status: 'available' },
  { id: 'model-claude-opus', name: 'Claude 3 Opus', provider: 'cloud', node: 'api.anthropic.com', contextWindow: 200000, status: 'available' },
]
