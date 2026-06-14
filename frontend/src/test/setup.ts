import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Unmount React trees and reset mocks/storage between tests for isolation.
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  localStorage.clear()
})
