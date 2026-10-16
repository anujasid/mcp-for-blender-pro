# Getting started

Install `mcp-for-blender-pro.zip` through Blender's **Get Extensions → Install from Disk** menu. Enable the extension and open the **MCP Pro** sidebar in the 3D Viewport.

## Connect an assistant

Choose a provider, enter its API key if needed, and click **Load models**. Select a tool-capable model. Save a connection profile to switch between accounts later.

For Ollama, enter the address of your local server. For a custom endpoint, select the matching API protocol and enter the endpoint URL.

## Start a conversation

Ask the assistant to inspect your scene first. Send a small modeling request, approve requested actions, and inspect the result. Open **Studio** for a larger chat workspace with viewport snapshots and scene objects.

Use **Stop** to cancel subsequent steps after the current operation. Use Blender's undo controls when you want to revert a scene edit.

## Work with a team

Open **Team & workflow** in Studio. Add one manager, at least one worker and at least one reviewer. Give each agent a clear responsibility. Select **Team chain**, send a task and follow its progress on the task board.

## Use OpenCode

Click **OpenCode Portable**. OpenCode uses its own saved connections. Select a model from its model list and connect a provider when requested. Your Blender connection is configured automatically.

See [Connections and agents](CONNECTIONS.md) for the provider and MCP details.
