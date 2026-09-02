import { useState, useEffect, useCallback, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { codeToHtml } from 'shiki'
import type { Message } from '../App'

interface MessageBubbleProps {
  message: Message
}

// Cache for highlighted code blocks
const highlightCache = new Map<string, string>()

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [html, setHtml] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const cacheKey = `${language}:${code}`
    if (highlightCache.has(cacheKey)) {
      setHtml(highlightCache.get(cacheKey)!)
      return
    }

    codeToHtml(code, {
      lang: language || 'text',
      theme: 'vitesse-dark',
    })
      .then((result) => {
        highlightCache.set(cacheKey, result)
        setHtml(result)
      })
      .catch(() => {
        // Fallback if language not supported
        codeToHtml(code, { lang: 'text', theme: 'vitesse-dark' })
          .then((result) => {
            highlightCache.set(cacheKey, result)
            setHtml(result)
          })
      })
  }, [code, language])

  const copyCode = useCallback(() => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [code])

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-block-lang">{language || 'text'}</span>
        <button
          className={`code-copy-btn ${copied ? 'copied' : ''}`}
          onClick={copyCode}
        >
          {copied ? 'Copiado' : 'Copiar'}
        </button>
      </div>
      {html ? (
        <div dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <pre style={{ padding: '16px', background: '#0d1117', margin: 0 }}>
          <code>{code}</code>
        </pre>
      )}
    </div>
  )
}

export const MessageBubble = memo(function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="message user">
        {message.content}
      </div>
    )
  }

  return (
    <div className="message assistant">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const codeString = String(children).replace(/\n$/, '')

            // Block code (has language class or is multiline)
            if (match || (codeString.includes('\n') && !className)) {
              return (
                <CodeBlock
                  code={codeString}
                  language={match ? match[1] : 'text'}
                />
              )
            }

            // Inline code
            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
          // Override pre to avoid double wrapping
          pre({ children }) {
            return <>{children}</>
          },
        }}
      >
        {message.content}
      </ReactMarkdown>
    </div>
  )
})
