import { apiFetch } from './apiClient'
import type { Character, Scene } from '../types/dialogue'

export function fetchCharacters(): Promise<Character[]> {
  return apiFetch<Character[]>('/characters/')
}

export function fetchScenes(): Promise<Scene[]> {
  return apiFetch<Scene[]>('/scenes/')
}
