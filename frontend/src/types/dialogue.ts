// Mirrors backend dialogue.serializers 1:1. Platform-wide, seeded once via
// the Django admin — see backend dialogue.models docstrings — never
// created/edited from this frontend.
export type CharacterRole = 'CUSTOMER' | 'TELLER' | 'COMPLIANCE_OFFICER' | 'BRANCH_MANAGER' | 'OTHER'

export interface Character {
  id: number
  name: string
  role: CharacterRole
  avatar_image: string
}

export type SceneType = 'FRONT_OFFICE' | 'BACK_OFFICE'

export interface Scene {
  id: number
  name: string
  scene_type: SceneType
  background_image: string
}
