/** Accessible menu groups with shared sticky-heading presentation and viewport observation. */
import { useId, type ReactNode } from 'react'
import css from './MenuGroup.module.css'

/**
 * Render a named group with an instance-owned heading id.
 * @param props - Caller-localized label and optional menu rows.
 * @returns A section named by its direct heading, followed by the supplied children.
 */
export function MenuGroup({ label, children }: { label: string; children?: ReactNode }) {
  const headingId = useId()
  return (
    <section role="group" aria-labelledby={headingId} data-menu-group="" className={css.group}>
      <div id={headingId} data-menu-group-heading="" className={css.heading}>{label}</div>
      {children}
    </section>
  )
}

/**
 * Update direct menu-group headings synchronously, then on scroll and resize.
 * A heading is stuck only while its section straddles the viewport top and scrollTop is positive.
 * Group membership is captured at setup; dispose and observe again when the rendered groups change.
 * @param viewport - Scroll container whose direct groups contain direct data-menu-group-heading children.
 * @returns Cleanup that removes listeners, disconnects size observation, and clears every managed
 * heading's data-stuck attribute. A viewport without groups acquires no listeners or observer.
 */
export function observeStickyMenuGroups(viewport: HTMLElement): () => void {
  const entries = [...viewport.querySelectorAll<HTMLElement>(':scope > [data-menu-group]')].flatMap((section) => {
    const heading = section.querySelector<HTMLElement>(':scope > [data-menu-group-heading]')
    return heading === null ? [] : [{ section, heading }]
  })
  if (entries.length === 0) return () => {}

  const update = (): void => {
    const top = viewport.getBoundingClientRect().top
    // Section boxes retain their normal positions while their headings stick.
    const stuck = entries.map(({ section }) => {
      const bounds = section.getBoundingClientRect()
      return viewport.scrollTop > 0 && bounds.top < top && bounds.bottom > top
    })
    entries.forEach(({ heading }, index) => { heading.toggleAttribute('data-stuck', stuck[index]) })
  }
  update()
  viewport.addEventListener('scroll', update, { passive: true })
  window.addEventListener('resize', update)
  const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(update)
  observer?.observe(viewport)
  for (const { section } of entries) observer?.observe(section)
  return () => {
    viewport.removeEventListener('scroll', update)
    window.removeEventListener('resize', update)
    observer?.disconnect()
    for (const { heading } of entries) heading.removeAttribute('data-stuck')
  }
}
