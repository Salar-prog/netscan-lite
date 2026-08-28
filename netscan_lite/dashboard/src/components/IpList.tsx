import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getGroupsDetail, listIPs } from '../api'
import type { GroupDetail, IPListItem, IPStatus } from '../types'

const statusBadge: Record<IPStatus, string> = {
  ACTIVE_DETECTED: 'bg-green-100 text-green-800',
  AVAILABLE_CANDIDATE: 'bg-teal-100 text-teal-800',
  UNCERTAIN_FIREWALLED: 'bg-yellow-100 text-yellow-800',
  ASSIGNED_RESERVED: 'bg-red-100 text-red-800',
}

const statusOptions = [
  { value: '', label: 'All statuses' },
  { value: 'ACTIVE_DETECTED', label: 'Active' },
  { value: 'AVAILABLE_CANDIDATE', label: 'Available' },
  { value: 'UNCERTAIN_FIREWALLED', label: 'Uncertain' },
  { value: 'ASSIGNED_RESERVED', label: 'Reserved' },
]

export default function IpList() {
  const [groups, setGroups] = useState<GroupDetail[]>([])
  const [ips, setIps] = useState<IPListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [selectedGroup, setSelectedGroup] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const pageSize = 25

  useEffect(() => {
    getGroupsDetail().then(setGroups).catch(console.error)
  }, [])

  const fetchIPs = () => {
    setLoading(true)
    listIPs({
      group: selectedGroup || undefined,
      status: selectedStatus || undefined,
      search: search || undefined,
      page,
      page_size: pageSize,
    })
      .then((r) => { setIps(r.ips); setTotal(r.total) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchIPs() }, [page, selectedGroup, selectedStatus])

  const handleSearch = () => { setPage(1); fetchIPs() }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">IP Addresses</h2>

      {/* Filters */}
      <div className="flex gap-4 mb-6 items-end flex-wrap">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Group</label>
          <select
            value={selectedGroup}
            onChange={(e) => { setSelectedGroup(e.target.value); setPage(1) }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            <option value="">All groups</option>
            {groups.map((g) => (
              <option key={g.id} value={g.name}>{g.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
          <select
            value={selectedStatus}
            onChange={(e) => { setSelectedStatus(e.target.value); setPage(1) }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            {statusOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-gray-500 mb-1">Search</label>
          <div className="flex">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="IP or hostname"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-l-md text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
            <button
              onClick={handleSearch}
              className="px-4 py-2 bg-teal-600 text-white text-sm rounded-r-md hover:bg-teal-700"
            >
              Search
            </button>
          </div>
        </div>
      </div>

      {/* IP table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-100">
              <th className="px-4 py-2">IP Address</th>
              <th className="px-4 py-2">Hostname</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Group</th>
              <th className="px-4 py-2">Misses</th>
              <th className="px-4 py-2">Last Seen</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {ips.map((ip) => (
              <tr key={ip.ip} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-mono text-gray-800">{ip.ip}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{ip.hostname || '—'}</td>
                <td className="px-4 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusBadge[ip.status]}`}>
                    {ip.status.replace('_', ' ')}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-600">{ip.group_name || '—'}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{ip.consecutive_misses}</td>
                <td className="px-4 py-2 text-sm text-gray-600">
                  {ip.last_seen_at ? new Date(ip.last_seen_at).toLocaleDateString() : '—'}
                </td>
                <td className="px-4 py-2">
                  <Link to={`/ips/${ip.ip}`} className="text-sm text-teal-600 hover:text-teal-800">
                    Details
                  </Link>
                </td>
              </tr>
            ))}
            {ips.length === 0 && !loading && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-400">No IPs found</td></tr>
            )}
            {loading && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-400">Loading...</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              Previous
            </button>
            <span className="px-3 py-1 text-sm text-gray-600">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
