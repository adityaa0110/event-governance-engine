import assert from 'node:assert/strict'
import test from 'node:test'
import { can } from './auth.js'

test('admin satisfies every role', () => {
  assert.equal(can({ roles: ['admin'] }, 'viewer'), true)
  assert.equal(can({ roles: ['admin'] }, 'approver'), true)
})

test('viewer cannot edit or approve', () => {
  assert.equal(can({ roles: ['viewer'] }, 'viewer'), true)
  assert.equal(can({ roles: ['viewer'] }, 'editor'), false)
  assert.equal(can({ roles: ['viewer'] }, 'approver'), false)
})

test('editor can edit and approver can approve', () => {
  assert.equal(can({ roles: ['editor'] }, 'editor'), true)
  assert.equal(can({ roles: ['editor'] }, 'approver'), false)
  assert.equal(can({ roles: ['approver'] }, 'editor'), true)
  assert.equal(can({ roles: ['approver'] }, 'approver'), true)
})

test('missing principal cannot act', () => {
  assert.equal(can(null, 'viewer'), false)
})
