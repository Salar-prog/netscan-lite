import { useEffect, useState, useRef } from 'react'
import { getGroups, importFile } from '../api'
import type { Group, ImportResponse } from '../types'

export default function Import() {
  const [groups, setGroups] = useState<Group[]>([])
  const [selectedGroup, setSelectedGroup] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<ImportResponse | null>(null)
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getGroups().then(setGroups).catch(console.error)
  }, [])

  const handleFile = (f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase()
    if (ext !== 'csv' && ext !== 'xlsx') {
      setError('Only .csv and .xlsx files are supported')
      return
    }
    setFile(f)
    setError('')
    setResult(null)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleImport = async () => {
    if (!file) return
    setImporting(true)
    setError('')
    try {
      const res = await importFile(file, selectedGroup || undefined)
      setResult(res)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setImporting(false)
    }
  }

  const reset = () => {
    setFile(null)
    setResult(null)
    setError('')
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Import IPs</h2>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {/* Group override */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Group Override (optional)</label>
          <select
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            <option value="">Use group from file</option>
            {groups.map((g) => (
              <option key={g.id} value={g.name}>{g.name}</option>
            ))}
          </select>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            dragOver ? 'border-teal-500 bg-teal-50' : 'border-gray-300 hover:border-teal-400'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            className="hidden"
          />
          {file ? (
            <div>
              <p className="text-sm font-medium text-gray-800">{file.name}</p>
              <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-gray-600">Drop a CSV or XLSX file here, or click to browse</p>
              <p className="text-xs text-gray-400 mt-1">Columns: ip (required), hostname (optional), group (optional)</p>
            </div>
          )}
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 text-sm px-3 py-2 rounded-md mt-4">{error}</div>
        )}

        {/* Actions */}
        <div className="flex gap-3 mt-4">
          <button
            onClick={handleImport}
            disabled={!file || importing}
            className="px-4 py-2 bg-teal-600 text-white text-sm rounded-md hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {importing ? 'Importing...' : 'Import'}
          </button>
          {file && (
            <button onClick={reset} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mt-6">
          <h3 className="font-semibold text-gray-700 mb-3">Import Results</h3>
          <div className="grid grid-cols-3 gap-4 text-center mb-4">
            <div>
              <div className="text-2xl font-bold text-green-600">{result.imported}</div>
              <div className="text-xs text-gray-500">Imported</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow-600">{result.skipped}</div>
              <div className="text-xs text-gray-500">Skipped</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-red-600">{result.errors.length}</div>
              <div className="text-xs text-gray-500">Errors</div>
            </div>
          </div>
          {result.errors.length > 0 && (
            <div className="bg-red-50 rounded-md p-3">
              <p className="text-xs font-medium text-red-700 mb-1">Errors:</p>
              <ul className="text-xs text-red-600 space-y-0.5">
                {result.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
          <button onClick={reset} className="mt-4 text-sm text-teal-600 hover:text-teal-800">
            Import Another
          </button>
        </div>
      )}
    </div>
  )
}
