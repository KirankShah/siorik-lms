import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'

// RTL's automatic afterEach-cleanup only self-registers when it detects a
// global `afterEach` (i.e. vitest's `globals: true`) — since this project
// deliberately imports test globals explicitly instead, register it here.
afterEach(() => {
  cleanup()
})
