"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "motion/react"
import {
  MessageCircle,
  Send,
  X,
  ChevronDown,
  RotateCcw,
  Loader2,
  Ticket,
  CheckCircle2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"
import { supportApi } from "@/api/endpoints"
import { useCreateTicket } from "@/services/queries"
import type { CreateTicketRequest } from "@/api/endpoints"

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

interface SupportModalProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
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

// ─── Chat Sub-components ─────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-3 py-2.5">
      <span
        className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
        style={{ animationDelay: "0ms" }}
      />
      <span
        className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
        style={{ animationDelay: "120ms" }}
      />
      <span
        className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
        style={{ animationDelay: "240ms" }}
      />
    </div>
  )
}

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
        "flex w-full",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3.5 py-2.5 text-sm",
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

// ─── Ticket Form ─────────────────────────────────────────────

function TicketForm({ onSuccess }: { onSuccess: () => void }) {
  const t = useT()
  const [subject, setSubject] = useState("")
  const [description, setDescription] = useState("")

  const createTicket = useCreateTicket()

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!subject.trim() || !description.trim()) return

      try {
        await createTicket.mutateAsync({
          subject: subject.trim(),
          description: description.trim(),
        } as CreateTicketRequest)
        onSuccess()
      } catch {
        // Error state is handled by the mutation
      }
    },
    [subject, description, createTicket, onSuccess]
  )

  const isSubmitting = createTicket.isPending
  const canSubmit = subject.trim().length > 0 && description.trim().length > 0 && !isSubmitting

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-4">
      <div className="space-y-1.5">
        <label
          htmlFor="support-ticket-subject"
          className="text-sm font-medium text-foreground"
        >
          {t("support.bugTitle", "Subject")}
        </label>
        <input
          id="support-ticket-subject"
          type="text"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder={t("support.bugTitlePlaceholder", "Brief summary of the issue...")}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground/60 focus-visible:ring-1 focus-visible:ring-ring"
          autoComplete="off"
          disabled={isSubmitting}
        />
      </div>

      <div className="space-y-1.5 flex-1">
        <label
          htmlFor="support-ticket-desc"
          className="text-sm font-medium text-foreground"
        >
          {t("support.bugDesc", "Description")}
        </label>
        <textarea
          id="support-ticket-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("support.bugDescPlaceholder", "Describe the issue in detail...")}
          className="min-h-[120px] w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground/60 focus-visible:ring-1 focus-visible:ring-ring"
          disabled={isSubmitting}
        />
      </div>

      <Button
        type="submit"
        disabled={!canSubmit}
        className="w-full"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            {t("support.submitting", "Submitting...")}
          </>
        ) : (
          t("common.submit", "Submit")
        )}
      </Button>

      {createTicket.isError && (
        <p className="text-center text-sm text-destructive">
          {t("support.chat.error", "Something went wrong. Please try again.")}
        </p>
      )}
    </form>
  )
}

// ─── Success State ──────────────────────────────────────────

function TicketSuccess({ onSubmitAnother }: { onSubmitAnother: () => void }) {
  const t = useT()

  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <CheckCircle2 className="mb-4 h-12 w-12 text-emerald-500" />
      <h3 className="text-lg font-semibold">
        {t("support.ticketSubmitted", "Ticket submitted")}
      </h3>
      <p className="mt-1.5 text-sm text-muted-foreground max-w-sm">
        {t(
          "support.ticketSubmittedDesc",
          "Our support team will review your ticket and get back to you as soon as possible."
        )}
      </p>
      <Button
        variant="outline"
        onClick={onSubmitAnother}
        className="mt-6"
      >
        {t("support.submitAnother", "Submit another")}
      </Button>
    </div>
  )
}

// ─── Tab Bar ────────────────────────────────────────────────

type Tab = "chat" | "ticket"

// ─── Main Component ─────────────────────────────────────────

export function SupportModal({ open: controlledOpen, onOpenChange }: SupportModalProps) {
  const t = useT()
  const [internalOpen, setInternalOpen] = useState(false)
  const open = controlledOpen ?? internalOpen
  const setOpen = (val: boolean | ((prev: boolean) => boolean)) => {
    const next = typeof val === "function" ? val(open) : val
    if (onOpenChange) onOpenChange(next)
    else setInternalOpen(next)
  }

  const [activeTab, setActiveTab] = useState<Tab>("chat")

  // ── Chat state ────────────────────────────────────────────

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(
    getStoredConversationId
  )
  const [userScrolledUp, setUserScrolledUp] = useState(false)
  const [showNewMessagePill, setShowNewMessagePill] = useState(false)

  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const lastMessageCountRef = useRef(0)

  // ── Ticket state ──────────────────────────────────────────

  const [ticketSubmitted, setTicketSubmitted] = useState(false)

  // ── Initialize welcome message ────────────────────────────

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

  // ── Auto-scroll logic ─────────────────────────────────────

  useEffect(() => {
    if (messages.length === 0) return
    if (messages.length > lastMessageCountRef.current) {
      const newMessagesCount = messages.length - lastMessageCountRef.current
      lastMessageCountRef.current = messages.length

      if (!userScrolledUp) {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
      } else {
        const newMessages = messages.slice(-newMessagesCount)
        if (newMessages.some((m) => m.role === "assistant")) {
          setShowNewMessagePill(true)
        }
      }
    }
  }, [messages, userScrolledUp])

  // ── Focus input when opening chat tab ─────────────────────

  useEffect(() => {
    if (open && activeTab === "chat") {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open, activeTab])

  // ── Reset ticket state when switching tabs ────────────────

  useEffect(() => {
    if (activeTab !== "ticket") {
      // Don't reset submitted state on tab switch — user can see success
    }
  }, [activeTab])

  // ── Body scroll lock ──────────────────────────────────────

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [open])

  // ── Escape key ────────────────────────────────────────────

  useEffect(() => {
    if (!open) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [open])

  // ── Scroll handler ────────────────────────────────────────

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

  // ── Core API call — appends assistant reply (or throws on error) ─

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
    },
    [conversationId]
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

  // ── Auto-resize textarea ──────────────────────────────────

  useEffect(() => {
    const textarea = inputRef.current
    if (!textarea) return
    textarea.style.height = "auto"
    const newHeight = Math.min(textarea.scrollHeight, 120)
    textarea.style.height = `${newHeight}px`
  }, [input])

  const canSend = input.trim().length > 0

  // ── Tab switching ─────────────────────────────────────────

  const handleTabChange = useCallback((tab: Tab) => {
    setActiveTab(tab)
    if (tab === "ticket") {
      setTicketSubmitted(false)
    }
  }, [])

  const handleTicketSuccess = useCallback(() => {
    setTicketSubmitted(true)
  }, [])

  const handleSubmitAnother = useCallback(() => {
    setTicketSubmitted(false)
  }, [])

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-md"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -16 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            role="dialog"
            aria-modal="true"
            aria-label={t("support.chat.title", "ARGO Support")}
          >
            <div className="flex w-full max-w-lg flex-col overflow-hidden rounded-xl border border-border/50 bg-background shadow-2xl shadow-black/20 dark:border-border/30 dark:bg-zinc-900/95 dark:backdrop-blur-2xl max-h-[90vh]">
              {/* Header */}
              <div className="flex shrink-0 items-center justify-between border-b border-border/50 px-4 py-3 dark:border-border/30">
                <h2 className="text-sm font-semibold">
                  {t("support.chat.title", "ARGO Support")}
                </h2>
                <button
                  onClick={() => setOpen(false)}
                  className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                  aria-label={t("common.close", "Close")}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Tab bar */}
              <div className="flex shrink-0 border-b border-border/50 dark:border-border/30">
                <button
                  onClick={() => handleTabChange("chat")}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors",
                    activeTab === "chat"
                      ? "border-b-2 border-primary text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <MessageCircle className="h-4 w-4" />
                  {t("support.liveChat", "Live Chat")}
                </button>
                <button
                  onClick={() => handleTabChange("ticket")}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors",
                    activeTab === "ticket"
                      ? "border-b-2 border-primary text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Ticket className="h-4 w-4" />
                  {t("support.submitTicket", "Submit Ticket")}
                </button>
              </div>

              {/* Chat tab */}
              {activeTab === "chat" && (
                <div className="flex flex-1 flex-col overflow-hidden">
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
                      <div className="flex justify-start">
                        <div className="max-w-[85%] rounded-lg bg-muted px-3.5 py-2">
                          <TypingIndicator />
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
                  <div className="shrink-0 border-t border-border/50 px-3 py-3 dark:border-border/30">
                    <form onSubmit={handleSubmit} className="flex items-end gap-2">
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
                </div>
              )}

              {/* Ticket tab */}
              {activeTab === "ticket" && (
                <div className="flex-1 overflow-y-auto">
                  {ticketSubmitted ? (
                    <TicketSuccess onSubmitAnother={handleSubmitAnother} />
                  ) : (
                    <TicketForm onSuccess={handleTicketSuccess} />
                  )}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
