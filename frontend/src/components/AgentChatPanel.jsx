import { useMemo, useRef, useState } from 'react'
import { Bot, Mic, Paperclip, Send, Sparkles, X } from 'lucide-react'
import { sendAgentChatMessage } from '../lib/agentChatLLM'

const STARTERS = [
  'What is the biggest issue in this campaign?',
  'What should I optimize first?',
]

function formatMeta(meta) {
  if (!meta) return ''
  if (meta === 'local-fallback') return 'fallback'
  return meta
}

export default function AgentChatPanel({ context }) {
  const fileInputRef = useRef(null)
  const recognitionRef = useRef(null)
  const [attachments, setAttachments] = useState([])
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "I'm your Reflection Agent. Ask about campaign performance, patterns, insights, memory, or next actions.",
      meta: 'ready',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)

  const starterButtons = useMemo(() => STARTERS.slice(0, 2), [])

  function handleAttach(event) {
    const files = Array.from(event.target.files || [])
    if (!files.length) return
    setAttachments(current => [...current, ...files].slice(0, 4))
    event.target.value = ''
  }

  function removeAttachment(name) {
    setAttachments(current => current.filter(file => file.name !== name))
  }

  function toggleMic() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return

    if (listening && recognitionRef.current) {
      recognitionRef.current.stop()
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    recognition.onstart = () => setListening(true)
    recognition.onend = () => setListening(false)
    recognition.onerror = () => setListening(false)
    recognition.onresult = event => {
      const transcript = event.results?.[0]?.[0]?.transcript || ''
      setInput(current => [current, transcript].filter(Boolean).join(current ? ' ' : ''))
    }
    recognitionRef.current = recognition
    recognition.start()
  }

  async function submitMessage(raw) {
    const text = raw.trim()
    if ((!text && !attachments.length) || loading) return

    const attachmentLabel = attachments.length
      ? `
Attached: ${attachments.map(file => file.name).join(', ')}`
      : ''
    const outgoing = `${text}${attachmentLabel}`.trim()

    setMessages(current => [...current, { role: 'user', content: outgoing }])
    setInput('')
    setLoading(true)

    try {
      const { reply, model } = await sendAgentChatMessage(outgoing, context)
      setMessages(current => [...current, { role: 'assistant', content: reply, meta: model }])
      setAttachments([])
    } catch {
      setMessages(current => [...current, { role: 'assistant', content: 'Chat is unavailable right now. Try again in a moment.', meta: 'error' }])
    } finally {
      setLoading(false)
      setListening(false)
    }
  }

  return (
    <div className="workspace-chat-panel premium-chat-panel">
      <div className="workspace-chat-scroll">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={message.role === 'assistant' ? 'workspace-chat-bubble workspace-chat-bubble-ai premium-chat-bubble' : 'workspace-chat-bubble workspace-chat-bubble-user premium-chat-bubble premium-chat-bubble-user'}
          >
            <div className="workspace-chat-bubble-header">
              <span className="workspace-chat-role">
                {message.role === 'assistant' ? <Bot size={13} /> : <Sparkles size={13} />}
                {message.role === 'assistant' ? 'Reflection Agent' : 'You'}
              </span>
              {message.meta && <span className={message.meta === 'ready' ? 'workspace-chat-meta workspace-chat-meta-muted' : 'workspace-chat-meta'}>{formatMeta(message.meta)}</span>}
            </div>
            <div>{message.content}</div>
          </div>
        ))}

        {loading && (
          <div className="workspace-chat-bubble workspace-chat-bubble-ai premium-chat-bubble">
            <div className="workspace-chat-bubble-header">
              <span className="workspace-chat-role"><Bot size={13} />Reflection Agent</span>
              <span className="workspace-chat-meta">thinking</span>
            </div>
            <div>Working through the current campaign context...</div>
          </div>
        )}
      </div>

      <div className="workspace-chat-starters">
        {starterButtons.map(item => (
          <button key={item} type="button" className="workspace-chat-starter" onClick={() => submitMessage(item)}>
            {item}
          </button>
        ))}
      </div>

      {attachments.length > 0 && (
        <div className="workspace-chat-attachments">
          {attachments.map(file => (
            <span key={file.name} className="workspace-chat-attachment">
              <Paperclip size={12} />
              {file.name}
              <button type="button" className="workspace-chat-attachment-remove" onClick={() => removeAttachment(file.name)}>
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}

      <form
        className="workspace-chat-composer"
        onSubmit={event => {
          event.preventDefault()
          submitMessage(input)
        }}
      >
        <div className="workspace-chat-composer-shell">
          <textarea
            className="workspace-chat-input"
            rows={4}
            value={input}
            onChange={event => setInput(event.target.value)}
            placeholder="Ask about insights, patterns, performance, or next actions..."
          />
          <div className="workspace-chat-composer-actions">
            <input ref={fileInputRef} type="file" multiple hidden onChange={handleAttach} />
            <button type="button" className="workspace-chat-icon-button" onClick={() => fileInputRef.current?.click()}>
              <Paperclip size={15} />
            </button>
            <button type="button" className={listening ? 'workspace-chat-icon-button workspace-chat-icon-button-active' : 'workspace-chat-icon-button'} onClick={toggleMic}>
              <Mic size={15} />
            </button>
            <button type="submit" className="workspace-chat-send" disabled={loading || (!input.trim() && !attachments.length)}>
              <Send size={14} />
              Send
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
