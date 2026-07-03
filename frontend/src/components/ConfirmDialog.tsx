import { type ReactNode, useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** When true the confirm button gets a danger (red-tinted) style. Default: true. */
  danger?: boolean;
  /** When true both buttons are disabled and the confirm button shows a spinner. */
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  danger = true,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  /** Holds the element that was focused when the dialog opened so we can restore it. */
  const prevFocusRef = useRef<Element | null>(null);

  // Focus management + scroll-lock
  useEffect(() => {
    if (!open) return;

    // Capture current focus so we can restore it on close
    prevFocusRef.current = document.activeElement;

    // Move focus to Cancel (safer default for a destructive action)
    const raf = requestAnimationFrame(() => {
      cancelRef.current?.focus();
    });

    // Prevent background scroll
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      cancelAnimationFrame(raf);
      document.body.style.overflow = prevOverflow;
      // Restore focus to the element that opened the dialog
      if (prevFocusRef.current instanceof HTMLElement) {
        prevFocusRef.current.focus();
      }
    };
  }, [open]);

  // Escape key + focus trap
  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
        return;
      }

      // Trap Tab/Shift-Tab between the two buttons
      if (e.key === 'Tab') {
        const cancel = cancelRef.current;
        const confirm = confirmRef.current;
        if (!cancel || !confirm) return;

        if (e.shiftKey) {
          // Shift+Tab on Cancel → jump to Confirm
          if (document.activeElement === cancel) {
            e.preventDefault();
            confirm.focus();
          }
        } else {
          // Tab on Confirm → jump to Cancel
          if (document.activeElement === confirm) {
            e.preventDefault();
            cancel.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return createPortal(
    <div
      className="modal-backdrop-kb"
      // Clicking the backdrop (not the card) cancels
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="confirm-dialog"
      >
        <h2 id={titleId} className="confirm-dialog-title">
          {title}
        </h2>

        {message && <p className="confirm-dialog-message">{message}</p>}

        <div className="confirm-actions">
          <button
            ref={cancelRef}
            type="button"
            className="btn btn-outline-secondary btn-sm"
            onClick={onCancel}
            disabled={busy}
          >
            {cancelLabel}
          </button>

          <button
            ref={confirmRef}
            type="button"
            className={`btn btn-sm${danger ? ' confirm-btn-danger' : ' btn-primary'}`}
            onClick={onConfirm}
            disabled={busy}
            aria-busy={busy}
          >
            {busy && (
              <span
                className="spinner-border spinner-border-sm me-2"
                role="status"
                aria-hidden="true"
              />
            )}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
