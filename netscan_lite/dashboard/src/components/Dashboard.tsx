import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getStats, getGroupsDetail } from '../api'
import type { Stats, GroupDetail } from '../types'

const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  uncertain: 'bg-yellow-100 text-yellow-800',
  available: 'bg-teal-100 text-teal-800',
  reserved: 'bg-red-100 text-red-800',
  total: 'bg-blue-100 text-blue-800',
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [groups, setGroups] = useState<GroupDetail[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getStats(), getGroupsDetail()])
      .then(([s, g]) => { setStats(s); setGroups(g) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>
  if (!stats) return <div className="p-8 text-red-500">Failed to load stats</div>

  const cards = [
    { label: 'Total IPs', value: stats.total_ips, color: statusColors.total },
    { label: 'Active', value: stats.active, color: statusColors.active },
    { label: 'Uncertain', value: stats.uncertain, color: statusColors.uncertain },
    { label: 'Available', value: stats.available, color: statusColors.available },
    { label: 'Reserved', value: stats.reserved, color: statusColors.reserved },
  ]

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
        <div className="flex gap-3">
          <Link to="/scan" className="px-4 py-2 bg-teal-600 text-white text-sm rounded-md hover:bg-teal-700">
            Scan All
          </Link>
          <Link to="/import" className="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-md hover:bg-gray-50">
            Import IPs
          </Link>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${c.color} mb-2`}>
              {c.label}
            </div>
            <div className="text-3xl font-bold text-gray-800">{c.value}</div>
          </div>
        ))}
      </div>

      {/* Last scan */}
      {stats.last_scan && (
        <p className="text-sm text-gray-500 mb-6">Last scan: {new Date(stats.last_scan).toLocaleString()}</p>
      )}

      {/* Groups table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="font-semibold text-gray-700">Groups</h3>
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-100">
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">IPs</th>
              <th className="px-4 py-2">Miss Threshold</th>
              <th className="px-4 py-2">Quarantine Hours</th>
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
              <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-400">No groups yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
