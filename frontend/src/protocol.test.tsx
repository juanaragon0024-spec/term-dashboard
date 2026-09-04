import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

/** Construye una respuesta SSE con los eventos indicados. */
function sse(eventos: object[]) {
  const texto = eventos.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
  return {
    ok: true,
    body: {
      getReader() {
        let enviado = false
        return {
          read: async () => {
            if (enviado) return { done: true, value: undefined }
            enviado = true
            return { done: false, value: new TextEncoder().encode(texto) }
          },
        }
      },
    },
  }
}

let enviados: any[] = []

beforeEach(() => {
  localStorage.clear()
  enviados = []
})

/** Instala un backend de mentira que responde con los eventos dados. */
function backend(...tandas: object[][]) {
  let turno = 0
  vi.stubGlobal('fetch', vi.fn(async (_url: string, opciones: any) => {
    enviados.push(JSON.parse(opciones.body))
    return sse(tandas[Math.min(turno++, tandas.length - 1)])
  }))
}

async function enviar(texto: string) {
  const entrada = screen.getByRole('textbox')
  await userEvent.type(entrada, `${texto}{Enter}`)
}

describe('protocolo con el backend', () => {
  it('pinta el texto que llega en trozos', async () => {
    backend([{ type: 'chunk', content: 'Hola ' }, { type: 'chunk', content: 'mundo' }])
    render(<App />)
    await enviar('saluda')
    await waitFor(() => expect(screen.getByText(/Hola mundo/)).toBeInTheDocument())
  })

  it('el primer mensaje abre sesión y el segundo la continúa', async () => {
    // Sin esto la web no tenía memoria: cada mensaje empezaba de cero.
    backend(
      [{ type: 'session', sessionId: 'ses-1' }, { type: 'chunk', content: 'uno' }],
      [{ type: 'chunk', content: 'dos' }],
    )
    render(<App />)
    await enviar('primero')
    await waitFor(() => expect(screen.getByText(/uno/)).toBeInTheDocument())
    await enviar('segundo')
    await waitFor(() => expect(enviados).toHaveLength(2))

    expect(enviados[0].resume).toBe(false)
    expect(enviados[1].sessionId).toBe('ses-1')
    expect(enviados[1].resume).toBe(true)
  })

  it('muestra el coste real que informa el backend', async () => {
    backend([
      { type: 'chunk', content: 'ya está' },
      { type: 'usage', tokens: 1234, cost: 0.0567, contextWindow: 1000000 },
    ])
    render(<App />)
    await enviar('haz algo')
    await waitFor(() => expect(screen.getByText(/0\.0567/)).toBeInTheDocument())
  })

  it('usa la ventana de contexto que dice el backend', async () => {
    backend([{ type: 'usage', tokens: 10, cost: 0, contextWindow: 1000000 }])
    render(<App />)
    await enviar('x')
    await waitFor(() =>
      expect(screen.getByText(/1,000,000/)).toBeInTheDocument())
  })

  it('avisa del uso de una herramienta', async () => {
    backend([{ type: 'tool', name: 'Read' }, { type: 'chunk', content: 'listo' }])
    render(<App />)
    await enviar('lee el archivo')
    await waitFor(() => expect(screen.getByText(/Read/)).toBeInTheDocument())
  })

  it('enseña los errores en vez de tragárselos', async () => {
    backend([{ type: 'error', content: 'sin saldo' }])
    render(<App />)
    await enviar('algo')
    await waitFor(() => expect(screen.getByText(/sin saldo/)).toBeInTheDocument())
  })

  it('limpiar el chat olvida también la sesión', async () => {
    // Si no, la IA seguiría recordando lo que el usuario ya no ve.
    backend(
      [{ type: 'session', sessionId: 'ses-1' }, { type: 'chunk', content: 'uno' }],
      [{ type: 'chunk', content: 'dos' }],
    )
    const { container } = render(<App />)
    await enviar('primero')
    await waitFor(() => expect(screen.getByText(/uno/)).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Limpiar' }))
    await enviar('segundo')
    await waitFor(() => expect(enviados).toHaveLength(2))
    expect(enviados[1].sessionId).toBeUndefined()
    expect(enviados[1].resume).toBe(false)
    expect(within(container).queryByText(/uno/)).not.toBeInTheDocument()
  })

  it('cada pestaña lleva su propia sesión', async () => {
    backend(
      [{ type: 'session', sessionId: 'ses-A' }, { type: 'chunk', content: 'a' }],
      [{ type: 'session', sessionId: 'ses-B' }, { type: 'chunk', content: 'b' }],
    )
    const { container } = render(<App />)
    await enviar('en la primera')
    await waitFor(() => expect(screen.getByText(/^a$/)).toBeInTheDocument())

    const barra = container.querySelector('.tab-bar') as HTMLElement
    await userEvent.click(within(barra).getByRole('button', { name: '+' }))
    await enviar('en la segunda')
    await waitFor(() => expect(enviados).toHaveLength(2))
    // La pestaña nueva no hereda la sesión de la anterior.
    expect(enviados[1].sessionId).toBeUndefined()
  })
})
