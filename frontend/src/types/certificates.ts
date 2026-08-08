export interface Certificate {
  id: number
  user: number
  course: number
  course_title: string
  issued_at: string
  certificate_number: string
  verification_token: string
  pdf_file: string | null
  expires_at: string | null
}

export type TextAlign = 'LEFT' | 'CENTER' | 'RIGHT'

// Mirrors CertificateTemplateSerializer. background_image/font_file fields
// are URLs when read, or a File instance when writing a new upload — see
// buildCertificateTemplateFormData in lib/certificatesApi.ts.
export interface CertificateTemplate {
  id: number
  name: string
  background_image: string
  is_default: boolean

  staff_name_x_percent: number
  staff_name_y_percent: number
  staff_name_font_size: number
  staff_name_color: string
  staff_name_font_file: string | null
  staff_name_text_align: TextAlign

  course_name_x_percent: number
  course_name_y_percent: number
  course_name_font_size: number
  course_name_color: string
  course_name_font_file: string | null
  course_name_text_align: TextAlign

  issue_date_x_percent: number
  issue_date_y_percent: number
  issue_date_font_size: number
  issue_date_color: string
  issue_date_font_file: string | null
  issue_date_text_align: TextAlign

  qr_code_x_percent: number
  qr_code_y_percent: number
  qr_code_size_percent: number

  created_at: string
  updated_at: string
}

export type CertificateTemplateFieldName = 'staff_name' | 'course_name' | 'issue_date'

export interface CertificateTemplateInput {
  name?: string
  background_image?: File
  is_default?: boolean

  staff_name_x_percent?: number
  staff_name_y_percent?: number
  staff_name_font_size?: number
  staff_name_color?: string
  staff_name_font_file?: File
  staff_name_text_align?: TextAlign

  course_name_x_percent?: number
  course_name_y_percent?: number
  course_name_font_size?: number
  course_name_color?: string
  course_name_font_file?: File
  course_name_text_align?: TextAlign

  issue_date_x_percent?: number
  issue_date_y_percent?: number
  issue_date_font_size?: number
  issue_date_color?: string
  issue_date_font_file?: File
  issue_date_text_align?: TextAlign

  qr_code_x_percent?: number
  qr_code_y_percent?: number
  qr_code_size_percent?: number
}
