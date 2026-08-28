import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getIP, reserveIP } from '../api'
import type { IPAddress, IPStatus } from '../types'

const statusBadge: Record<IPStatus, string> = {
  ACTIVE_DETECTED: 'bg-green-100 text-green-800',
  AVAILABLE_CANDIDATE: 'bg-teal-100 text-teal-800',
  UNCERTAIN_FIREWALLED: 'bg-yellow-100 text-yellow-800',
  ASSIGNED_RESERVED: 'bg-red-100 text-red-800',
}

export default function IpDetail() {
  const { ip } = useParams<{ ip: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<IPAddress | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!ip) return
    getIP(ip)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [ip])

  const handleReserve = async () => {
    if (!data) return
    const newStatus = data.status === 'ASSIGNED_RESERVED' ? 'AVAILABLE_CANDIDATE' : 'ASSIGNED_RESERVED'
    try {
      await reserveIP(data.ip, newStatus)
      setData({ ...data, status: newStatus as IPStatus })
    } catch (err: any) {
      setError(err.message)
    }
  }

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>
  if (error) return <div className="p-8 text-red-500">{error}</div>
  if (!data) return <div className="p-8 text-gray-500">IP not found</div>

  return (
    <div className="p-8">
      <button onClick={() => navigate('/ips')} className="text-sm text-teal-600 hover:text-teal-800 mb-4">
        &larr; Back to IPs
      </button>

      <div className="flex items-center gap-4 mb-6">
        <h2 className="text-2xl font-bold text-gray-800 font-mono">{data.ip}</h2>
        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusBadge[data.status]}`}>
          {data.status}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Info card */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-700 mb-4">Details</h3>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Hostname</dt>
              <dd className="text-gray-800">{data.hostname || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">MAC Address</dt>
              <dd className="text-gray-800 font-mono">{data.mac_address || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">MAC Vendor</dt>
              <dd className="text-gray-800">{data.mac_vendor || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Discovery Method</dt>
              <dd className="text-gray-800">{data.discovery_method || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Consecutive Misses</dt>
              <dd className="text-gray-800">{data.consecutive_misses}</dd>
            </div>
          </dl>
        </div>

        {/* Timestamps */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-700 mb-4">Timestamps</h3>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">First Seen</dt>
              <dd className="text-gray-800">{data.first_seen_at ? new Date(data.first_seen_at).toLocaleString() : '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Last Seen</dt>
              <dd className="text-gray-800">{data.last_seen_at ? new Date(data.last_seen_at).toLocaleString() : '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Last Scanned</dt>
              <dd className="text-gray-800">{data.last_scanned_at ? new Date(data.last_scanned_at).toLocaleString() : '—'}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Actions */}
      <div className="mt-6 flex gap-3">
        <button
          onClick={handleReserve}
          className={`px-4 py-2 text-sm rounded-md ${
            data.status === 'ASSIGNED_RESERVED'
              ? 'bg-green-600 text-white hover:bg-green-700'
              : 'bg-red-600 text-white hover:bg-red-700'
          }`}
        >
          {data.status === 'ASSIGNED_RESERVED' ? 'Release IP' : 'Reserve IP'}
        </button>
      </div>

      {/* Open ports */}
      {data.open_ports.length > 0 && (
        <div className="mt-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-700 mb-4">Open Ports</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase">
                <th className="pb-2">Port</th>
                <th className="pb-2">Protocol</th>
                <th className="pb-2">State</th>
                <th className="pb-2">Service</th>
              </tr>
            </thead>
            <tbody>
              {data.open_ports.map((p, i) => (
                <tr key={i} className="border-t border-gray-100">
                  <td className="py-1 font-mono">{p.port}</td>
                  <td className="py-1">{p.protocol}</td>
                  <td className="py-1">{p.state}</td>
                  <td className="py-1">{p.service}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
