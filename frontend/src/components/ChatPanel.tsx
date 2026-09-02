import { useRef, useEffect, useState } from 'react'
import type { ChatTabData } from '../App'
import type { ThemeKey } from '../themes'
import { MessageBubble } from './MessageBubble'
import { themes } from '../themes'

const LOGO = `████████╗ ███████╗ ██████╗  ███╗   ███╗
╚══██╔══╝ ██╔════╝ ██╔══██╗ ████╗ ████║
   ██║    █████╗   ██████╔╝ ██╔████╔██║
   ██║    ██╔══╝   ██╔══██╗ ██║╚██╔╝██║
   ██║    ███████╗ ██║  ██║ ██║ ╚═╝ ██║
   ╚═╝    ╚══════╝ ╚═╝  ╚═╝ ╚═╝     ╚═╝`

interface ChatPanelProps {
  tab: ChatTabData
  onSend: (text: string) => void
  onStop: () => void
  onClear: () => void
  theme: ThemeKey
}

export function ChatPanel({ tab, onSend, onStop, onClear, theme }: ChatPanelProps) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [tab.messages])

  const handleSubmit = () => {
    const text = input.trim()
    if (!text || tab.isLoading) return
    setInput('')
    onSend(text)
    if (inputRef.current) inputRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  const gradient = themes[theme].gradient
  const gradientCSS = `linear-gradient(90deg, ${gradient[0]} 0%, ${gradient[Math.floor(gradient.length / 2)]} 50%, ${gradient[gradient.length - 1]} 100%)`

  return (
    <main className="chat-panel">
      <div className="messages-container">
        {tab.messages.length === 0 && (
          <div className="empty-state">
            <div className="ascii-logo">
              <pre style={{
                background: gradientCSS,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>{LOGO}</pre>
            </div>
            <div className="empty-state-sub">
              Escribe un mensaje o /help para ver comandos.
            </div>
          </div>
        )}
        {tab.messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {tab.isLoading && (
          <div className="loading-dots">
            <span /><span /><span />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={`Mensaje a ${tab.modelName}...`}
            rows={1}
            spellCheck={false}
          />
          {tab.isLoading ? (
            <button className="send-btn stop" onClick={onStop}>Detener</button>
          ) : (
            <button className="send-btn" onClick={handleSubmit} disabled={!input.trim()}>Enviar</button>
          )}
        </div>
      </div>
    </main>
  )
}
