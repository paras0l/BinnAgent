# BinnAgent Grammar Autofill Extension

Chromium Manifest V3 extension for the grammar micro-topic flow.

## Load locally

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable Developer mode.
3. Click "Load unpacked".
4. Select this folder: `browser-extension/grammar-autofill`.

## Flow

1. In BinnAgent, open Explore -> Grammar micro topics.
2. Select a topic and click "复制并跳转".
3. The extension stores the prompt, opens the target AI site, and fills the first likely chat input. It does not auto-submit.
4. After the AI returns HTML, prefer clicking the copy button on the HTML code block in DeepSeek.
5. Click "发送回 BinnAgent". The extension first reads the copied code block from the clipboard, then falls back to selected text, then visible code blocks.

If the target site changes its DOM and autofill fails, the copied prompt remains on the clipboard, and BinnAgent still supports manual HTML paste.
