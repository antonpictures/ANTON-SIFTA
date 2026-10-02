// @vitest-environment jsdom
/** Menu-group naming, sticky transitions, and viewport-observer ownership. */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MenuGroup, observeStickyMenuGroups } from '../src/MenuGroup.tsx'

const disposers: (() => void)[] = []

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', undefined)
})

afterEach(() => {
  for (const dispose of disposers.splice(0)) dispose()
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function observe(viewport: HTMLElement): () => void {
  const dispose = observeStickyMenuGroups(viewport)
  disposers.push(dispose)
  return dispose
}

function fixture() {
  render(
    <div data-testid="viewport">
      <MenuGroup label="Provider A"><button type="button">Model A</button></MenuGroup>
      <MenuGroup label="Provider B"><button type="button">Model B</button></MenuGroup>
    </div>,
  )
  const viewport = screen.getByTestId('viewport')
  const first = screen.getByRole('group', { name: 'Provider A' })
  const second = screen.getByRole('group', { name: 'Provider B' })
  const firstHeading = within(first).getByText('Provider A')
  const secondHeading = within(second).getByText('Provider B')
  const viewportRect = vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 100, 200, 200))
  const firstRect = vi.spyOn(first, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 100, 200, 100))
  const secondRect = vi.spyOn(second, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 203, 200, 100))
  return { viewport, first, second, firstHeading, secondHeading, viewportRect, firstRect, secondRect }
}

describe('MenuGroup', () => {
  it('names each section with a unique direct heading and preserves child order', () => {
    const { first, second, firstHeading, secondHeading } = fixture()
    expect(first.tagName).toBe('SECTION')
    expect(first.hasAttribute('data-menu-group')).toBe(true)
    expect(firstHeading.hasAttribute('data-menu-group-heading')).toBe(true)
    expect(first.getAttribute('aria-labelledby')).toBe(firstHeading.id)
    expect(second.getAttribute('aria-labelledby')).toBe(secondHeading.id)
    expect(firstHeading.id).not.toBe('')
    expect(firstHeading.id).not.toBe(secondHeading.id)
    expect(first.firstElementChild).toBe(firstHeading)
    expect(firstHeading.nextElementSibling).toBe(within(first).getByRole('button', { name: 'Model A' }))
  })

  it('renders a named group without rows', () => {
    render(<MenuGroup label="Empty provider" />)
    const group = screen.getByRole('group', { name: 'Empty provider' })
    expect(group.children).toHaveLength(1)
    expect(group.getAttribute('aria-labelledby')).toBe(within(group).getByText('Empty provider').id)
  })
})

describe('observeStickyMenuGroups', () => {
  it('handles normal headings, sticking, handoff, and scrolling back without ResizeObserver', () => {
    const { viewport, firstHeading, secondHeading, firstRect, secondRect } = fixture()
    observe(viewport)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
    expect(secondHeading.hasAttribute('data-stuck')).toBe(false)

    viewport.scrollTop = 20
    firstRect.mockReturnValue(new DOMRect(0, 80, 200, 100))
    secondRect.mockReturnValue(new DOMRect(0, 183, 200, 100))
    fireEvent.scroll(viewport)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(true)
    expect(secondHeading.hasAttribute('data-stuck')).toBe(false)

    viewport.scrollTop = 100
    firstRect.mockReturnValue(new DOMRect(0, 0, 200, 100))
    secondRect.mockReturnValue(new DOMRect(0, 103, 200, 100))
    fireEvent.scroll(viewport)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
    expect(secondHeading.hasAttribute('data-stuck')).toBe(false)

    viewport.scrollTop = 103
    secondRect.mockReturnValue(new DOMRect(0, 100, 200, 100))
    fireEvent.scroll(viewport)
    expect(secondHeading.hasAttribute('data-stuck')).toBe(false)

    viewport.scrollTop = 104
    firstRect.mockReturnValue(new DOMRect(0, -4, 200, 100))
    secondRect.mockReturnValue(new DOMRect(0, 99, 200, 100))
    fireEvent.scroll(viewport)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
    expect(secondHeading.hasAttribute('data-stuck')).toBe(true)

    viewport.scrollTop = 0
    fireEvent.scroll(viewport)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
    expect(secondHeading.hasAttribute('data-stuck')).toBe(false)
  })

  it('synchronously updates an already-scrolled viewport and reads all boxes before writing attributes', () => {
    const { viewport, firstHeading, secondHeading, viewportRect, firstRect, secondRect } = fixture()
    viewport.scrollTop = 20
    firstRect.mockReturnValue(new DOMRect(0, 80, 200, 100))
    const firstWrite = vi.spyOn(firstHeading, 'toggleAttribute')
    const secondWrite = vi.spyOn(secondHeading, 'toggleAttribute')
    observe(viewport)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(true)
    const reads = [...viewportRect.mock.invocationCallOrder, ...firstRect.mock.invocationCallOrder, ...secondRect.mock.invocationCallOrder]
    const writes = [...firstWrite.mock.invocationCallOrder, ...secondWrite.mock.invocationCallOrder]
    expect(Math.max(...reads)).toBeLessThan(Math.min(...writes))
  })

  it('updates on window resize and removes scroll and resize listeners on cleanup', () => {
    const { viewport, firstHeading, firstRect, viewportRect } = fixture()
    const addScroll = vi.spyOn(viewport, 'addEventListener')
    const removeScroll = vi.spyOn(viewport, 'removeEventListener')
    const removeResize = vi.spyOn(window, 'removeEventListener')
    const dispose = observe(viewport)
    expect(addScroll).toHaveBeenCalledWith('scroll', expect.any(Function), { passive: true })

    viewport.scrollTop = 20
    firstRect.mockReturnValue(new DOMRect(0, 80, 200, 100))
    fireEvent.resize(window)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(true)
    viewportRect.mockReturnValue(new DOMRect(0, 70, 200, 200))
    fireEvent.resize(window)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
    viewportRect.mockReturnValue(new DOMRect(0, 100, 200, 200))
    fireEvent.resize(window)
    expect(firstHeading.hasAttribute('data-stuck')).toBe(true)

    dispose()
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
    expect(removeScroll).toHaveBeenCalledWith('scroll', expect.any(Function))
    expect(removeResize).toHaveBeenCalledWith('resize', expect.any(Function))
    firstRect.mockClear()
    fireEvent.scroll(viewport)
    fireEvent.resize(window)
    expect(firstRect).not.toHaveBeenCalled()
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
  })

  it('observes the viewport and every section when ResizeObserver is available, then disconnects', () => {
    const observeSize = vi.fn()
    const disconnect = vi.fn()
    let notify: () => void = () => { throw new Error('ResizeObserver has not been constructed') }
    class StubResizeObserver implements ResizeObserver {
      observe = observeSize
      unobserve = vi.fn()
      disconnect = disconnect
      constructor(callback: ResizeObserverCallback) {
        notify = () => { callback([], this) }
      }
    }
    vi.stubGlobal('ResizeObserver', StubResizeObserver)
    const { viewport, first, second, firstHeading, secondHeading, firstRect, secondRect } = fixture()
    const dispose = observe(viewport)
    expect(observeSize.mock.calls).toEqual([[viewport], [first], [second]])

    viewport.scrollTop = 20
    firstRect.mockReturnValue(new DOMRect(0, 80, 200, 100))
    notify()
    expect(firstHeading.hasAttribute('data-stuck')).toBe(true)
    firstRect.mockReturnValue(new DOMRect(0, -20, 200, 100))
    secondRect.mockReturnValue(new DOMRect(0, 83, 200, 100))
    notify()
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
    expect(secondHeading.hasAttribute('data-stuck')).toBe(true)

    dispose()
    expect(disconnect).toHaveBeenCalledOnce()
    expect(firstHeading.hasAttribute('data-stuck')).toBe(false)
    expect(secondHeading.hasAttribute('data-stuck')).toBe(false)
  })

  it('ignores nested groups, unmarked sections, and headings that are not direct children', () => {
    render(
      <div data-testid="viewport">
        <MenuGroup label="Direct">
          <MenuGroup label="Nested" />
        </MenuGroup>
        <section data-menu-group=""><div><div data-menu-group-heading="">Indirect</div></div></section>
        <section><div data-menu-group-heading="">Unmarked</div></section>
      </div>,
    )
    const viewport = screen.getByTestId('viewport')
    const direct = screen.getByRole('group', { name: 'Direct' })
    const nested = screen.getByRole('group', { name: 'Nested' })
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 100, 200, 200))
    vi.spyOn(direct, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 80, 200, 100))
    const nestedRect = vi.spyOn(nested, 'getBoundingClientRect')
    viewport.scrollTop = 20
    observe(viewport)
    expect(screen.getByText('Direct').hasAttribute('data-stuck')).toBe(true)
    expect(screen.getByText('Nested').hasAttribute('data-stuck')).toBe(false)
    expect(screen.getByText('Indirect').hasAttribute('data-stuck')).toBe(false)
    expect(screen.getByText('Unmarked').hasAttribute('data-stuck')).toBe(false)
    expect(nestedRect).not.toHaveBeenCalled()
  })

  it('acquires no listeners or ResizeObserver for a viewport without direct groups', () => {
    render(<div data-testid="viewport"><div><MenuGroup label="Nested" /></div></div>)
    const viewport = screen.getByTestId('viewport')
    const addScroll = vi.spyOn(viewport, 'addEventListener')
    const addResize = vi.spyOn(window, 'addEventListener')
    const ResizeObserverStub = vi.fn()
    vi.stubGlobal('ResizeObserver', ResizeObserverStub)
    const dispose = observe(viewport)
    expect(addScroll).not.toHaveBeenCalled()
    expect(addResize).not.toHaveBeenCalled()
    expect(ResizeObserverStub).not.toHaveBeenCalled()
    expect(dispose).not.toThrow()
  })
})
