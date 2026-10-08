import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { FillBlankTextAnswer } from './FillBlankTextAnswer'

function ControlledFillBlankAnswer() {
  const [values, setValues] = useState<Record<number, string>>({})

  return (
    <FillBlankTextAnswer
      questionText="According to FATF, the three types are {{1}} and {{2}} PEPs."
      values={values}
      onChange={(blankIndex, value) => setValues((current) => ({ ...current, [blankIndex]: value }))}
    />
  )
}

describe('FillBlankTextAnswer', () => {
  it('accepts complete answers longer than the old 12-character limit in every blank', () => {
    render(<ControlledFillBlankAnswer />)

    const inputs = screen.getAllByPlaceholderText('Your answer...')
    const answers = ['international organization', 'senior management officials']

    inputs.forEach((input, index) => {
      expect(input).not.toHaveAttribute('maxlength')
      fireEvent.change(input, { target: { value: answers[index] } })
      expect(input).toHaveValue(answers[index])
    })
  })
})
