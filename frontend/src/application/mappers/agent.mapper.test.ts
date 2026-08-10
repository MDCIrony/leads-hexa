import { describe, expect, it } from 'vitest';
import agentsPageFixture from '../../test/fixtures/agents-page.json';
import { mapAgent } from './agent.mapper';

describe('mapAgent', () => {
  it('maps a real AgentResponse to camelCase, dropping fields the API never sends', () => {
    const agent = mapAgent(agentsPageFixture.items[0]);

    expect(agent).toEqual({
      id: agentsPageFixture.items[0].id,
      name: 'Fixture Agent',
      email: agentsPageFixture.items[0].email,
      groupId: null,
      isActive: true,
      role: 'AGENT',
    });
  });
});
