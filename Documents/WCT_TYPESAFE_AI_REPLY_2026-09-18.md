# Reply draft: TypeSafe AI — interfaces vs runtime (2026-09-18)

For George to send. Grounded in SIFTA's real architecture (receipts, four
ledgers, WDP_V1 world packets, NavigateToObject contract).

---

Great question, and it's the exact fork in the road. The honest answer from
building SIFTA: both, but they're not equal halves — the interfaces are the
easy 20%, the runtime is where composability actually lives or dies.

Yes, we lean on typed contracts as the floor — function calling with strict
schemas, versioned service definitions (our robot bridge speaks a
NavigateToObject contract, our world packets are a hash-chained WDP_V1 schema,
every action writes a receipt with a truth label). If you can't call it like a
function with a type you can verify, it's not a primitive, it's a demo.

But the deeper half is the runtime those primitives live in. A function call
proves the AI *said* something; it doesn't prove what happened, who is
responsible for the hardware it touched, or what the system remembers
afterwards. So SIFTA's runtime is a stigmergic field: four append-only ledgers,
every primitive leaves a receipt with provenance and a hash, memory decays and
reinforces like pheromones, and every node carries the identity of the human
who powers it. Composability without that runtime gives you modules that call
each other but can't be trusted or audited — the same horseless-carriage
problem one level down.

So: interfaces are how you invoke intelligence; the receipted field is how you
trust it. The manifesto's Model T point lands exactly there — the chassis
redesign isn't just typed APIs, it's an operating environment where every
composite action is born with its evidence attached.
