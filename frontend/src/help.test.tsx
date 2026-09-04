import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { COMMAND_GROUPS } from './commands.generated'
import { HelpPanel } from './components/HelpPanel'

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('sin backend'))))
})

describe('panel de ayuda', () => {
  it('lista todos los comandos, no unos pocos escritos a mano', () => {
    // Tenía catorce a mano mientras la terminal llegaba a ochenta y tres.
    const total = COMMAND_GROUPS.reduce((n, g) => n + g.commands.length, 0)
    expect(total).toBeGreaterThan(70)

    render(<HelpPanel />)
    for (const grupo of COMMAND_GROUPS) {
      expect(screen.getByText(grupo.title)).toBeInTheDocument()
    }
  })

  it('marca los que solo funcionan en la terminal', () => {
    render(<HelpPanel />)
    // /git es de terminal; /clear funciona aquí.
    expect(screen.getAllByText('term').length).toBeGreaterThan(0)
  })

  it('se pueden filtrar los que sí funcionan aquí', async () => {
    render(<HelpPanel />)
    expect(screen.getByText('/git')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Solo en el navegador' }))
    expect(screen.queryByText('/git')).not.toBeInTheDocument()
    expect(screen.getByText('/clear')).toBeInTheDocument()
  })

  it('el buscador filtra por nombre y por descripción', async () => {
    render(<HelpPanel />)
    await userEvent.type(screen.getByPlaceholderText('Filtrar comandos…'), 'commit')
    expect(screen.getByText('/commit [mensaje]')).toBeInTheDocument()
    expect(screen.queryByText('/clear')).not.toBeInTheDocument()
  })

  it('avisa cuando no hay coincidencias', async () => {
    render(<HelpPanel />)
    await userEvent.type(screen.getByPlaceholderText('Filtrar comandos…'), 'zzzzz')
    expect(screen.getByText(/Ningún comando coincide/)).toBeInTheDocument()
  })
})

describe('comandos en el chat', () => {
  async function escribir(texto: string) {
    await userEvent.type(screen.getByRole('textbox'), `${texto}{Enter}`)
  }

  it('«/» no se manda a la IA', async () => {
    render(<App />)
    await escribir('/clear')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('/help abre el panel de ayuda', async () => {
    render(<App />)
    await escribir('/help')
    expect(screen.getByPlaceholderText('Filtrar comandos…')).toBeInTheDocument()
  })

  it('/theme cambia el tema', async () => {
    render(<App />)
    await escribir('/theme dracula')
    expect(localStorage.getItem('term-theme')).toBe('dracula')
  })

  it('/theme con un tema inventado avisa y no lo cambia', async () => {
    render(<App />)
    await escribir('/theme inventado')
    expect(screen.getByText(/Temas:/)).toBeInTheDocument()
    expect(localStorage.getItem('term-theme')).not.toBe('inventado')
  })

  it('/new abre otra pestaña', async () => {
    const { container } = render(<App />)
    await escribir('/new Pruebas')
    const barra = container.querySelector('.tab-bar') as HTMLElement
    expect(within(barra).getByText('Pruebas')).toBeInTheDocument()
  })

  it('/name renombra la pestaña activa', async () => {
    const { container } = render(<App />)
    await escribir('/name Refactor')
    const barra = container.querySelector('.tab-bar') as HTMLElement
    expect(within(barra).getByText('Refactor')).toBeInTheDocument()
  })

  it('un comando de terminal lo dice en vez de mandarlo a la IA', async () => {
    render(<App />)
    await escribir('/git')
    expect(screen.getByText(/solo funciona en la terminal/)).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('un comando inventado no llega a la IA', async () => {
    render(<App />)
    await escribir('/noexiste')
    expect(screen.getByText(/Comando desconocido/)).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('un mensaje normal sí llega a la IA', async () => {
    render(<App />)
    await escribir('hola qué tal')
    expect(fetch).toHaveBeenCalled()
  })
})
