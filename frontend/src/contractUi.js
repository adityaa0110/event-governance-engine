import { createElement as h, useState } from 'react'

export function formatDiffValue(value) {
  if (value == null || value === '') return '—'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

export function parametersFromRows(rows) {
  const parameters = {}
  for (const row of rows) {
    const name = (row.name || '').trim()
    if (!name) continue
    parameters[name] = { type: row.type || 'string', required: Boolean(row.required) }
  }
  return parameters
}

export function DiffView({ diff }) {
  if (!diff) return null
  if (!diff.baseline_version) return h('p', { className: 'muted' }, 'No approved snapshot to compare yet.')
  const changes = diff.changes || []
  return h(
    'div',
    { className: 'diff-view' },
    h('h3', { style: { fontFamily: 'var(--font-display)' } }, `Diff vs approved ${diff.baseline_version}`),
    changes.length
      ? changes.map((change) =>
          h(
            'p',
            { key: change.field },
            h('code', null, change.field),
            ' ',
            formatDiffValue(change.before),
            ' → ',
            formatDiffValue(change.after),
          ),
        )
      : h('p', { className: 'muted' }, 'Matches the last approved version.'),
  )
}

function emptyRow() {
  return { name: '', type: 'string', required: true }
}

export function ContractEditor({ onSubmit, initial }) {
  const [name, setName] = useState(initial?.event_name || '')
  const [description, setDescription] = useState(initial?.description || '')
  const [rows, setRows] = useState(
    initial?.parameters
      ? Object.entries(initial.parameters).map(([key, spec]) => ({
          name: key,
          type: spec.type || 'string',
          required: spec.required !== false,
        }))
      : [emptyRow()],
  )

  function update(index, patch) {
    setRows((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)))
  }

  return h(
    'form',
    {
      className: 'contract-editor',
      onSubmit: (event) => {
        event.preventDefault()
        onSubmit({
          event_name: name.trim(),
          description: description.trim(),
          parameters: parametersFromRows(rows),
          expected_revision: initial?.revision,
        })
      },
    },
    !initial &&
      h('input', {
        'aria-label': 'Event name',
        value: name,
        required: true,
        placeholder: 'event_name',
        onChange: (event) => setName(event.target.value),
      }),
    h('input', {
      'aria-label': 'Description',
      value: description,
      placeholder: 'Description',
      onChange: (event) => setDescription(event.target.value),
    }),
    rows.map((row, index) =>
      h(
        'div',
        { className: 'toolbar', key: index },
        h('input', {
          'aria-label': `Parameter ${index + 1} name`,
          value: row.name,
          placeholder: 'parameter',
          onChange: (event) => update(index, { name: event.target.value }),
        }),
        h(
          'select',
          {
            'aria-label': `Parameter ${index + 1} type`,
            value: row.type,
            onChange: (event) => update(index, { type: event.target.value }),
          },
          ['string', 'number', 'boolean'].map((type) => h('option', { key: type, value: type }, type)),
        ),
        h('label', null, h('input', {
          type: 'checkbox',
          checked: row.required,
          onChange: (event) => update(index, { required: event.target.checked }),
        }), ' Required'),
        h(
          'button',
          {
            type: 'button',
            className: 'btn btn-secondary',
            onClick: () => setRows((current) => current.filter((_, rowIndex) => rowIndex !== index)),
          },
          'Remove',
        ),
      ),
    ),
    h(
      'div',
      { className: 'toolbar' },
      h(
        'button',
        { type: 'button', className: 'btn btn-secondary', onClick: () => setRows((current) => [...current, emptyRow()]) },
        'Add parameter',
      ),
      h(
        'button',
        { className: 'btn btn-primary', type: 'submit' },
        initial ? 'Save contract' : 'Create draft contract',
      ),
    ),
  )
}
