import { useEffect, useState } from 'react'
import { getGroupsDetail, updateGroup, deleteGroup } from '../api'
import type { GroupDetail } from '../types'

export default function GroupManager() {
  const [groups, setGroups] = useState<GroupDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<GroupDetail | null>(null)
  const [editForm, setEditForm] = useState({ miss_threshold: 3, quarantine_hours: 48, description: '' })
  const [deleting, setDeleting] = useState<GroupDetail | null>(null)
  const [error, setError] = useState('')

  const fetchGroups = () => {
    setLoading(true)
    getGroupsDetail()
      .then(setGroups)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchGroups() }, [])

  const handleEdit = (g: GroupDetail) => {
    setEditing(g)
    setEditForm({ miss_threshold: g.miss_threshold, quarantine_hours: g.quarantine_hours, description: g.description || '' })
  }

  const handleSave = async () => {
    if (!editing) return
    try {
      await updateGroup(editing.id, editForm)
      setEditing(null)
      fetchGroups()
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleDelete = async () => {
    if (!deleting) return
    try {
      await deleteGroup(deleting.id)
      setDeleting(null)
      fetchGroups()
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Groups</h2>

      {error && (
        <div className="bg-red-50 text-red-700 text-sm px-3 py-2 rounded-md mb-4">{error}</div>
      )}

      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-100">
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">IPs</th>
              <th className="px-4 py-2">Miss Threshold</th>
              <th className="px-4 py-2">Quarantine Hours</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-medium text-gray-800">{g.name}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{g.ip_count}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{g.miss_threshold}</td>
                <td className="px-4 py-2 text-sm text-gray-600">{g.quarantine_hours}h</td>
                <td className="px-4 py-2 text-sm space-x-2">
                  <button onClick={() => handleEdit(g)} className="text-teal-600 hover:text-teal-800">Edit</button>
                  <button onClick={() => setDeleting(g)} className="text-red-600 hover:text-red-800">Delete</button>
                </td>
              </tr>
            ))}
            {groups.length === 0 && !loading && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">No groups yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Edit Group: {editing.name}</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Miss Threshold</label>
                <input
                  type="number"
                  value={editForm.miss_threshold}
                  onChange={(e) => setEditForm({ ...editForm, miss_threshold: Number(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Quarantine Hours</label>
                <input
                  type="number"
                  value={editForm.quarantine_hours}
                  onChange={(e) => setEditForm({ ...editForm, quarantine_hours: Number(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setEditing(null)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
                Cancel
              </button>
              <button onClick={handleSave} className="px-4 py-2 bg-teal-600 text-white text-sm rounded-md hover:bg-teal-700">
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {deleting && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold mb-2">Delete Group</h3>
            <p className="text-sm text-gray-600 mb-4">
              Delete <strong>{deleting.name}</strong> and all {deleting.ip_count} IPs in it? This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDeleting(null)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
                Cancel
              </button>
              <button onClick={handleDelete} className="px-4 py-2 bg-red-600 text-white text-sm rounded-md hover:bg-red-700">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
