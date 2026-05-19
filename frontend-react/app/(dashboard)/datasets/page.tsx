'use client'

import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import { Database, Plus, Upload, Trash2, ChevronDown, ChevronRight, Settings2, Lock, X, Check } from 'lucide-react'
import { toast } from 'sonner'
import type { DatasetItem, ColumnDef, Dataset } from '@/types'

// ---------------------------------------------------------------------------
// Default column schema (used when dataset has no column_schema)
// ---------------------------------------------------------------------------
const DEFAULT_SCHEMA: ColumnDef[] = [
  { key: 'input_data',      label: 'Input',           built_in: true },
  { key: 'expected_output', label: 'Expected Output', built_in: true },
]

function getSchema(ds: Dataset | undefined): ColumnDef[] {
  if (!ds?.column_schema || ds.column_schema.length === 0) return DEFAULT_SCHEMA
  return ds.column_schema
}

function extractText(val: unknown): string {
  if (!val) return '--'
  if (typeof val === 'string') return val
  const obj = val as Record<string, unknown>
  const text = obj.question ?? obj.answer ?? obj.text ?? obj.input ?? obj.output ?? obj.content
  if (text !== undefined) return String(text)
  return JSON.stringify(val)
}

// ---------------------------------------------------------------------------
// Column Manager panel
// ---------------------------------------------------------------------------
function ColumnManager({
  schema,
  onSave,
  onClose,
  isSaving,
}: {
  schema: ColumnDef[]
  onSave: (cols: ColumnDef[]) => void
  onClose: () => void
  isSaving: boolean
}) {
  const [cols, setCols] = useState<ColumnDef[]>(schema)
  const [newLabel, setNewLabel] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  function rename(idx: number, label: string) {
    setCols((prev) => prev.map((c, i) => (i === idx ? { ...c, label } : c)))
  }

  function addColumn() {
    if (!newLabel.trim()) return
    const key = 'col_' + Math.random().toString(36).slice(2, 8)
    setCols((prev) => [...prev, { key, label: newLabel.trim(), built_in: false }])
    setNewLabel('')
    inputRef.current?.focus()
  }

  function removeColumn(idx: number) {
    setCols((prev) => prev.filter((_, i) => i !== idx))
  }

  return (
    <div className="border rounded-xl bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">Manage Columns</p>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>
      <p className="text-xs text-muted-foreground">Rename any column. Built-in columns cannot be deleted. Custom columns are stored in item metadata.</p>
      <div className="space-y-1.5">
        {cols.map((col, idx) => (
          <div key={col.key} className="flex items-center gap-2">
            {col.built_in
              ? <span title="Built-in column (cannot delete)"><Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0" /></span>
              : <button onClick={() => removeColumn(idx)} className="text-muted-foreground hover:text-red-500 shrink-0"><X className="h-3.5 w-3.5" /></button>
            }
            <input
              value={col.label}
              onChange={(e) => rename(idx, e.target.value)}
              className="flex-1 text-sm px-2 py-1 border rounded bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <span className="text-[10px] font-mono text-muted-foreground/60 w-20 truncate shrink-0" title={col.key}>{col.key}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-2 pt-1 border-t">
        <input
          ref={inputRef}
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') addColumn() }}
          placeholder="New column name..."
          className="flex-1 text-sm px-2 py-1 border rounded bg-background focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <button onClick={addColumn} disabled={!newLabel.trim()}
          className="flex items-center gap-1 px-2.5 py-1 text-xs border rounded hover:bg-muted disabled:opacity-40">
          <Plus className="h-3.5 w-3.5" /> Add
        </button>
      </div>
      <div className="flex gap-2">
        <button onClick={() => onSave(cols)} disabled={isSaving}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-xs disabled:opacity-50">
          <Check className="h-3.5 w-3.5" />
          {isSaving ? 'Saving...' : 'Save Columns'}
        </button>
        <button onClick={onClose} className="px-3 py-1.5 border rounded-md text-xs hover:bg-muted">Cancel</button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ItemRow — dynamic columns
// ---------------------------------------------------------------------------
function ItemRow({ item, schema, onDelete }: { item: DatasetItem; schema: ColumnDef[]; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const meta = item.metadata as Record<string, unknown> | null
  const tags: string[] = Array.isArray((item as unknown as Record<string, unknown>).tags)
    ? (item as unknown as Record<string, string[]>).tags : []

  function cellValue(col: ColumnDef): string {
    if (col.key === 'input_data') return extractText(item.input_data)
    if (col.key === 'expected_output') return extractText(item.expected_output)
    return meta?.[col.key] !== undefined ? String(meta[col.key]) : '--'
  }

  return (
    <>
      <tr className="border-b hover:bg-muted/20 cursor-pointer transition-colors" onClick={() => setExpanded(!expanded)}>
        <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{item.id.slice(0, 8)}...</td>
        {schema.map((col) => (
          <td key={col.key} className="px-4 py-2.5 max-w-[200px]">
            <p className="text-xs line-clamp-2">{cellValue(col)}</p>
          </td>
        ))}
        <td className="px-4 py-2.5">
          <div className="flex items-center gap-1">
            <button onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="p-1 text-muted-foreground hover:text-red-500 rounded transition-colors">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
            {expanded ? <ChevronDown className="h-3 w-3 text-muted-foreground" /> : <ChevronRight className="h-3 w-3 text-muted-foreground" />}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-muted/10 border-b">
          <td colSpan={schema.length + 2} className="px-4 py-3">
            <div className="space-y-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">Full Input</p>
                <pre className="text-xs bg-background rounded-lg border p-3 whitespace-pre-wrap break-words font-mono leading-relaxed">
                  {item.input_data ? JSON.stringify(item.input_data, null, 2) : '--'}
                </pre>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">Expected Output</p>
                <pre className="text-xs bg-background rounded-lg border p-3 whitespace-pre-wrap break-words font-mono leading-relaxed">
                  {item.expected_output ? JSON.stringify(item.expected_output, null, 2) : '--'}
                </pre>
              </div>
              {meta && Object.keys(meta).length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">Metadata</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(meta).map(([k, v]) => (
                      <span key={k} className="px-2 py-0.5 bg-primary/10 text-primary rounded text-[11px] font-mono">
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {tags.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">Tags</p>
                  <div className="flex gap-1 flex-wrap">
                    {tags.map((t) => <span key={t} className="px-2 py-0.5 bg-muted rounded-full text-[11px]">{t}</span>)}
                  </div>
                </div>
              )}
              <p className="text-[11px] text-muted-foreground/60">
                ID: <span className="font-mono">{item.id}</span>
                {item.created_at && ` - Created: ${new Date(item.created_at).toLocaleString()}`}
              </p>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function DatasetsPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null)
  const [showColManager, setShowColManager] = useState(false)

  // Add item form state
  const [showAddItem, setShowAddItem] = useState(false)
  const [itemInput, setItemInput] = useState('')
  const [itemOutput, setItemOutput] = useState('')
  const [itemCustom, setItemCustom] = useState<Record<string, string>>({})
  const [itemTags, setItemTags] = useState('')

  // JSON import state
  const [showJsonImport, setShowJsonImport] = useState(false)
  const [jsonText, setJsonText] = useState('')

  const { data: datasets = [], isLoading } = useQuery({
    queryKey: ['datasets', project?.id],
    queryFn: () => api.datasets.list(project!.id),
    enabled: !!project,
  })

  const { data: items = [], refetch: refetchItems } = useQuery({
    queryKey: ['dataset-items', selectedDataset],
    queryFn: () => api.datasets.items(selectedDataset!),
    enabled: !!selectedDataset,
  })

  const selectedDs = datasets.find((d) => d.id === selectedDataset)
  const schema = getSchema(selectedDs)
  const customCols = schema.filter((c) => !c.built_in)

  const create = useMutation({
    mutationFn: () => api.datasets.create({ project_id: project!.id, name, description }),
    onSuccess: () => {
      toast.success('Dataset created')
      qc.invalidateQueries({ queryKey: ['datasets', project?.id] })
      setShowCreate(false); setName(''); setDescription('')
    },
    onError: () => toast.error('Failed to create dataset'),
  })

  const deleteDataset = useMutation({
    mutationFn: (id: string) => api.datasets.delete(id),
    onSuccess: (_, id) => {
      toast.success('Dataset deleted')
      qc.invalidateQueries({ queryKey: ['datasets', project?.id] })
      if (selectedDataset === id) setSelectedDataset(null)
    },
    onError: () => toast.error('Failed to delete dataset'),
  })

  const deleteItem = useMutation({
    mutationFn: ({ itemId }: { itemId: string }) => api.datasets.deleteItem(selectedDataset!, itemId),
    onSuccess: () => {
      toast.success('Item deleted')
      refetchItems()
      qc.invalidateQueries({ queryKey: ['datasets', project?.id] })
    },
    onError: () => toast.error('Failed to delete item'),
  })

  const addItem = useMutation({
    mutationFn: (payload: { input_data?: unknown; expected_output?: unknown; metadata?: Record<string, string>; tags?: string[] }) =>
      api.datasets.addItem(selectedDataset!, payload),
    onSuccess: () => {
      toast.success('Item added')
      refetchItems()
      qc.invalidateQueries({ queryKey: ['datasets', project?.id] })
      setItemInput(''); setItemOutput(''); setItemCustom({}); setItemTags(''); setShowAddItem(false)
    },
    onError: () => toast.error('Failed to add item'),
  })

  const importJson = useMutation({
    mutationFn: async (rows: { input?: string; input_data?: unknown; expected_output?: unknown; output?: string; metadata?: Record<string, string>; tags?: string[] }[]) => {
      for (const row of rows) {
        const input_data = row.input_data ?? (row.input ? { question: row.input } : undefined)
        const expected_output = row.expected_output ?? (row.output ? { answer: row.output } : undefined)
        if (!input_data) throw new Error('Each item must have an "input" or "input_data" field')
        if (!expected_output) throw new Error('Each item must have an "expected_output" or "output" field')
        await api.datasets.addItem(selectedDataset!, { input_data, expected_output, metadata: row.metadata, tags: row.tags })
      }
    },
    onSuccess: () => {
      toast.success('Items imported'); refetchItems()
      qc.invalidateQueries({ queryKey: ['datasets', project?.id] })
      setJsonText(''); setShowJsonImport(false)
    },
    onError: () => toast.error('Failed to import items'),
  })

  const updateSchema = useMutation({
    mutationFn: (cols: ColumnDef[]) => api.datasets.updateSchema(selectedDataset!, cols),
    onSuccess: () => {
      toast.success('Columns saved')
      qc.invalidateQueries({ queryKey: ['datasets', project?.id] })
      setShowColManager(false)
    },
    onError: () => toast.error('Failed to save columns'),
  })

  function handleSubmitItem() {
    if (!itemInput.trim()) { toast.error('Input is required'); return }
    if (!itemOutput.trim()) { toast.error('Expected Output is required'); return }
    const input_data = { question: itemInput.trim() }
    const expected_output = { answer: itemOutput.trim() }
    const tags = itemTags.split(',').map((t) => t.trim()).filter(Boolean)
    const metadata = Object.keys(itemCustom).length ? { ...itemCustom } : undefined
    addItem.mutate({ input_data, expected_output, metadata, tags: tags.length ? tags : undefined })
  }

  function handleJsonImport() {
    try {
      const parsed = JSON.parse(jsonText)
      if (!Array.isArray(parsed)) { toast.error('JSON must be an array of items'); return }
      importJson.mutate(parsed)
    } catch { toast.error('Invalid JSON') }
  }

  if (!project) {
    return <div className="flex items-center justify-center h-64 text-muted-foreground">Select a project</div>
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Datasets</h1>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">
          <Plus className="h-4 w-4" /> New Dataset
        </button>
      </div>

      {showCreate && (
        <div className="rounded-xl border bg-card p-5 space-y-3">
          <h2 className="font-medium">New Dataset</h2>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Dataset name"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (optional)" rows={2}
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-none" />
          <div className="flex gap-2">
            <button onClick={() => create.mutate()} disabled={!name || create.isPending}
              className="px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm disabled:opacity-50">
              {create.isPending ? 'Creating...' : 'Create'}
            </button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-1.5 border rounded-md text-sm hover:bg-muted">Cancel</button>
          </div>
        </div>
      )}

      <div className="flex gap-4 min-h-[400px]">
        {/* Dataset list */}
        <div className="w-72 shrink-0 space-y-2">
          {isLoading ? (
            <p className="text-sm text-muted-foreground p-4">Loading...</p>
          ) : datasets.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 gap-2 border rounded-xl">
              <Database className="h-7 w-7 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">No datasets</p>
            </div>
          ) : (
            datasets.map((ds) => (
              <div key={ds.id} className={`rounded-xl border transition-colors ${selectedDataset === ds.id ? 'border-primary bg-primary/5' : 'bg-card hover:bg-muted/30'}`}>
                <button className="w-full text-left p-4" onClick={() => { setSelectedDataset(ds.id === selectedDataset ? null : ds.id); setShowColManager(false) }}>
                  <div className="flex items-start gap-3">
                    <Database className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm truncate">{ds.name}</p>
                      <p className="text-xs text-muted-foreground">v{ds.version} - {ds.item_count ?? ds.example_count ?? 0} items</p>
                      <p className="text-xs text-muted-foreground">{formatDate(ds.created_at)}</p>
                    </div>
                    <button onClick={(e) => { e.stopPropagation(); if (confirm('Delete this dataset?')) deleteDataset.mutate(ds.id) }}
                      className="p-1 text-muted-foreground hover:text-red-500 rounded transition-colors shrink-0">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </button>
              </div>
            ))
          )}
        </div>

        {/* Items panel */}
        {selectedDataset && (
          <div className="flex-1 min-w-0 space-y-3">
            {/* Column Manager */}
            {showColManager && (
              <ColumnManager
                schema={schema}
                onSave={(cols) => updateSchema.mutate(cols)}
                onClose={() => setShowColManager(false)}
                isSaving={updateSchema.isPending}
              />
            )}

            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-medium">Dataset Items - {selectedDs?.name}</h2>
                  {selectedDs?.description && <p className="text-xs text-muted-foreground mt-0.5">{selectedDs.description}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{items.length} items</span>
                  <button onClick={() => { setShowColManager(!showColManager); setShowAddItem(false); setShowJsonImport(false) }}
                    className={`flex items-center gap-1 px-2.5 py-1 text-xs border rounded-md transition-colors ${showColManager ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'}`}>
                    <Settings2 className="h-3.5 w-3.5" /> Columns
                  </button>
                  <button onClick={() => { setShowJsonImport(!showJsonImport); setShowAddItem(false); setShowColManager(false) }}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs border rounded-md hover:bg-muted transition-colors">
                    <Upload className="h-3.5 w-3.5" /> Import JSON
                  </button>
                  <button onClick={() => { setShowAddItem(!showAddItem); setShowJsonImport(false); setShowColManager(false) }}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors">
                    <Plus className="h-3.5 w-3.5" /> Add Item
                  </button>
                </div>
              </div>

              {/* JSON Import */}
              {showJsonImport && (
                <div className="px-5 py-4 border-b bg-muted/20 space-y-3">
                  <p className="text-xs font-medium">
                    Paste a JSON array. Required: <span className="font-mono text-red-500">input</span> + <span className="font-mono text-red-500">expected_output</span>.
                    {customCols.length > 0 && <> Custom columns: {customCols.map(c => <span key={c.key} className="font-mono text-primary ml-1">{c.key}</span>)} go in <span className="font-mono">metadata</span>.</>}
                  </p>
                  <textarea value={jsonText} onChange={(e) => setJsonText(e.target.value)} rows={5}
                    placeholder={`[{"input": "...", "expected_output": "..."${customCols.length ? `, "metadata": {"${customCols[0].key}": "..."}` : ''}}]`}
                    className="w-full text-xs px-3 py-2 border rounded-md bg-background font-mono focus:outline-none focus:ring-1 focus:ring-ring resize-y" />
                  <div className="flex gap-2">
                    <button onClick={handleJsonImport} disabled={!jsonText.trim() || importJson.isPending}
                      className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-xs disabled:opacity-50">
                      {importJson.isPending ? 'Importing...' : 'Import'}
                    </button>
                    <button onClick={() => { setShowJsonImport(false); setJsonText('') }} className="px-3 py-1.5 border rounded-md text-xs hover:bg-muted">Cancel</button>
                  </div>
                </div>
              )}

              {/* Add Item Form */}
              {showAddItem && (
                <div className="px-5 py-4 border-b bg-muted/20 space-y-3">
                  <p className="text-xs font-semibold">New Item</p>
                  <div>
                    <label className="text-[11px] text-muted-foreground block mb-1">{schema.find(c => c.key === 'input_data')?.label ?? 'Input'} <span className="text-red-500">*</span></label>
                    <textarea value={itemInput} onChange={(e) => setItemInput(e.target.value)} rows={2}
                      placeholder="Enter the question or input prompt..."
                      className="w-full text-xs px-3 py-2 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-y" />
                  </div>
                  <div>
                    <label className="text-[11px] text-muted-foreground block mb-1">{schema.find(c => c.key === 'expected_output')?.label ?? 'Expected Output'} <span className="text-red-500">*</span></label>
                    <textarea value={itemOutput} onChange={(e) => setItemOutput(e.target.value)} rows={2}
                      placeholder="Enter the expected answer..."
                      className="w-full text-xs px-3 py-2 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-y" />
                  </div>
                  {customCols.map((col) => (
                    <div key={col.key}>
                      <label className="text-[11px] text-muted-foreground block mb-1">{col.label}</label>
                      <input
                        value={itemCustom[col.key] ?? ''}
                        onChange={(e) => setItemCustom((p) => ({ ...p, [col.key]: e.target.value }))}
                        placeholder={`Enter ${col.label.toLowerCase()}...`}
                        className="w-full text-xs px-3 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                      />
                    </div>
                  ))}
                  <div>
                    <label className="text-[11px] text-muted-foreground block mb-1">Tags (comma-separated, optional)</label>
                    <input value={itemTags} onChange={(e) => setItemTags(e.target.value)} placeholder="e.g. history, wwii, facts"
                      className="w-full text-xs px-3 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
                  </div>
                  <div className="flex gap-2">
                    <button onClick={handleSubmitItem} disabled={addItem.isPending || !itemInput.trim() || !itemOutput.trim()}
                      className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-xs disabled:opacity-50">
                      {addItem.isPending ? 'Saving...' : 'Save Item'}
                    </button>
                    <button onClick={() => { setShowAddItem(false); setItemInput(''); setItemOutput(''); setItemCustom({}); setItemTags('') }}
                      className="px-3 py-1.5 border rounded-md text-xs hover:bg-muted">Cancel</button>
                  </div>
                </div>
              )}

              <div className="overflow-auto max-h-[600px]">
                {items.length === 0 && !showAddItem && !showJsonImport ? (
                  <div className="flex flex-col items-center justify-center h-40 gap-2">
                    <Upload className="h-7 w-7 text-muted-foreground/40" />
                    <p className="text-sm text-muted-foreground">No items yet.</p>
                    <p className="text-xs text-muted-foreground">Use &ldquo;Add Item&rdquo; or &ldquo;Import JSON&rdquo; to add data.</p>
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/40">
                        <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">ID</th>
                        {schema.map((col) => (
                          <th key={col.key} className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">{col.label}</th>
                        ))}
                        <th className="px-4 py-2.5 w-16"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <ItemRow
                          key={item.id}
                          item={item}
                          schema={schema}
                          onDelete={() => { if (confirm('Delete this item?')) deleteItem.mutate({ itemId: item.id }) }}
                        />
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
