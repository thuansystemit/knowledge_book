import { useCallback, useEffect, useId, useRef, useState } from 'react';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  /** Shown in the trigger when `value` matches no option (e.g. before a value is chosen). */
  placeholder?: string;
  disabled?: boolean;
  /** 'sm' matches Bootstrap's .form-select-sm sizing. Default: 'md'. */
  size?: 'sm' | 'md';
  /** Explicit width; applied as inline style on the container. Without it the container is 100% of its parent. */
  width?: number | string;
  /** Maps to aria-label on both the trigger button and the listbox. */
  ariaLabel?: string;
  /** Applied to the trigger button so that <label htmlFor="…"> associations work. */
  id?: string;
  /** Extra classes forwarded to the outer container div (e.g. 'flex-shrink-0'). */
  className?: string;
}

export function Select({
  value,
  onChange,
  options,
  placeholder = '',
  disabled = false,
  size = 'md',
  width,
  ariaLabel,
  id,
  className = '',
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [flipUp, setFlipUp] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);
  const typeRef = useRef('');
  const typeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const uid = useId();
  const listboxId = `${id ?? uid}-lb`;

  const displayLabel = options.find((o) => o.value === value)?.label ?? placeholder;

  // ── open / close ────────────────────────────────────────────────────────
  const close = useCallback(() => {
    setOpen(false);
    setActiveIdx(-1);
  }, []);

  const openDropdown = useCallback(() => {
    if (disabled) return;
    // Detect whether to flip the panel above the trigger
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setFlipUp(window.innerHeight - rect.bottom < 300);
    }
    const selIdx = options.findIndex((o) => o.value === value && !o.disabled);
    setActiveIdx(selIdx >= 0 ? selIdx : options.findIndex((o) => !o.disabled));
    setOpen(true);
  }, [disabled, options, value]);

  // ── click-outside ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) close();
    };
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [open, close]);

  // ── scroll active option into view ───────────────────────────────────────
  useEffect(() => {
    if (!open || activeIdx < 0) return;
    const el = listboxRef.current?.querySelector<HTMLElement>(`[data-uidx="${activeIdx}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIdx, open]);

  // ── helpers ──────────────────────────────────────────────────────────────
  /** Returns the index of the next non-disabled option in direction dir (wraps). */
  const nextEnabledIdx = (from: number, dir: 1 | -1): number => {
    const len = options.length;
    for (let i = 1; i <= len; i++) {
      const idx = (from + dir * i + len * 2) % len;
      if (!options[idx].disabled) return idx;
    }
    return from;
  };

  const selectAndClose = (idx: number) => {
    if (idx >= 0 && idx < options.length && !options[idx].disabled) {
      onChange(options[idx].value);
      close();
      triggerRef.current?.focus();
    }
  };

  // ── keyboard handler ─────────────────────────────────────────────────────
  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    switch (e.key) {
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (!open) openDropdown();
        else selectAndClose(activeIdx);
        break;
      case 'ArrowDown':
        e.preventDefault();
        if (!open) {
          openDropdown();
        } else {
          setActiveIdx((p) => nextEnabledIdx(p < 0 ? -1 : p, 1));
        }
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (!open) {
          openDropdown();
        } else {
          setActiveIdx((p) => nextEnabledIdx(p < 0 ? options.length : p, -1));
        }
        break;
      case 'Escape':
        e.preventDefault();
        close();
        triggerRef.current?.focus();
        break;
      case 'Tab':
        close();
        break;
      default:
        // Type-ahead: jump to first option whose label starts with the typed prefix
        if (open && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          typeRef.current += e.key.toLowerCase();
          if (typeTimerRef.current) clearTimeout(typeTimerRef.current);
          typeTimerRef.current = setTimeout(() => {
            typeRef.current = '';
          }, 500);
          const prefix = typeRef.current;
          const match = options.findIndex(
            (o, i) =>
              !o.disabled && i !== activeIdx && o.label.toLowerCase().startsWith(prefix),
          );
          if (match >= 0) setActiveIdx(match);
        }
    }
  };

  const containerCls = [
    'ui-select',
    size === 'sm' ? 'ui-select--sm' : '',
    disabled ? 'ui-select--disabled' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      ref={containerRef}
      className={containerCls}
      style={width !== undefined ? { width } : undefined}
    >
      {/* ── Trigger button ── */}
      <button
        ref={triggerRef}
        id={id}
        type="button"
        className={`ui-select-trigger${open ? ' ui-select-trigger--open' : ''}`}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-label={ariaLabel}
        aria-activedescendant={
          open && activeIdx >= 0 ? `${listboxId}-opt-${activeIdx}` : undefined
        }
        onClick={() => (open ? close() : openDropdown())}
        onKeyDown={handleKeyDown}
      >
        <span className="ui-select-value">{displayLabel}</span>
        <i
          className={`bi bi-chevron-down ui-select-chevron${
            open ? ' ui-select-chevron--open' : ''
          }`}
          aria-hidden="true"
        />
      </button>

      {/* ── Dropdown panel ── */}
      {open && (
        <ul
          ref={listboxRef}
          id={listboxId}
          role="listbox"
          className={`ui-select-panel${flipUp ? ' ui-select-panel--up' : ''}`}
          aria-label={ariaLabel}
        >
          {options.map((opt, idx) => {
            const isSelected = opt.value === value;
            const isActive = idx === activeIdx;
            const cls = [
              'ui-select-option',
              isSelected ? 'ui-select-option--selected' : '',
              isActive ? 'ui-select-option--active' : '',
              opt.disabled ? 'ui-select-option--disabled' : '',
            ]
              .filter(Boolean)
              .join(' ');
            return (
              <li
                key={`${opt.value}-${idx}`}
                id={`${listboxId}-opt-${idx}`}
                role="option"
                aria-selected={isSelected}
                aria-disabled={opt.disabled ?? false}
                data-uidx={idx}
                className={cls}
                /* Prevent mousedown from stealing focus from the trigger */
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  if (!opt.disabled) {
                    onChange(opt.value);
                    close();
                    triggerRef.current?.focus();
                  }
                }}
                onMouseEnter={() => {
                  if (!opt.disabled) setActiveIdx(idx);
                }}
              >
                <span className="ui-select-option-label">{opt.label}</span>
                {isSelected && (
                  <i className="bi bi-check ui-select-option-check" aria-hidden="true" />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
