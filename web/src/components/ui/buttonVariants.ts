import { type HTMLAttributes, computed } from 'vue'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/cn'

export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 rounded-ink text-body font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink-primary-muted disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-ink-primary text-[var(--ink-primary-fg)] hover:bg-ink-primary-hover',
        secondary:
          'border border-ink-border bg-ink-surface-muted text-ink-text hover:bg-ink-paper-elevated',
        ghost: 'text-ink-text-secondary hover:bg-ink-surface-muted hover:text-ink-text',
        danger: 'bg-ink-danger text-white hover:opacity-90',
        outline: 'border border-ink-border bg-ink-surface text-ink-text hover:bg-ink-surface-muted',
      },
      size: {
        sm: 'h-8 px-3 text-caption leading-none',
        md: 'h-10 px-4',
        lg: 'h-11 px-5',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>

export { cn }
export type { HTMLAttributes }
export function useButtonClass(
  props: { variant?: ButtonVariants['variant']; size?: ButtonVariants['size']; class?: string },
) {
  return computed(() => cn(buttonVariants({ variant: props.variant, size: props.size }), props.class))
}
