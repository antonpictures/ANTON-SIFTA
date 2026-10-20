/**
 * SIFTA brand occupants for the sidebar slots.
 *
 * George, 2026-10-18: "add ant logo instead of whale" and "sifta coding arm
 * not harness". The shipped shell renders a fish/whale in `sidebar.brand.mark`
 * and a generic wordmark in `sidebar.brand.name`; both slots are single, so
 * these registrations shadow the shipped occupants.
 *
 * Colour discipline: every shape uses `currentColor`, so the mark inherits the
 * sidebar text colour and reads correctly in light and dark themes without
 * naming a single hex value or importing a primitives package.
 */
window.__ModuleLoader__.load({
  id: '@local/sifta-brand',
  factory(require) {
    const React = require('react');
    const h = React.createElement;

    /**
     * A worker ant: three body segments, six legs, two antennae, head left.
     * @param props - Host-supplied mark presentation.
     * @returns the SIFTA ant mark.
     */
    function SiftaBrandMark(props) {
      const size = typeof props?.size === 'number' && props.size > 0 ? props.size : 24;
      const body = { fill: 'currentColor', stroke: 'none' };
      const limbs = {
        fill: 'none',
        stroke: 'currentColor',
        strokeWidth: 1.35,
        strokeLinecap: 'round',
        strokeLinejoin: 'round',
      };
      return h(
        'svg',
        {
          viewBox: '0 0 24 24',
          width: size,
          height: size,
          role: 'img',
          'aria-label': 'SIFTA',
          style: { display: 'block', flex: '0 0 auto' },
        },
        // antennae
        h('path', { d: 'M6.1 10.4 L3.9 7.2', ...limbs }),
        h('path', { d: 'M7.4 10.1 L7.1 6.7', ...limbs }),
        // legs: three pairs from the thorax
        h('path', { d: 'M9.6 10.4 L6.7 6.6', ...limbs }),
        h('path', { d: 'M11.0 10.1 L11.0 6.1', ...limbs }),
        h('path', { d: 'M12.4 10.4 L15.3 6.7', ...limbs }),
        h('path', { d: 'M9.6 13.6 L6.5 17.4', ...limbs }),
        h('path', { d: 'M11.0 14.0 L11.0 18.0', ...limbs }),
        h('path', { d: 'M12.4 13.6 L15.5 17.3', ...limbs }),
        // abdomen, thorax, head
        h('ellipse', { cx: 16.6, cy: 12, rx: 4.0, ry: 3.2, ...body }),
        h('ellipse', { cx: 11.0, cy: 12, rx: 2.7, ry: 2.35, ...body }),
        h('circle', { cx: 6.6, cy: 12, r: 2.35, ...body })
      );
    }

    /**
     * The name beside the mark. The Architect asked for "sifta coding arm", so
     * the product name stays loud and the role sits quieter next to it.
     * @returns the SIFTA wordmark.
     */
    function SiftaBrandName() {
      return h(
        'span',
        {
          style: {
            display: 'inline-flex',
            alignItems: 'baseline',
            gap: '0.4em',
            fontSize: '0.95rem',
            fontWeight: 700,
            letterSpacing: '0.02em',
            lineHeight: 1.1,
            whiteSpace: 'nowrap',
            color: 'inherit',
          },
        },
        'SIFTA',
        h(
          'span',
          {
            style: {
              fontSize: '0.72em',
              fontWeight: 500,
              opacity: 0.55,
              letterSpacing: '0.05em',
              textTransform: 'lowercase',
            },
          },
          'coding arm'
        )
      );
    }

    return {
      inject: ['slots'],
      /**
       * Fill both sidebar brand slots as one declaration-aware registration set.
       * @param ctx - Client root context.
       */
      apply(ctx) {
        ctx.slots.inject('sidebar.brand.mark', () =>
          ctx.slots.inject('sidebar.brand.name', function* () {
            yield ctx.slots.register({ name: 'sidebar.brand.mark' }, SiftaBrandMark);
            yield ctx.slots.register({ name: 'sidebar.brand.name' }, SiftaBrandName);
          })
        );
      },
    };
  },
});
