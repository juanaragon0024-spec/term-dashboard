import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ChatTabData } from '../App'
import { ChatPanel } from './ChatPanel'

function tab(overrides: Partial<ChatTabData> = {}): ChatTabData {
  return {
    id: 'tab-1',
    name: 'Chat',
    model: 'claude',
    modelName: 'Claude',
    messages: [],
    isLoading: false,
    ...overrides,
  }
}

const conMensajes = [
  { id: 'm1', role: 'user' as const, content: 'hola' },
  { id: 'm2', role: 'assistant' as const, content: 'qué tal' },
]

describe('botón de limpiar', () => {
  it('no aparece cuando la conversación está vacía', () => {
    render(<ChatPanel tab={tab()} onSend={vi.fn()} onStop={vi.fn()} onClear={vi.fn()} theme="neon" />)
    expect(screen.queryByRole('button', { name: 'Limpiar' })).not.toBeInTheDocument()
  })

  it('aparece en cuanto hay mensajes', () => {
    render(
      <ChatPanel tab={tab({ messages: conMensajes })} onSend={vi.fn()} onStop={vi.fn()}
        onClear={vi.fn()} theme="neon" />,
    )
    expect(screen.getByRole('button', { name: 'Limpiar' })).toBeInTheDocument()
  })

  it('avisa al pulsarlo', async () => {
    // Este era el prop que se pasaba y nadie usaba: el botón no existía.
    const onClear = vi.fn()
    render(
      <ChatPanel tab={tab({ messages: conMensajes })} onSend={vi.fn()} onStop={vi.fn()}
        onClear={onClear} theme="neon" />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Limpiar' }))
    expect(onClear).toHaveBeenCalledOnce()
  })

  it('muestra el modelo de la pestaña en la cabecera', () => {
    render(
      <ChatPanel tab={tab({ messages: conMensajes, modelName: 'Claude Opus' })}
        onSend={vi.fn()} onStop={vi.fn()} onClear={vi.fn()} theme="neon" />,
    )
    expect(screen.getByText('Claude Opus')).toBeInTheDocument()
  })
})

describe('envío', () => {
  it('Enter envía y Shift+Enter no', async () => {
    const onSend = vi.fn()
    render(<ChatPanel tab={tab()} onSend={onSend} onStop={vi.fn()} onClear={vi.fn()} theme="neon" />)
    const entrada = screen.getByRole('textbox')

    await userEvent.type(entrada, 'primero{Enter}')
    expect(onSend).toHaveBeenCalledWith('primero')

    onSend.mockClear()
    await userEvent.type(entrada, 'segundo{Shift>}{Enter}{/Shift}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('no envía mensajes vacíos', async () => {
    const onSend = vi.fn()
    render(<ChatPanel tab={tab()} onSend={onSend} onStop={vi.fn()} onClear={vi.fn()} theme="neon" />)
    await userEvent.type(screen.getByRole('textbox'), '   {Enter}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('mientras responde ofrece Detener en lugar de Enviar', () => {
    render(
      <ChatPanel tab={tab({ isLoading: true })} onSend={vi.fn()} onStop={vi.fn()}
        onClear={vi.fn()} theme="neon" />,
    )
    expect(screen.getByRole('button', { name: 'Detener' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Enviar' })).not.toBeInTheDocument()
  })
})
