import { cn } from "@/lib/utils"

interface PasswordStrengthProps {
  password: string
}

function getScore(password: string): number {
  let score = 0
  if (password.length >= 8) score++
  if (password.length >= 12) score++
  if (/\d/.test(password)) score++
  if (/[^a-zA-Z0-9]/.test(password)) score++
  if (/[A-Z]/.test(password)) score++
  return score
}

const LEVELS = [
  { bars: 1, label: "Weak", color: "bg-red-500" },
  { bars: 2, label: "Fair", color: "bg-orange-500" },
  { bars: 3, label: "Good", color: "bg-yellow-500" },
  { bars: 4, label: "Strong", color: "bg-green-500" },
] as const

function getLevel(score: number) {
  if (score <= 1) return LEVELS[0]
  if (score === 2) return LEVELS[1]
  if (score === 3) return LEVELS[2]
  return LEVELS[3]
}

function meetsCriteria(password: string) {
  return {
    length8: password.length >= 8,
    length12: password.length >= 12,
    number: /\d/.test(password),
    symbol: /[^a-zA-Z0-9]/.test(password),
    uppercase: /[A-Z]/.test(password),
  }
}

export function PasswordStrength({ password }: PasswordStrengthProps) {
  if (!password) return null

  const score = getScore(password)
  const { bars, label, color } = getLevel(score)
  const criteria = meetsCriteria(password)

  return (
    <div className="space-y-2">
      <div
        className="flex gap-1"
        role="progressbar"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={5}
        aria-label={`Password strength: ${label}`}
      >
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={cn("h-1.5 flex-1 rounded-full transition-colors duration-300", i < bars ? color : "bg-muted")}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <ul className="space-y-1 text-xs">
        <li className={criteria.length8 ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}>
          {criteria.length8 ? "✓" : "○"} 8+ characters
        </li>
        <li className={criteria.number ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}>
          {criteria.number ? "✓" : "○"} Number
        </li>
        <li className={criteria.symbol ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}>
          {criteria.symbol ? "✓" : "○"} Symbol
        </li>
        <li className={criteria.uppercase ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}>
          {criteria.uppercase ? "✓" : "○"} Uppercase letter
        </li>
      </ul>
    </div>
  )
}
