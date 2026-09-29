# Deploying Guidelines

- Never deploy (`agents-cli deploy`, `gcloud run deploy`, or similar) unless the user explicitly asks for it in their current message.
- After a code change, test locally with `agents-cli run` or the local Playground (`agents-cli playground` / `adk web`). Don't redeploy to cloud targets just to test.
- If a change only takes effect on the deployed agent, inform the user and ask for explicit approval before deploying.
