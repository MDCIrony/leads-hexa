import { useState } from 'react';
import { Layout } from './presentation/components/Layout';
import { TabType } from './presentation/components/Sidebar';
import { DashboardPage } from './presentation/pages/DashboardPage';
import { RuleBuilderPage } from './presentation/pages/RuleBuilderPage';
import { BulkUploadPage } from './presentation/pages/BulkUploadPage';
import { SettingsPage } from './presentation/pages/SettingsPage';
import { LeadModel, LeadStatus } from './domain/lead.model';
import { ScoringRuleModel, Operator } from './domain/rule.model';
import { AgentModel } from './domain/agent.model';

export function App() {
  const [tenantId, setTenantId] = useState('b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d');
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');

  const [leads, setLeads] = useState<LeadModel[]>([
    {
      id: '9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d',
      tenantId,
      firstName: 'Maria',
      lastName: 'Gomez',
      email: 'mgomez@techcorp.com',
      company: 'TechCorp Inc',
      budget: 15000,
      industry: 'Technology',
      customAttributes: { employee_count: 150 },
      score: 45,
      status: LeadStatus.ASSIGNED,
      assignedAgentId: 'a3f811c2-1234-5678-90ab-cdef12345678',
      createdAt: '2026-07-31T17:40:00Z',
    },
    {
      id: '8a0ceb3c-2a6c-3abc-8acc-1a0c6a2cba5c',
      tenantId,
      firstName: 'Juan',
      lastName: 'Perez',
      email: 'jperez@smallbiz.es',
      company: 'SmallBiz Local',
      budget: 800,
      industry: 'Retail',
      customAttributes: {},
      score: -5,
      status: LeadStatus.DISQUALIFIED,
      createdAt: '2026-07-31T17:35:00Z',
    },
  ]);

  const [rules, setRules] = useState<ScoringRuleModel[]>([
    {
      id: 'rule-1',
      name: 'High Budget Lead',
      field: 'budget',
      operator: Operator.GREATER_THAN,
      value: 10000,
      scoreDelta: 25,
    },
    {
      id: 'rule-2',
      name: 'Tech Industry Bonus',
      field: 'industry',
      operator: Operator.EQUALS,
      value: 'Technology',
      scoreDelta: 20,
    },
  ]);

  const [agents, setAgents] = useState<AgentModel[]>([
    {
      id: 'a3f811c2-1234-5678-90ab-cdef12345678',
      name: 'Carlos Lopez',
      email: 'clopez@sales.com',
      team: 'Enterprise',
      activeLeadsCount: 1,
      isActive: true,
    },
  ]);

  const handleAddRule = (newRule: Omit<ScoringRuleModel, 'id'>) => {
    setRules((prev) => [...prev, { ...newRule, id: `rule-${Date.now()}` }]);
  };

  const handleDeleteRule = (id: string) => {
    setRules((prev) => prev.filter((r) => r.id !== id));
  };

  const handleAddAgent = (newAgent: Omit<AgentModel, 'id' | 'activeLeadsCount'>) => {
    setAgents((prev) => [
      ...prev,
      { ...newAgent, id: `agent-${Date.now()}`, activeLeadsCount: 0 },
    ]);
  };

  const handleUploadBatch = async (file: File) => {
    // Simulación de carga batch para UI
    const simulatedLead: LeadModel = {
      id: `lead-${Date.now()}`,
      tenantId,
      firstName: 'Batch',
      lastName: 'Imported',
      email: `imported_${Date.now()}@batch.com`,
      company: file.name.replace(/\.[^/.]+$/, ''),
      budget: 12000,
      industry: 'Finance',
      customAttributes: { source_file: file.name },
      score: 30,
      status: LeadStatus.QUALIFIED,
      createdAt: new Date().toISOString(),
    };
    setLeads((prev) => [simulatedLead, ...prev]);
  };

  return (
    <Layout
      tenantId={tenantId}
      onTenantChange={setTenantId}
      activeTab={activeTab}
      onTabChange={setActiveTab}
    >
      {activeTab === 'dashboard' && <DashboardPage leads={leads} />}
      {activeTab === 'rules' && (
        <RuleBuilderPage
          rules={rules}
          onAddRule={handleAddRule}
          onDeleteRule={handleDeleteRule}
        />
      )}
      {activeTab === 'upload' && <BulkUploadPage onUpload={handleUploadBatch} />}
      {activeTab === 'settings' && (
        <SettingsPage agents={agents} onAddAgent={handleAddAgent} />
      )}
    </Layout>
  );
}

export default App;
