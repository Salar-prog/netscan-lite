import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getGroups, getAvailable } from '../api'
import type { Group, IPStatus } from '../types'

// ponytail: IP list is client-filtered from /api/available + /api/ips
// Full implementation needs a list-all endpoint; for now we show available IPs.
// Add when: the backend adds GET /api/ips (paginated list).

const statusBadge: Record<IPStatus, string> = {
  ACTIVE_DETECTED: 'bg-green-100 text-green-800',
  AVAILABLE_CANDIDATE: 'bg-teal-100 text-teal-800',
  UNCERTAIN_FIREWALLED: 'bg-yellow-100 text-yellow-800',
  ASSIGNED_RESERVED: 'bg-red-100 text-red-800',
}

export default function IpList() {
  const [groups, setGroups] = useState<Group[]>([])
  const [selectedGroup, setSelectedGroup] = useState('')
  const [count, setCount] = useState(50)
  const [ips, setIps] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getGroups().then(setGroups).catch(console.error)
  }, [])

  const fetchIPs = () => {
    setLoading(true)
    getAvailable(selectedGroup || undefined, count)
      .then((r) => setIps(r.available_ips))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchIPs() }, [])

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">IP Addresses</h2>

      {/* Filters */}
      <div className="flex gap-4 mb-6 items-end">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Group</label>
          <select
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            <option value="">All groups</option>
            {groups.map((g) => (
              <option key={g.id} value={g.name}>{g.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Show available</label>
          <input
            type="number"
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            min={1}
            max={100}
            className="w-20 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          />
        </div>
        <button
          onClick={fetchIPs}
          className="px-4 py-2 bg-teal-600 text-white text-sm rounded-md hover:bg-teal-700"
        >
          Refresh
        </button>
      </div>

      {/* IP list */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-100">
              <th className="px-4 py-2">IP Address</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {ips.map((ip) => (
              <tr key={ip} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-mono text-gray-800">{ip}</td>
                <td className="px-4 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusBadge.AVAILABLE_CANDIDATE}`}>
                    AVAILABLE_CANDIDATE
                  </span>
                </td>
                <td className="px-4 py-2">
                  <Link to={`/ips/${ip}`} className="text-sm text-teal-600 hover:text-teal-800">
                    Details
                  </Link>
                </td>
              </tr>
            ))}
            {ips.length === 0 && !loading && (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-sm text-gray-400">No available IPs</td></tr>
            )}
            {loading && (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-sm text-gray-400">Loading...</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
