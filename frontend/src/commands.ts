/**
 * Ejecución de los comandos que empiezan por «/».
 *
 * Hasta ahora la web los listaba en la ayuda pero no los ejecutaba: escribir
 * /clear se lo mandaba a la IA como si fuera una frase.
 *
 * El catálogo se genera desde el de la terminal (scripts/gen_commands.py), así
 * que aquí solo está lo que el navegador sabe hacer de verdad.
 */

import { COMMAND_GROUPS, WEB_COMMANDS } from './commands.generated'
import { themes, type ThemeKey } from './themes'

export type PanelKey = 'chat' | 'settings' | 'apps' | 'tools' | 'help'

export const EFFORT_LEVELS = ['low', 'medium', 'high', 'max'] as const
export type Effort = (typeof EFFORT_LEVELS)[number]

export const MODELS: Record<string, string> = {
  claude: 'Claude',
  'claude-opus': 'Claude Opus',
  'claude-haiku': 'Claude Haiku',
}

/** Lo que un comando puede pedirle a la aplicación. */
export interface CommandContext {
  addTab: (name?: string, model?: string) => void
  closeTab: () => void
  clearTab: () => void
  renameTab: (name: string) => void
  setPanel: (panel: PanelKey) => void
  setTheme: (theme: ThemeKey) => void
  setEffort: (effort: Effort) => void
  setModel: (model: string) => void
  setWorkdir: (path: string) => void
  copyLast: () => Promise<boolean>
  exportChat: () => void
  search: (text: string) => number
  notify: (text: string) => void
  state: {
    theme: ThemeKey
    effort: Effort
    model: string
    workdir: string
    messages: number
  }
}

export interface CommandOutcome {
  /** Si era un comando; false significa «esto va a la IA». */
  handled: boolean
  /** Texto para enseñar en el chat como respuesta del propio Term. */
  reply?: string
}

/** Sugerencias mientras se escribe, para el desplegable del chat. */
export function suggest(text: string): { cmd: string; desc: string }[] {
  const escrito = text.trim().toLowerCase()
  if (!escrito.startsWith('/')) return []
  const cabeza = escrito.split(/\s+/)[0]
  return COMMAND_GROUPS.flatMap((g) => g.commands)
    .filter((c) => c.web && (escrito === '/' || c.cmd.split(' ')[0].startsWith(cabeza)))
    .slice(0, 8)
    .map((c) => ({ cmd: c.cmd, desc: c.desc }))
}

/** Completa un comando a medio escribir hasta su prefijo común. */
export function complete(text: string): string {
  const escrito = text.trim()
  if (!escrito.startsWith('/')) return text
  const candidatos = WEB_COMMANDS.filter((c) => c.startsWith(escrito))
  if (candidatos.length === 0) return text
  if (candidatos.length === 1) return `${candidatos[0]} `
  let comun = candidatos[0]
  for (const c of candidatos.slice(1)) {
    while (!c.startsWith(comun)) comun = comun.slice(0, -1)
  }
  return comun
}

const listaDeComandos = () =>
  COMMAND_GROUPS.map((g) => {
    const propios = g.commands.filter((c) => c.web)
    if (propios.length === 0) return ''
    const filas = propios.map((c) => `  \`${c.cmd}\` — ${c.desc}`).join('\n')
    return `**${g.title}**\n${filas}`
  })
    .filter(Boolean)
    .join('\n\n')

/**
 * Ejecuta un comando. Devuelve `handled: false` si no lo es, para que el texto
 * siga su camino hacia la IA.
 */
export function runCommand(entrada: string, ctx: CommandContext): CommandOutcome {
  const texto = entrada.trim()
  if (!texto.startsWith('/')) return { handled: false }

  const [cabeza, ...resto] = texto.split(/\s+/)
  const cmd = cabeza.toLowerCase()
  const arg = resto.join(' ').trim()

  switch (cmd) {
    case '/':
      return { handled: true, reply: listaDeComandos() }

    // -- conversación
    case '/new':
      ctx.addTab(arg || undefined)
      return { handled: true }
    case '/close':
      ctx.closeTab()
      return { handled: true }
    case '/clear':
      ctx.clearTab()
      return { handled: true }
    case '/name':
      if (!arg) return { handled: true, reply: 'Uso: `/name <texto>`' }
      ctx.renameTab(arg)
      return { handled: true }
    case '/search': {
      if (!arg) return { handled: true, reply: 'Uso: `/search <texto>`' }
      const n = ctx.search(arg)
      return {
        handled: true,
        reply: n
          ? `${n} ${n === 1 ? 'coincidencia' : 'coincidencias'} de «${arg}»`
          : `Sin coincidencias de «${arg}»`,
      }
    }
    case '/export':
      ctx.exportChat()
      return { handled: true, reply: 'Conversación descargada.' }
    case '/copy':
      void ctx.copyLast().then((ok) =>
        ctx.notify(ok ? 'Copiado al portapapeles' : 'No hay respuesta que copiar'),
      )
      return { handled: true }

    // -- configuración
    case '/model':
      if (!arg) {
        return { handled: true, reply: `Modelos: ${Object.keys(MODELS).join(', ')}` }
      }
      if (!(arg in MODELS)) {
        return { handled: true, reply: `Modelo desconocido: \`${arg}\`` }
      }
      ctx.setModel(arg)
      return { handled: true }
    case '/effort':
      if (!EFFORT_LEVELS.includes(arg as Effort)) {
        return { handled: true, reply: `Niveles: ${EFFORT_LEVELS.join(', ')}` }
      }
      ctx.setEffort(arg as Effort)
      return { handled: true }
    case '/theme':
      if (!(arg in themes)) {
        return { handled: true, reply: `Temas: ${Object.keys(themes).join(', ')}` }
      }
      ctx.setTheme(arg as ThemeKey)
      return { handled: true }
    case '/workdir':
      if (!arg) return { handled: true, reply: `Directorio: \`${ctx.state.workdir || '~'}\`` }
      ctx.setWorkdir(arg)
      return { handled: true }
    case '/save':
      return { handled: true, reply: 'Los ajustes se guardan solos en este navegador.' }

    // -- paneles
    case '/help':
    case '/settings':
    case '/apps':
    case '/tools':
      ctx.setPanel(cmd.slice(1) as PanelKey)
      return { handled: true }
    case '/files':
    case '/map':
      ctx.setPanel('apps')
      return { handled: true }

    // -- información
    case '/tab':
      return {
        handled: true,
        reply:
          `Modelo: **${MODELS[ctx.state.model] ?? ctx.state.model}** · ` +
          `Esfuerzo: **${ctx.state.effort}** · Tema: **${themes[ctx.state.theme].name}** · ` +
          `${ctx.state.messages} mensajes`,
      }
    case '/about':
    case '/version':
      return {
        handled: true,
        reply:
          'Term en el navegador. La versión de terminal (`term`) trae además ' +
          'git, procesos en segundo plano, MCP y control del sistema.',
      }

    default: {
      // Existe en la terminal pero aquí no: mejor decirlo que mandarlo a la IA.
      const enTerminal = COMMAND_GROUPS.flatMap((g) => g.commands).find(
        (c) => c.cmd.split(' ')[0] === cmd,
      )
      if (enTerminal) {
        return {
          handled: true,
          reply: `\`${cmd}\` solo funciona en la terminal, con \`term\`.`,
        }
      }
      return { handled: true, reply: `Comando desconocido: \`${cmd}\`. Prueba \`/help\`.` }
    }
  }
}
