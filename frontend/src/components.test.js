import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { ContractEditor, DiffView, formatDiffValue, parametersFromRows } from './contractUi.js'

test('formats diff values and builds parameter payloads', () => {
  assert.equal(formatDiffValue(null), '—')
  assert.equal(formatDiffValue({ price: { type: 'number', required: true } }), '{"price":{"type":"number","required":true}}')
  assert.deepEqual(parametersFromRows([{ name: ' item_id ', type: 'string', required: true, allowed: 'hero, footer', pii: true }, { name: '', type: 'number', required: false }]), {
    item_id: { type: 'string', required: true, allowed_values: ['hero', 'footer'], pii: true },
  })
})

test('renders a diff with before and after values', () => {
  const html = renderToStaticMarkup(
    h(DiffView, {
      diff: {
        baseline_version: '1.0',
        changes: [{ field: 'description', before: 'Old', after: 'New' }],
      },
    }),
  )
  assert.match(html, /Diff vs approved 1\.0/)
  assert.match(html, /description/)
  assert.match(html, /Old/)
  assert.match(html, /New/)
})

test('renders the contract editor with add and remove controls', () => {
  const html = renderToStaticMarkup(h(ContractEditor, { onSubmit: () => {}, initial: null }))
  assert.match(html, /Create draft contract/)
  assert.match(html, /Add parameter/)
  assert.match(html, /Remove/)
  assert.match(html, /Event name/)
  assert.match(html, /Owner/)
  assert.match(html, /BROADBAND/)
  assert.match(html, /PII/)
})

test('renders save controls when editing an existing draft', () => {
  const html = renderToStaticMarkup(
    h(ContractEditor, {
      onSubmit: () => {},
      initial: {
        event_name: 'banner_seen',
        description: 'Banner',
        revision: 2,
        parameters: { banner_id: { type: 'string', required: true } },
      },
    }),
  )
  assert.match(html, /Save contract/)
  assert.match(html, /banner_id/)
  assert.doesNotMatch(html, /Event name/)
})
