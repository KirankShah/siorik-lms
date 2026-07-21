export interface Certificate {
  id: number
  user: number
  course: number
  issued_at: string
  certificate_number: string
  verification_token: string
  pdf_file: string | null
  expires_at: string | null
}
