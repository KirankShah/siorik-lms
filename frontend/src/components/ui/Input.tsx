import type { InputHTMLAttributes } from 'react'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export function Input({ label, error, id, className = '', ...props }: InputProps) {
  return (
    <div>
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-neutral-700">
          {label}
        </label>
      )}
      <input
        id={id}
        className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm transition focus:outline-none focus:ring-1 ${label ? 'mt-1' : ''} ${
          error
            ? 'border-red-400 focus:border-red-500 focus:ring-red-500'
            : 'border-neutral-300 focus:border-brand-navy focus:ring-brand-navy'
        } ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}
