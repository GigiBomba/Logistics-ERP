"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "motion/react"
import {
  MessageCircle,
  Send,
  X,
  Paperclip,
  ChevronDown,
  RotateCcw,
  Bot,
  Minus,
  Maximize2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"
import { supportApi } from "@/api/endpoints"

// ─── Types ───────────────────────────────────────────────────

interface ChatMessage {
  id: string
  role: "user" | "assistant" | "error"
  content: string
  timestamp: string
  failed?: boolean
  escalation?: boolean
  originalContent?: string
}

export interface LiveChatProps {
  /** "floating" renders a trigger button + popover panel. "embedded" renders the panel inline. */
  variant?: "floating" | "embedded"
}

// ─── Helpers ─────────────────────────────────────────────────

function generateId(): string {
  return Math.random().toString(36).slice(2, 9)
}

function getStoredConversationId(): string | null {
  if (typeof window === "undefined") return null
  return sessionStorage.getItem("operion-chat-conversation-id")
}

function setStoredConversationId(id: string | null) {
  if (typeof window === "undefined") return
  if (id) {
    sessionStorage.setItem("operion-chat-conversation-id", id)
  } else {
    sessionStorage.removeItem("operion-chat-conversation-id")
  }
}

function formatTime(dateString: string): string {
  const d = new Date(dateString)
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
}

/** Fallback helper: if the i18n key has not been added yet, show the fallback text. */
function useT() {
  const { t } = useLocale()
  return useCallback(
    (key: string, fallback: string) => {
      const result = t(key)
      return result === key ? fallback : result
    },
    [t]
  )
}

// ─── Sub-components ──────────────────────────────────────────

interface MessageBubbleProps {
  message: ChatMessage
  onRetry?: () => void
}

function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  const t = useT()
  const isUser = message.role === "user"
  const isError = message.role === "error"

  return (
    <div
      className={cn(
        "flex w-full gap-2",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <Avatar className="mt-0.5 h-7 w-7 shrink-0">
          <AvatarFallback className="bg-primary/10 text-primary text-xs font-bold">
            A
          </AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-3.5 py-2.5 text-sm",
          isUser && "bg-primary text-primary-foreground",
          !isUser && !isError && "bg-muted text-foreground",
          isError &&
            "border border-destructive/30 bg-destructive/10 text-destructive"
        )}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        <div
          className={cn(
            "mt-1 flex items-center gap-1.5 text-[11px]",
            isUser ? "text-primary-foreground/70" : "text-muted-foreground"
          )}
        >
          <span>{formatTime(message.timestamp)}</span>
          {isError && onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-0.5 font-medium text-destructive hover:underline"
            >
              <RotateCcw className="h-3 w-3" />
              {t("support.chat.retry", "Retry")}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Main Component ──────────────────────────────────────────

export function LiveChat({ variant = "floating" }: LiveChatProps) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(
    getStoredConversationId
  )
  const [hasUnread, setHasUnread] = useState(false)
  const [userScrolledUp, setUserScrolledUp] = useState(false)
  const [showNewMessagePill, setShowNewMessagePill] = useState(false)
  const [pendingAttachment, setPendingAttachment] = useState<File | null>(null)

  const panelRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const lastMessageCountRef = useRef(0)

  // Initialize welcome message on first open when empty
  useEffect(() => {
    if (messages.length === 0 && !conversationId) {
      setMessages([
        {
          id: generateId(),
          role: "assistant",
          content: t(
            "support.chat.welcome",
            "Hi, I'm ARGO. Ask me anything about Operion, or tell me if something's not working."
          ),
          timestamp: new Date().toISOString(),
        },
      ])
    }
  }, [messages.length, conversationId, t])

  // Auto-scroll logic
  useEffect(() => {
    if (messages.length === 0) return
    if (messages.length > lastMessageCountRef.current) {
      const newMessagesCount = messages.length - lastMessageCountRef.current
      lastMessageCountRef.current = messages.length

      if (!userScrolledUp) {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
      } else {
        // Show new message pill only for assistant messages
        const newMessages = messages.slice(-newMessagesCount)
        if (newMessages.some((m) => m.role === "assistant")) {
          setShowNewMessagePill(true)
        }
      }
    }
  }, [messages, userScrolledUp])

  // Reset unread when opening
  useEffect(() => {
    if (open) {
      setHasUnread(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  // Close on click outside
  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [open])

  const handleScroll = useCallback(() => {
    const container = messagesContainerRef.current
    if (!container) return
    const threshold = 40
    const atBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight <
      threshold
    setUserScrolledUp(!atBottom)
    if (atBottom) {
      setShowNewMessagePill(false)
    }
  }, [])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    setUserScrolledUp(false)
    setShowNewMessagePill(false)
  }, [])

  // Core API call — appends assistant reply (or throws on error)
  const postMessage = useCallback(
    async (content: string) => {
      const { data } = await supportApi.sendMessage({
        conversation_id: conversationId,
        message: content.trim(),
        channel: "chat",
      })

      if (data.conversation_id) {
        setConversationId(data.conversation_id)
        setStoredConversationId(data.conversation_id)
      }

      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: data.reply,
        timestamp: new Date().toISOString(),
        escalation: data.escalated,
      }

      setMessages((prev) => [...prev, assistantMessage])

      if (!open) {
        setHasUnread(true)
      }
    },
    [conversationId, open]
  )

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return

      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "user",
          content: content.trim(),
          timestamp: new Date().toISOString(),
        },
      ])

      setInput("")
      setIsLoading(true)
      setUserScrolledUp(false)

      try {
        await postMessage(content)
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "error",
            content: t(
              "support.chat.error",
              "Something went wrong sending that — try again?"
            ),
            timestamp: new Date().toISOString(),
            failed: true,
            originalContent: content.trim(),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading, postMessage, t]
  )

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault()
      if (!input.trim()) return
      sendMessage(input)
    },
    [input, sendMessage]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit]
  )

  const handleRetry = useCallback(
    async (message: ChatMessage) => {
      if (!message.originalContent) return

      // Remove the error bubble
      setMessages((prev) => prev.filter((m) => m.id !== message.id))
      setIsLoading(true)
      setUserScrolledUp(false)

      try {
        await postMessage(message.originalContent)
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "error",
            content: t(
              "support.chat.error",
              "Something went wrong sending that — try again?"
            ),
            timestamp: new Date().toISOString(),
            failed: true,
            originalContent: message.originalContent,
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [postMessage, t]
  )

  const handleAttachmentClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) {
        setPendingAttachment(file)
        // TODO: wire to attachment API once backend supports file upload on chat messages
      }
      e.target.value = ""
    },
    []
  )

  // Auto-resize textarea
  useEffect(() => {
    const textarea = inputRef.current
    if (!textarea) return
    textarea.style.height = "auto"
    const newHeight = Math.min(textarea.scrollHeight, 120)
    textarea.style.height = `${newHeight}px`
  }, [input])

  const canSend = input.trim().length > 0

  // ─── Shared panel content ──────────────────────────────────

  const panelContent = (
    <>
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">
            {t("support.chat.title", "ARGO Support")}
          </h3>
          <Badge variant="success" className="h-5 px-1.5 text-[10px] font-normal leading-none">
            Online
          </Badge>
        </div>
        <div className="flex items-center gap-1">
          {variant === "embedded" && (
            <button
              onClick={() => setMinimized((p) => !p)}
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              aria-label={minimized ? "Expand" : "Minimize"}
            >
              {minimized ? <Maximize2 className="h-3.5 w-3.5" /> : <Minus className="h-3.5 w-3.5" />}
            </button>
          )}
          {variant === "floating" && (
            <button
              onClick={() => {
                setOpen(false)
                setMinimized(false)
              }}
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              aria-label={t("common.close", "Close")}
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Minimized state for embedded */}
      {variant === "embedded" && minimized ? null : (
        <>
          {/* Messages */}
          <div
            ref={messagesContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
          >
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onRetry={
                  message.failed
                    ? () => handleRetry(message)
                    : undefined
                }
              />
            ))}

            {isLoading && (
              <div className="flex justify-start gap-2">
                <Avatar className="mt-0.5 h-7 w-7 shrink-0">
                  <AvatarFallback className="bg-primary/10 text-primary text-xs font-bold">
                    A
                  </AvatarFallback>
                </Avatar>
                <div className="max-w-[80%] rounded-lg bg-muted px-4 py-3">
                  <LoadingSpinner size="sm" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* New message pill */}
          <AnimatePresence>
            {showNewMessagePill && (
              <motion.button
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                transition={{ duration: 0.15 }}
                onClick={scrollToBottom}
                className="absolute bottom-[72px] left-1/2 -translate-x-1/2 z-10 flex items-center gap-1 rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow-md hover:bg-primary/90"
              >
                <ChevronDown className="h-3 w-3" />
                {t("support.chat.newMessage", "New message")}
              </motion.button>
            )}
          </AnimatePresence>

          {/* Input area */}
          <div className="shrink-0 border-t px-3 py-3">
            {pendingAttachment && (
              <div className="mb-2 flex items-center gap-2 rounded-md bg-muted px-2.5 py-1.5 text-xs text-muted-foreground">
                <Paperclip className="h-3 w-3" />
                <span className="truncate">{pendingAttachment.name}</span>
                <button
                  type="button"
                  onClick={() => setPendingAttachment(null)}
                  className="ml-auto flex h-4 w-4 items-center justify-center rounded-full hover:bg-accent"
                  aria-label={t("common.remove", "Remove")}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
            <form onSubmit={handleSubmit} className="flex items-end gap-2">
              <button
                type="button"
                onClick={handleAttachmentClick}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                aria-label={t("support.chat.attach", "Attach file")}
              >
                <Paperclip className="h-4 w-4" />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileChange}
                accept="image/*,.log,.txt,.pdf,.zip"
              />
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t(
                  "support.chat.placeholder",
                  "Type your message..."
                )}
                rows={1}
                className="min-h-[36px] max-h-[120px] flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm leading-relaxed placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
              <Button
                type="submit"
                size="icon"
                disabled={!canSend || isLoading}
                className="shrink-0"
                aria-label={t("support.chat.send", "Send")}
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </>
      )}
    </>
  )

  // ─── Floating widget mode ──────────────────────────────────

  if (variant === "floating") {
    return (
      <div className="relative">
        {/* Trigger button */}
        <button
          ref={buttonRef}
          onClick={() => setOpen((prev) => !prev)}
          className="relative flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          aria-label={t("support.chat.title", "ARGO Support")}
          aria-expanded={open}
          aria-haspopup="true"
        >
          <MessageCircle className="h-[18px] w-[18px]" />
          {hasUnread && (
            <span className="absolute -right-0.5 -top-0.5 flex h-2.5 w-2.5 items-center justify-center">
              <span className="absolute h-2.5 w-2.5 animate-ping rounded-full bg-primary opacity-75" />
              <span className="relative flex h-2.5 w-2.5 rounded-full bg-primary" />
            </span>
          )}
        </button>

        {/* Panel */}
        <AnimatePresence>
          {open && (
            <>
              {/* Backdrop (mobile visible, desktop invisible click-catcher) */}
              <div
                className="fixed inset-0 z-40 bg-black/50 md:bg-transparent"
                onClick={() => setOpen(false)}
              />

              <motion.div
                ref={panelRef}
                initial={{ opacity: 0, scale: 0.95, y: -4 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: -4 }}
                transition={{ duration: 0.15, ease: "easeOut" }}
                className={cn(
                  "z-50 flex flex-col overflow-hidden border bg-popover shadow-xl",
                  /* Desktop anchored dropdown */
                  "md:absolute md:right-0 md:top-full md:mt-2 md:w-[380px] md:max-h-[560px] md:rounded-xl",
                  /* Mobile full-screen takeover */
                  "fixed inset-0 md:inset-auto rounded-none"
                )}
              >
                {panelContent}
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    )
  }

  // ─── Embedded variant ──────────────────────────────────────

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-xl border bg-popover shadow-sm",
        minimized ? "" : "min-h-[400px]"
      )}
    >
      {panelContent}
    </div>
  )
}
