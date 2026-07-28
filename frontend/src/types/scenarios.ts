// is_recommended is answer-key data and is stripped from the API response
// for learners — see backend scenarios.serializers.ScenarioChoiceSerializer.
export interface ScenarioChoice {
  id: number
  node: number
  choice_text: string
  // Null means picking this choice ends the scenario.
  next_node: number | null
  feedback_text: string
  is_recommended?: boolean
  order: number
}

export interface ScenarioNode {
  id: number
  slide: number
  node_key: string
  prompt: string
  prompt_image: string | null
  is_start: boolean
  choices: ScenarioChoice[]
}

export interface ScenarioAttempt {
  id: number
  enrollment: number
  slide: number
  path_taken: number[]
  reached_recommended_ending: boolean
  completed_at: string
}
