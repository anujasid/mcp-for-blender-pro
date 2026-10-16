# Connections and teams

In Blender's MCP Pro panel, select Service, enter your API key, click Load models,
then Choose model. The same connection is used by Studio. Credentials stay in
Blender user preferences. Save Preferences to persist them.

For a service not listed, select Custom API:

| API protocol | Base URL example | Appended paths |
|---|---|---|
| OpenAI Chat Completions | `https://your-service.example/v1` | `/models`, `/chat/completions` |
| Anthropic Messages | `https://your-service.example/v1` | `/models`, `/messages` |
| Ollama | `http://localhost:11434` | `/api/tags`, `/api/chat` |

Use the base URL from your provider's API documentation, not its website or a full
completion endpoint. Select a model supporting tool calls. Missing catalogs can
be bypassed by entering the model ID manually. Custom authorization schemes,
OpenAI Responses-only APIs, and unrelated protocols need a separate adapter.

In Studio open Team & workflow. Each agent has a name, position, instructions,
provider, model, manager and enabled switch. Blank provider/model inherit the
workspace setting. Keys come from the saved provider connection. There is one
saved custom endpoint shared by custom agents.

Choose Team chain beside Send. Configure exactly one enabled manager, one or more
workers and one or more reviewers. The manager assigns tasks and acceptance
criteria. Workers execute each task; reviewers approve it or return findings.
One correction attempt is allowed before a second failed review stops the chain.
Tasks run sequentially. Cancel stops subsequent steps after the current operation.
Single assistant retains the normal chat workflow.

Use the header language selector for English, German, French, Spanish
or Chinese. The Blender sidebar has its own Language selector. Main menu labels
are translated; provider errors, model IDs, generated text and some status text
remain in their original language.

## OpenCode

Click OpenCode Portable to open its connection and model dialog. Saved providers
are shown as connected without revealing their keys. Choose Add or change
connection to open OpenCode's provider login window, then refresh the catalog.
Select a model from the list and click OK. OpenCode credentials remain separate
from Blender connection profiles. Use OpenCode's own account controls to switch
between saved accounts.

## External MCP clients

Enable the MCP server in extension preferences. Configure a compatible client
with `http://127.0.0.1:9876/mcp` (or your configured port) and an
`Authorization: Bearer <your access token>` header. Keep the token in the client's
secret store or environment. The bundled OpenCode launcher sets this up for you.
