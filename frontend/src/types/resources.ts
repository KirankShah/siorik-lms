// Mirrors resources.serializers.ResourceSerializer. `file` is intentionally
// absent — it's write_only on the backend (accepted on upload, never echoed
// back), so the raw storage path is never handed to a client; the protected
// viewer fetches PDF bytes exclusively through ResourceViewSet.stream.
export interface Resource {
  id: number
  organization: number
  title: string
  description: string
  uploaded_by: number | null
  uploaded_by_name: string | null
  uploaded_at: string
  can_delete: boolean
}

export interface ResourceUploadInput {
  title: string
  description: string
  file: File
}
