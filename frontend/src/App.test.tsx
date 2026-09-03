import { render, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

// El chat habla con el backend; aquí solo se prueba la barra de pestañas.
beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('sin backend'))))
})

/**
 * La barra lateral tiene su propio botón "Chat", así que todas las consultas
 * se acotan a la barra de pestañas para no confundir uno con otra.
 */
function barra(container: HTMLElement): HTMLElement {
  const bar = container.querySelector('.tab-bar')
  if (!bar) throw new Error('no se encontró la barra de pestañas')
  return bar as HTMLElement
}

function pintar() {
  const { container } = render(<App />)
  return barra(container)
}

describe('renombrar pestañas', () => {
  it('el doble clic abre un campo con el nombre actual', async () => {
    // renameTab existía pero no la llamaba nadie: no había forma de renombrar.
    const bar = pintar()
    await userEvent.dblClick(within(bar).getByText('Chat'))
    expect(within(bar).getByDisplayValue('Chat')).toBeInTheDocument()
  })

  it('Enter guarda el nombre nuevo', async () => {
    const bar = pintar()
    await userEvent.dblClick(within(bar).getByText('Chat'))
    const campo = within(bar).getByDisplayValue('Chat')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Refactor{Enter}')

    expect(within(bar).getByText('Refactor')).toBeInTheDocument()
    expect(within(bar).queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('Escape descarta lo escrito', async () => {
    const bar = pintar()
    await userEvent.dblClick(within(bar).getByText('Chat'))
    const campo = within(bar).getByDisplayValue('Chat')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Descartado{Escape}')

    expect(within(bar).getByText('Chat')).toBeInTheDocument()
    expect(within(bar).queryByText('Descartado')).not.toBeInTheDocument()
  })

  it('perder el foco guarda', async () => {
    const bar = pintar()
    await userEvent.dblClick(within(bar).getByText('Chat'))
    const campo = within(bar).getByDisplayValue('Chat')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Por foco')
    await userEvent.tab()

    expect(within(bar).getByText('Por foco')).toBeInTheDocument()
  })

  it('un nombre en blanco no deja la pestaña sin etiqueta', async () => {
    const bar = pintar()
    await userEvent.dblClick(within(bar).getByText('Chat'))
    const campo = within(bar).getByDisplayValue('Chat')
    await userEvent.clear(campo)
    await userEvent.type(campo, '   {Enter}')

    expect(within(bar).getByText('Chat')).toBeInTheDocument()
  })

  it('mientras se renombra no se ofrece cerrar la pestaña', async () => {
    const bar = pintar()
    await userEvent.click(within(bar).getByRole('button', { name: '+' }))
    expect(within(bar).getAllByRole('button', { name: 'x' })).toHaveLength(2)

    await userEvent.dblClick(within(bar).getByText('Chat'))
    // La cruz junto al campo invitaría a cerrar la pestaña justo cuando lo que
    // se quiere es aceptar el nombre.
    expect(within(bar).getAllByRole('button', { name: 'x' })).toHaveLength(1)
  })

  it('renombra la pestaña correcta cuando hay varias', async () => {
    const bar = pintar()
    await userEvent.click(within(bar).getByRole('button', { name: '+' }))
    expect(within(bar).getByText('Chat 2')).toBeInTheDocument()

    await userEvent.dblClick(within(bar).getByText('Chat'))
    const campo = within(bar).getByDisplayValue('Chat')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Primera{Enter}')

    expect(within(bar).getByText('Primera')).toBeInTheDocument()
    expect(within(bar).getByText('Chat 2')).toBeInTheDocument()
  })

  it('renombrar no cambia de pestaña activa', async () => {
    const bar = pintar()
    await userEvent.click(within(bar).getByRole('button', { name: '+' }))
    const activaAntes = bar.querySelector('.tab.active')?.textContent

    await userEvent.dblClick(within(bar).getByText('Chat 2'))
    const campo = within(bar).getByDisplayValue('Chat 2')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Renombrada{Enter}')

    expect(activaAntes).toContain('Chat 2')
    expect(bar.querySelector('.tab.active')?.textContent).toContain('Renombrada')
  })
})

describe('barra de pestañas', () => {
  it('con una sola pestaña no se puede cerrar', () => {
    const bar = pintar()
    expect(within(bar).queryByRole('button', { name: 'x' })).not.toBeInTheDocument()
  })

  it('el botón + añade pestañas', async () => {
    const bar = pintar()
    await userEvent.click(within(bar).getByRole('button', { name: '+' }))
    expect(within(bar).getByText('Chat 2')).toBeInTheDocument()
  })
})
