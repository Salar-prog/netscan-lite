import { useEffect, useState } from 'react'
import { getGroupsDetail, connectScanWS } from '../api'
import type { GroupDetail, WSMessage, IPStatus } from '../types'

const resultColor: Record<string, string> = {
  ACTIVE_DETECTED: 'text-green-600',
  AVAILABLE_CANDIDATE: 'text-teal-600',
  UNCERTAIN_FIREWALLED: 'text-yellow-600',
  ASSIGNED_RESERVED: 'text-red-600',
}

interface ScanProgress {
  ip: string
  status: 'scanning' | 'done'
  result?: IPStatus
}

export default function ScanTrigger() {
  const [groups, setGroups] = useState<GroupDetail[]>([])
  const [mode, setMode] = useState<'group' | 'ips'>('group')
  const [selectedGroup, setSelectedGroup] = useState('')
  const [ipList, setIpList] = useState('')
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState<ScanProgress[]>([])
  const [complete, setComplete] = useState<{ scanned: number; active: number; uncertain: number; available: number } | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getGroupsDetail().then((g) => {
      setGroups(g)
      if (g.length > 0) setSelectedGroup(g[0].name)
    }).catch(console.error)
  }, [])

  const handleScan = () => {
    setScanning(true)
    setProgress([])
    setComplete(null)
    setError('')

    const ws = connectScanWS((msg: WSMessage) => {
      if (msg.type === 'progress') {
        setProgress((prev) => {
          const exists = prev.find((p) => p.ip === msg.ip)
          if (exists) {
            return prev.map((p) => p.ip === msg.ip ? { ...p, status: msg.status, result: msg.result } : p)
          }
          return [...prev, { ip: msg.ip, status: msg.status, result: msg.result }]
        })
      } else if (msg.type === 'complete') {
        setComplete(msg)
        setScanning(false)
        ws.close()
      } else if (msg.type === 'error') {
        setError(msg.detail)
        setScanning(false)
        ws.close()
      }
    })

    ws.onopen = () => {
      const payload = mode === 'group'
        ? { group: selectedGroup }
        : { ips: ipList.split(',').map((s) => s.trim()).filter(Boolean) }
      ws.send(JSON.stringify(payload))
    }

    ws.onerror = () => {
      setError('WebSocket connection failed')
      setScanning(false)
    }
  }

  const totalIPs = progress.length
  const doneIPs = progress.filter((p) => p.status === 'done').length
  const percent = totalIPs > 0 ? Math.round((doneIPs / totalIPs) * 100) : 0

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Scan</h2>

      {/* Target selection */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex gap-4 mb-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" checked={mode === 'group'} onChange={() => setMode('group')} className="text-teal-600" />
            By Group
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" checked={mode === 'ips'} onChange={() => setMode('ips')} className="text-teal-600" />
            Specific IPs
          </label>
        </div>

        {mode === 'group' ? (
          <select
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            {groups.map((g) => (
              <option key={g.id} value={g.name}>{g.name} ({g.ip_count} IPs)</option>
            ))}
          </select>
        ) : (
          <textarea
            value={ipList}
            onChange={(e) => setIpList(e.target.value)}
            placeholder="10.0.0.1, 10.0.0.5, 10.0.0.12"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono focus:outline-none focus:ring-2 focus:ring-teal-500"
            rows={3}
          />
        )}

        <button
          onClick={handleScan}
          disabled={scanning || (mode === 'group' && !selectedGroup) || (mode === 'ips' && !ipList.trim())}
          className="mt-4 px-6 py-2 bg-teal-600 text-white text-sm rounded-md hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {scanning ? 'Scanning...' : 'Start Scan'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 text-sm px-3 py-2 rounded-md mb-4">{error}</div>
      )}

      {/* Progress */}
      {scanning && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>Progress</span>
            <span>{doneIPs} / {totalIPs} ({percent}%)</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-teal-600 h-2 rounded-full transition-all" style={{ width: `${percent}%` }} />
          </div>
        </div>
      )}

      {/* Live results feed */}
      {progress.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h3 className="font-semibold text-gray-700 mb-3">Results</h3>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {progress.map((p) => (
              <div key={p.ip} className="flex items-center gap-3 text-sm font-mono">
                <span className="w-32">{p.ip}</span>
                {p.status === 'scanning' ? (
                  <span className="text-gray-400">scanning...</span>
                ) : (
                  <span className={resultColor[p.result || ''] || 'text-gray-600'}>{p.result}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      {complete && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-700 mb-3">Scan Complete</h3>
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-gray-800">{complete.scanned}</div>
              <div className="text-xs text-gray-500">Scanned</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-600">{complete.active}</div>
              <div className="text-xs text-gray-500">Active</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow-600">{complete.uncertain}</div>
              <div className="text-xs text-gray-500">Uncertain</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-teal-600">{complete.available}</div>
              <div className="text-xs text-gray-500">Available</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
