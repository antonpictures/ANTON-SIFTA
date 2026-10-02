# Agent Note: Image input for any resolvable model route

Status: implemented

## Problem

Image prompts were refused harness-side whenever the route's model did not declare `image` in `inputModalities`. Many OpenAI-compatible deployments accept `image_url` parts without declaring that modality, so the harness was rejecting images the provider would have rendered. Five independent gates refused (read_image tool, prompt upload, DeepSeek adapter serialization, MCP client admission, ACP advertisement/route), so no single-layer relaxation could unblock real routes, and the refusals rotted per deployment.

## Decision

Image-capability gating moved from the harness to the provider. Every gate that previously refused images because the route's model did not declare `image` now admits images whenever the exact model route is resolvable; the provider remains the final arbiter of whether it renders them. Five layers changed together:

| Layer | Package | Change |
|---|---|---|
| `read_image` tool gate | `fs/tool-fs` | `assertImageCapableRoute` only resolves the routed provider/model; no modality check. Failure text is now `cannot read "<path>" as an image: the current model route could not be resolved`. |
| Prompt upload gate | `host/apiproxy` | Removed the `MODEL_DOES_NOT_SUPPORT_IMAGES` refusal in prompt admission; image admission still serializes per agent. |
| DeepSeek adapter | `llm/llm-deepseek` | Removed the stream-start modality gate; image policy resolution already works for any catalog model (declared or default budgets). Unlisted models resolve to default budgets. |
| MCP client admission | `mcp/mcp-client` | `resolveImageAdmission` requires only a mounted attachment store and a resolvable route; it no longer reads the LLM catalog. |
| ACP advertisement + route | `acp/acp` | `supportsAcpImagePrompts` advertises whenever the route resolves (any modalities); `assertImageRoute` keeps only route resolution. |

Unchanged: the legitimate protocol guards — DeepSeek `assertTextOnly`/`assertSupportedImageRoles` (images stay invalid in non-user roles), the ACP `imageEnabled` flag gate in prompt admission, image-format validation (PNG/JPEG/WebP/GIF, canonical base64), and `llm/llm/src/content.ts`'s projection of durable image history into text for an exact text-only model, which bounds poisoned-history damage when a provider does refuse.

## Alternatives considered

- **Keeping per-model gates and whitelisting known-vision model ids** — duplicates the provider's knowledge in the harness and rots per deployment.
- **Relaxing only the tool gate** — uploads, adapter serialization, MCP, and ACP each independently refused, so partial relaxation still blocked real routes.

## Consequences

- A route with a genuinely text-only provider now reaches the provider with image parts and fails there (projected back as an error or text) instead of failing fast in the harness; the text projection keeps such sessions recoverable instead of bricking on a poisoned history.
- `llm-pi-ai` still refuses image input for its models (`UNSUPPORTED_CONTENT`); relaxing it needs the same adapter-level change and is deferred.
- Verification: `llm-deepseek` adapter spec 143/143 (text-only and unlisted-declaration models pass image refs through the Files API wire representation); `tool-fs` read-image spec 29/29; `mcp-client` spec 56/56 (refusals flipped to success-or-route-resolved semantics); `acp` content spec covers resolvable text, undeclared, and fallback routes — all admit; `pnpm run typecheck` passes.
- Snapshot recording for the model-visible change remains a gap: `snapshot:record` requires `DEEPSEEK_API_KEY`, unavailable in this session.