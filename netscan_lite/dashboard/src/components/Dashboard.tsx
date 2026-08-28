import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getStats, getGroupsDetail } from '../api'
import type { Stats, GroupDetail } from '../types'

const cardStyles = [
  { key: 'total', label: 'Total IPs', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  { key: 'active', label: 'Active', color: 'bg-green-50 text-green-700 border-green-200' },
  { key: 'uncertain', label: 'Uncertain', color: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  { key: 'available', label: 'Available', color: 'bg-teal-50 text-teal-700 border-teal-200' },
  { key: 'reserved', label: 'Reserved', color: 'bg-red-50 text-red-700 border-red-200' },
]

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [groups, setGroups] = useState<GroupDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getStats(), getGroupsDetail()])
      .then(([s, g]) => { setStats(s); setGroups(g) })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-2 text-gray-500">
        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
        Loading...
      </div>
    )
  }
  if (error) return <div className="p-8 text-red-500">{error}</div>
  if (!stats) return <div className="p-8 text-gray-500">No data</div>

  const statValues: Record<string, number> = {
    total: stats.total_ips,
    active: stats.active,
    uncertain: stats.uncertain,
    available: stats.available,
    reserved: stats.reserved,
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
        <div className="flex gap-3">
          <Link to="/scan" className="px-4 py-2 bg-teal-600 text-white text-sm rounded-md hover:bg-teal-700 transition-colors">
            Scan IPs
          </Link>
          <Link to="/import" className="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-md hover:bg-gray-50 transition-colors">
            Import
          </Link>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        {cardStyles.map((c) => (
          <div key={c.key} className={`rounded-lg border p-4 ${c.color}`}>
            <div className="text-xs font-medium opacity-75 mb-1">{c.label}</div>
            <div className="text-3xl font-bold">{statValues[c.key]}</div>
          </div>
        ))}
      </div>

      {/* Last scan */}
      {stats.last_scan && (
        <p className="text-sm text-gray-500 mb-6">
          Last scan: {new Date(stats.last_scan).toLocaleString()}
        </p>
      )}

      {/* Groups table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-700">Groups</h3>
          <Link to="/groups" className="text-sm text-teal-600 hover:text-teal-800">Manage</Link>
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-100">
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">IPs</th>
              <th className="px-4 py-2">Miss Threshold</th>
              <th className="px-4 py-2">Quarantine</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-medium text-gray-800">{g.name}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{g.ip_count}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{g.miss_threshold}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{g.quarantine_hours}h</td>
              </tr>
            ))}
            {groups.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-400">No groups yet — import some IPs to get started</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
