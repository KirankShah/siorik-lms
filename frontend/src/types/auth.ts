export type Role = 'LEARNER' | 'INSTRUCTOR' | 'ORG_ADMIN' | 'PLATFORM_ADMIN'
export type NarrationLanguage = 'en' | 'ne'

export interface Organization {
  id: number
  name: string
  slug: string
  logo: string | null
  is_active: boolean
}

export interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  role: Role
  organization: Organization | null
  phone_number: string | null
  designation: string | null
  is_active: boolean
  is_demo: boolean
  must_reset_password: boolean
  preferred_narration_language: NarrationLanguage
}

export interface AuthTokens {
  access: string
  refresh: string
}
